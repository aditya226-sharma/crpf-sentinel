"""Signature-based detection engine.

Pipeline: normalized_event → match enabled rules → correlation checks →
create/update alert → risk score → notifications → live stream.

Rules are read from PostgreSQL; nothing is hardcoded in the API layer.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.detection.correlation import evaluate_count_rule, evaluate_sequence_rule
from app.detection.matcher import event_matches
from app.models.alert import Alert, AlertEvent
from app.models.event import NormalizedEvent
from app.models.rule import DetectionRule
from app.models.user import User
from app.services.notifications import notify_user
from app.services.risk import compute_risk_score
from app.websocket.stream import publish


def _correlation_key_value(event: dict, key: str | None) -> str | None:
    if not key:
        return None
    value = event.get(key)
    return str(value) if value is not None else None


def _user_can_see_unit(user: User, unit_id: str | None) -> bool:
    """Global roles see all units; unit-scoped users only see their own."""
    if user.role and user.role.name in ("super_admin", "security_expert"):
        return True
    return user.unit_id is not None and user.unit_id == unit_id


def _find_open_alert(
    db: Session, rule: DetectionRule, event: dict, corr_value: str | None
) -> Alert | None:
    query = db.query(Alert).filter(
        Alert.rule_id == rule.id,
        Alert.status.in_(["open", "investigating"]),
    )
    if corr_value:
        query = query.filter(Alert.correlation_key == corr_value)
    return query.order_by(Alert.created_at.desc()).first()


def _run_rule(db: Session, rule: DetectionRule, event: dict) -> Alert | None:
    if rule.correlation_type == "count":
        matched, count = evaluate_count_rule(db, rule, event)
        if not matched:
            return None
        explanation = (
            f"{count} matching events (event_id {event['event_id']}) "
            f"within {rule.time_window_seconds}s window"
        )
        event_count = count
    elif rule.correlation_type == "sequence":
        matched, failure_count, reason = evaluate_sequence_rule(db, rule, event)
        if not matched:
            return None
        explanation = reason
        event_count = failure_count + (1 if event["event_id"] == 4624 else 0)
    else:
        matched, reason = event_matches(event, rule)
        if not matched:
            return None
        explanation = f"Signature matched: {rule.name}"
        event_count = 1

    rule.times_matched += 1
    rule.last_matched_at = datetime.now(timezone.utc)
    db.add(rule)

    corr_key = rule.correlation_key
    corr_value = _correlation_key_value(event, corr_key)
    correlated_success = event["event_id"] == 4624 and rule.correlation_type == "sequence"

    open_alert = _find_open_alert(db, rule, event, corr_value)
    alert_created = open_alert is None
    now = datetime.now(timezone.utc)
    risk_score, risk_factors = compute_risk_score(
        severity=rule.severity,
        event_count=event_count,
        username=event.get("username"),
        source_ip=event.get("source_ip"),
        event_id=event["event_id"],
        correlated_success=correlated_success,
    )

    if open_alert is not None:
        open_alert.event_count = event_count
        open_alert.last_seen = now
        open_alert.risk_score = risk_score
        open_alert.risk_factors = risk_factors
        open_alert.source_ip = event.get("source_ip") or open_alert.source_ip
        open_alert.username = event.get("username") or open_alert.username
        db.add(open_alert)
        alert = open_alert
    else:
        alert = Alert(
            id=uuid.uuid4().hex[:16],
            alert_id=_next_alert_id(),
            rule_id=rule.id,
            title=rule.name,
            description=rule.description,
            severity=rule.severity,
            unit_id=event.get("unit_id"),
            agent_id=event.get("agent_id"),
            hostname=event.get("hostname"),
            source_ip=event.get("source_ip"),
            username=event.get("username"),
            event_count=event_count,
            first_seen=now,
            last_seen=now,
            status="open",
            risk_score=risk_score,
            risk_factors=risk_factors,
            mitre_technique=rule.mitre_technique,
            mitre_name=rule.mitre_name,
            detection_explanation=explanation,
            recommended_steps=_recommended_steps(rule),
            correlation_key=corr_value or event.get("hostname") or event.get("agent_id"),
        )
        db.add(alert)
        db.flush()

        # Notify only users who may see this alert's unit (global roles + matching unit).
        for user in db.query(User).filter(User.is_active.is_(True)):
            if not _user_can_see_unit(user, event.get("unit_id")):
                continue
            notify_user(
                db,
                user.id,
                f"{rule.severity.upper()} ALERT",
                rule.name,
                severity=rule.severity,
                alert_id=alert.id,
            )

    # Link the triggering normalized event to the alert
    event_id_ref = event.get("_event_row_id")
    if event_id_ref:
        db.add(
            AlertEvent(
                alert_id=alert.id,
                normalized_event_id=event_id_ref,
                timestamp=now,
            )
        )

    db.commit()
    if alert_created:
        publish(
            "alert",
            {
                "alert_id": alert.alert_id,
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity,
                "rule_id": rule.rule_id,
                "unit_id": alert.unit_id,
                "hostname": alert.hostname,
                "source_ip": alert.source_ip,
                "status": alert.status,
                "risk_score": alert.risk_score,
            },
        )
    return alert


def _next_alert_id() -> str:
    """Human-readable alert id: ALT-YYMMDD-RANDOM."""
    return f"ALT-{datetime.now(timezone.utc):%y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _recommended_steps(rule: DetectionRule) -> list[str]:
    steps: list[str] = [
        "Correlate the affected host against the full event timeline.",
        "Confirm whether the activity matches known authorized behavior.",
        "Check for related artifacts (new accounts, services, scheduled tasks).",
    ]
    if rule.mitre_technique:
        steps.insert(0, f"Review MITRE ATT&CK technique {rule.mitre_technique} context.")
    return steps


def run_detection_engine(
    db: Session,
    event: dict,
    event_row_id: int | None = None,
    previous_alert_triggered: list[str] | None = None,
) -> tuple[list[Alert], list[str]]:
    """Evaluate a normalized event against all enabled rules.

    Returns (alerts, matched_rule_ids).
    """
    event = dict(event)
    if event_row_id is not None:
        event["_event_row_id"] = event_row_id

    rules = (
        db.query(DetectionRule)
        .filter(DetectionRule.status == "enabled")
        .all()
    )
    triggered: list[Alert] = []
    matched_ids: list[str] = []
    for rule in rules:
        try:
            alert = _run_rule(db, rule, event)
        except Exception:
            continue
        if alert is not None and alert.id not in {a.id for a in triggered}:
            triggered.append(alert)
            matched_ids.append(rule.rule_id)
            if previous_alert_triggered is not None:
                previous_alert_triggered.append(rule.rule_id)
    return triggered, matched_ids
