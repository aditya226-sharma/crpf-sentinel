"""Shared alert writer for analysis-based detectors.

The signature engine owns Alert creation for rules. Analysis detectors
(traffic anomalies, VPN audit) need the same Alert pipeline — dedupe against
an open alert, risk-score, notify, stream — so they reuse this writer instead
of duplicating it. Everything still lands in the existing ``Alert`` model.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertEvent
from app.models.rule import DetectionRule
from app.models.user import User
from app.services.notifications import notify_user
from app.services.risk import compute_risk_score
from app.websocket.stream import publish


def get_or_create_rule(db: Session, definition: dict) -> DetectionRule:
    """Idempotent lookup/create of a reference detection rule."""
    rule = db.query(DetectionRule).filter(DetectionRule.rule_id == definition["rule_id"]).first()
    if rule is None:
        kwargs = dict(definition)
        kwargs.setdefault("status", "enabled")
        kwargs.setdefault("event_id", [0])
        kwargs.setdefault("conditions", {})
        kwargs.setdefault("correlation_type", "none")
        kwargs.setdefault("threshold", 1)
        kwargs.setdefault("time_window_seconds", 300)
        rule = DetectionRule(id=uuid.uuid4().hex[:16], **kwargs)
        db.add(rule)
        db.flush()
    return rule


def write_analysis_alert(
    db: Session,
    *,
    rule: DetectionRule,
    event: dict,
    event_row_id: int | None,
    explanation: str,
    severity: str,
    risk_factors: list[dict],
    source_ip: str | None,
    correlation_key: str | None,
    mitre: tuple[str, str] | None = None,
) -> Alert:
    """Create or merge an open alert for an analysis condition."""
    now = datetime.now(timezone.utc)
    open_alert = (
        db.query(Alert)
        .filter(
            Alert.rule_id == rule.id,
            Alert.status.in_(["open", "investigating"]),
        )
        .order_by(Alert.created_at.desc())
        .first()
    )
    if open_alert is not None and correlation_key and open_alert.correlation_key != correlation_key:
        open_alert = None
    if open_alert is not None:
        open_alert.last_seen = now
        open_alert.event_count += 1
        open_alert.source_ip = source_ip or open_alert.source_ip
        db.add(open_alert)
        alert = open_alert
        created = False
    else:
        alert = Alert(
            id=uuid.uuid4().hex[:16],
            alert_id=f"ALT-{now:%y%m%d}-{uuid.uuid4().hex[:6].upper()}",
            rule_id=rule.id,
            title=rule.name,
            description=rule.description,
            severity=severity,
            unit_id=event.get("unit_id"),
            agent_id=event.get("agent_id"),
            hostname=event.get("hostname"),
            source_ip=source_ip,
            event_count=1,
            first_seen=now,
            last_seen=now,
            status="open",
            risk_score=0,
            risk_factors=risk_factors,
            mitre_technique=mitre[0] if mitre else None,
            mitre_name=mitre[1] if mitre else None,
            detection_explanation=explanation,
            recommended_steps=[
                "Review the aggregate telemetry for this indicator.",
                "Correlate against the affected host timeline.",
                "Escalate to the relevant unit security desk if confirmed.",
            ],
            correlation_key=correlation_key,
        )
        db.add(alert)
        db.flush()
        created = True

        for user in db.query(User).filter(User.is_active.is_(True)):
            role_ok = user.role and user.role.name in ("super_admin", "security_expert")
            unit_ok = user.unit_id is not None and user.unit_id == event.get("unit_id")
            if not (role_ok or unit_ok):
                continue
            notify_user(db, user.id, f"{severity.upper()} ALERT", rule.name, severity=severity, alert_id=alert.id)

    risk_score, scored_factors = compute_risk_score(
        severity=severity,
        event_count=alert.event_count,
        username=event.get("username"),
        source_ip=source_ip,
        event_id=event.get("event_id"),
    )
    alert.risk_score = risk_score
    alert.risk_factors = risk_factors + scored_factors
    db.add(alert)

    if event_row_id is not None:
        db.add(AlertEvent(alert_id=alert.id, normalized_event_id=event_row_id, timestamp=now))

    db.commit()

    if created:
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