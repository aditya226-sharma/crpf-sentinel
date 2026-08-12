"""IOC matching engine.

Matches inbound normalized events against enabled IOC entries
(IP / domain / hash / URL / command) and raises IOC alerts.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.detection.engine import _next_alert_id, _user_can_see_unit
from app.models.alert import Alert, AlertEvent
from app.models.ioc import IocEntry
from app.models.user import User
from app.services.notifications import notify_user
from app.services.risk import compute_risk_score
from app.websocket.stream import publish


def _event_text_fields(event: dict) -> list[str]:
    fields = [
        event.get("source_ip"),
        event.get("destination_ip"),
        event.get("hostname"),
        event.get("username"),
        event.get("process_name"),
        event.get("command_line"),
    ]
    extra = event.get("extra") or {}
    for v in extra.values():
        if isinstance(v, str):
            fields.append(v)
    return [f.lower() for f in fields if f]


def _contains_token(text: str, needle: str) -> bool:
    return any(tok == needle for tok in text.split())


def _ioc_matches(ioc: IocEntry, event: dict) -> bool:
    needle = ioc.value.lower()
    texts = _event_text_fields(event)

    if ioc.ioc_type in ("ip", "domain", "hash", "url"):
        return any(_contains_token(t, needle) for t in texts)
    if ioc.ioc_type == "command":
        cmd = (event.get("command_line") or "").lower()
        return needle in cmd
    return False


def run_ioc_check(db: Session, event: dict, event_row_id: int | None = None) -> list[Alert]:
    """Check a normalized event against enabled IOCs, raising alerts on match.

    Returns the alerts created (or updated) by IOC hits.
    """
    triggered: list[Alert] = []
    iocs = (
        db.query(IocEntry)
        .filter(IocEntry.status == "enabled")
        .all()
    )
    for ioc in iocs:
        if not _ioc_matches(ioc, event):
            continue
        alert = _raise_ioc_alert(db, ioc, event, event_row_id)
        if alert is not None:
            triggered.append(alert)
    return triggered


def _find_open_ioc_alert(
    db: Session, ioc: IocEntry, event: dict
) -> Alert | None:
    """Reuse an existing open alert for the same indicator + unit.

    Mirrors the rule engine's open-alert dedup so repeated matches of the same
    indicator inside a unit aggregate into one alert (bumping event_count)
    instead of flooding the alert list with one new alert per matching event.
    """
    unit_id = event.get("unit_id")
    query = db.query(Alert).filter(
        Alert.rule_id.is_(None),
        Alert.title == f"IOC Match: {ioc.value}",
        Alert.status.in_(["open", "investigating"]),
    )
    if unit_id:
        query = query.filter(Alert.unit_id == unit_id)
    return query.order_by(Alert.last_seen.desc()).first()


def _raise_ioc_alert(db: Session, ioc: IocEntry, event: dict, event_row_id: int | None) -> Alert | None:
    now = datetime.now(timezone.utc)
    severity = ioc.severity or "medium"
    risk_score, risk_factors = compute_risk_score(
        severity=severity,
        event_count=1,
        username=event.get("username"),
        source_ip=event.get("source_ip"),
        event_id=event.get("event_id"),
    )

    title = f"IOC Match: {ioc.value}"
    description = (
        f"Event {event.get('event_id')} from {event.get('hostname')} matched enabled "
        f"{ioc.ioc_type.upper()} indicator {ioc.value}."
        + (f" ({ioc.description})" if ioc.description else "")
    )

    open_alert = _find_open_ioc_alert(db, ioc, event)
    if open_alert is not None:
        open_alert.event_count += 1
        open_alert.last_seen = now
        open_alert.risk_score = max(open_alert.risk_score or 0, risk_score)
        open_alert.risk_factors = risk_factors
        open_alert.source_ip = event.get("source_ip") or open_alert.source_ip
        db.add(open_alert)
        ioc.times_matched += 1
        ioc.last_matched_at = now
        db.add(ioc)
        if event_row_id:
            db.add(
                AlertEvent(
                    alert_id=open_alert.id,
                    normalized_event_id=event_row_id,
                    timestamp=now,
                )
            )
        db.commit()
        return None

    alert = Alert(
        id=uuid.uuid4().hex[:16],
        alert_id=_next_alert_id(),
        rule_id=None,
        title=title,
        description=description,
        severity=severity,
        unit_id=event.get("unit_id"),
        agent_id=event.get("agent_id"),
        hostname=event.get("hostname"),
        source_ip=event.get("source_ip"),
        username=event.get("username"),
        event_count=1,
        first_seen=now,
        last_seen=now,
        status="open",
        risk_score=risk_score,
        risk_factors=risk_factors,
        mitre_technique=None,
        mitre_name=f"IOC:{ioc.ioc_type.upper()}",
        detection_explanation=f"Matched IOC {ioc.ioc_id} ({ioc.ioc_type})",
        recommended_steps=_recommended_steps_plain(),
        correlation_key=event.get("hostname") or event.get("source_ip"),
    )
    db.add(alert)
    db.flush()

    ioc.times_matched += 1
    ioc.last_matched_at = now
    db.add(ioc)

    for user in db.query(User).filter(User.is_active.is_(True)):
        if not _user_can_see_unit(user, event.get("unit_id")):
            continue
        notify_user(
            db,
            user.id,
            f"{severity.upper()} IOC MATCH",
            title,
            severity=severity,
            alert_id=alert.id,
        )

    if event_row_id:
        db.add(
            AlertEvent(
                alert_id=alert.id,
                normalized_event_id=event_row_id,
                timestamp=now,
            )
        )

    db.commit()
    publish(
        "alert",
        {
            "alert_id": alert.alert_id,
            "id": alert.id,
            "title": title,
            "severity": severity,
            "rule_id": None,
            "unit_id": alert.unit_id,
            "hostname": alert.hostname,
            "source_ip": alert.source_ip,
            "status": alert.status,
            "risk_score": risk_score,
        },
    )
    return alert


def _recommended_steps_plain() -> list[str]:
    return [
        "Block the matched indicator at the network perimeter.",
        "Hunt for additional events referencing the same indicator.",
        "Correlate the affected host against the full event timeline.",
        "If confirmed malicious, raise an incident and preserve evidence.",
    ]
