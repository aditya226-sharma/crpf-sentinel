"""Ingestion pipeline: raw event → parse → normalize → store → detect."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.detection.engine import run_detection_engine
from app.detection.ioc import run_ioc_check
from app.models.agent import Agent
from app.models.event import NormalizedEvent
from app.models.log import Log
from app.models.unit import Unit
from app.normalization.engine import normalize_event
from app.parsers import ParserRegistry
from app.parsers.windows import WindowsEventParser
from app.websocket.stream import publish


def ingest_payload(
    db: Session,
    payload: dict | str,
    *,
    agent: Agent,
    unit: Unit | None,
    parser_format: str = "windows",
) -> dict[str, Any]:
    """Parse, normalize, store and run detection for a single raw payload."""
    try:
        parser = ParserRegistry.get(parser_format)
    except ValueError:
        parser = WindowsEventParser()

    parsed = parser.parse(payload)
    if parsed is None:
        return {"accepted": 0, "parsed": 0, "error": "unparseable"}

    unit_id = unit.id if unit else agent.unit_id
    normalized = normalize_event(
        parsed,
        unit_id=unit_id,
        agent_id=agent.id,
        parser_version=parser.version,
    )
    if normalized is None:
        return {"accepted": 1, "parsed": 0, "error": "missing_event_id"}

    raw_log = parsed.raw or (payload if isinstance(payload, str) else "")

    log_row = Log(
        unit_id=unit_id,
        agent_id=agent.id,
        source=parser.format_name,
        format=parser_format,
        raw_log=raw_log[:8000],
        parsed=True,
        received_at=datetime.now(timezone.utc),
    )
    db.add(log_row)
    db.flush()

    event_row = NormalizedEvent(
        log_id=log_row.id,
        timestamp=normalized["timestamp"],
        unit_id=normalized["unit_id"],
        agent_id=normalized["agent_id"],
        hostname=normalized["hostname"],
        event_id=normalized["event_id"],
        provider=normalized["provider"],
        category=normalized["category"],
        action=normalized["action"],
        username=normalized["username"],
        source_ip=normalized["source_ip"],
        destination_ip=normalized["destination_ip"],
        process_name=normalized["process_name"],
        command_line=normalized["command_line"],
        logon_type=normalized["logon_type"],
        status_code=normalized["status_code"],
        severity=normalized["severity"],
        parser_version=normalized["parser_version"],
        is_suspicious=False,
        simulated=agent.simulated,
        extra=normalized["extra"],
    )
    db.add(event_row)
    db.flush()

    alerts, matched_ids = run_detection_engine(db, normalized, event_row_id=event_row.id)
    ioc_alerts = run_ioc_check(db, normalized, event_row_id=event_row.id)
    if ioc_alerts:
        alerts = alerts + ioc_alerts
    if matched_ids or ioc_alerts:
        event_row.is_suspicious = True
        event_row.matched_rule_id = matched_ids[0] if matched_ids else None
        db.add(event_row)
        log_row.normalized_event_id = event_row.id
        db.add(log_row)

    db.commit()

    unit_name = unit.name if unit else None
    publish(
        "event",
        {
            "id": event_row.id,
            "timestamp": event_row.timestamp.isoformat(),
            "unit_id": normalized["unit_id"],
            "unit_name": unit_name,
            "hostname": normalized["hostname"],
            "event_id": normalized["event_id"],
            "category": normalized["category"],
            "action": normalized["action"],
            "severity": normalized["severity"],
            "source_ip": normalized["source_ip"],
            "username": normalized["username"],
            "matched_rule_id": matched_ids[0] if matched_ids else None,
        },
    )

    return {
        "accepted": 1,
        "parsed": 1,
        "alerts_triggered": len(alerts),
        "matched_rules": matched_ids,
        "new_alert_ids": [a.alert_id for a in alerts],
    }
