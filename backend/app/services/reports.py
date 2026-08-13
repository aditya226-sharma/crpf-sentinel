"""Report generation. CSV/JSON for MVP; PDF is a future add-on."""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.alert import Alert
from app.models.event import NormalizedEvent
from app.models.rule import DetectionRule
from app.models.unit import Unit

REPORT_TYPES = ["daily", "weekly", "unit", "alerts", "rules"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rows_for(
    report_type: str,
    db: Session,
    unit_id: str | None,
    unit_scope: list[str] | None = None,
) -> tuple[str, list[list], list[str]]:
    now = _utcnow()

    def scoped(q, unit_col):
        if unit_scope:
            return q.filter(unit_col.in_(unit_scope))
        return q

    if report_type in ("daily", "weekly"):
        hours = 24 if report_type == "daily" else 24 * 7
        since = now - timedelta(hours=hours)
        is_postgres = db.bind.dialect.name == "postgresql"
        if is_postgres:
            bucket_expr = func.date_trunc("hour", NormalizedEvent.timestamp).label("bucket")
            suspicious_expr = func.sum(
                func.cast(NormalizedEvent.is_suspicious, Integer())
            ).label("suspicious")
        else:
            bucket_expr = func.strftime(
                "%Y-%m-%d %H:00", NormalizedEvent.timestamp
            ).label("bucket")
            suspicious_expr = func.sum(NormalizedEvent.is_suspicious).label("suspicious")
        q = scoped(
            db.query(
                bucket_expr,
                func.count(NormalizedEvent.id).label("events"),
                suspicious_expr,
            ).filter(NormalizedEvent.timestamp >= since),
            NormalizedEvent.unit_id,
        )
        rows = [
            [str(bucket), int(events), int(suspicious or 0)]
            for bucket, events, suspicious in q.group_by("bucket").order_by("bucket").all()
        ]
        return "Hourly event summary", rows, ["timestamp", "events", "suspicious"]

    if report_type == "unit":
        query = scoped(
            db.query(Unit, func.count(Agent.id), func.count(NormalizedEvent.id))
            .outerjoin(Agent, Agent.unit_id == Unit.id)
            .outerjoin(NormalizedEvent, NormalizedEvent.unit_id == Unit.id)
            .group_by(Unit.id),
            Unit.id,
        )
        if unit_id:
            query = query.filter(Unit.id == unit_id)
        rows = [
            [u.unit_code, u.name, agents, events, u.status]
            for u, agents, events in query.all()
        ]
        return "Unit security report", rows, ["unit_code", "name", "agents", "events", "status"]

    if report_type == "alerts":
        query = scoped(db.query(Alert), Alert.unit_id)
        if unit_id:
            query = query.filter(Alert.unit_id == unit_id)
        rows = [
            [a.alert_id, a.title, a.severity, a.status, a.hostname, a.source_ip, a.event_count, a.first_seen.isoformat(), a.risk_score]
            for a in query.order_by(Alert.created_at.desc()).limit(2000).all()
        ]
        return "Alert report", rows, ["alert_id", "title", "severity", "status", "host", "source_ip", "event_count", "first_seen", "risk_score"]

    if report_type == "rules":
        rows = [
            [r.rule_id, r.name, r.severity, r.correlation_type, r.times_matched, r.status, r.mitre_technique or ""]
            for r in db.query(DetectionRule).all()
        ]
        return "Detection rule report", rows, ["rule_id", "name", "severity", "type", "times_matched", "status", "mitre"]

    return "Summary", [], []


def build_report(
    db: Session,
    report_type: str,
    unit_id: str | None = None,
    fmt: str = "csv",
    unit_scope: list[str] | None = None,
) -> tuple[str, str, dict]:
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Unsupported report type: {report_type}")
    title, rows, headers = _rows_for(report_type, db, unit_id, unit_scope)

    if fmt == "json":
        payload = json.dumps({"title": title, "generated_at": _utcnow().isoformat(), "headers": headers, "rows": rows}, indent=2)
        content_type = "application/json"
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        payload = buffer.getvalue()
        content_type = "text/csv"

    meta = {
        "report_type": report_type,
        "title": title,
        "generated_at": _utcnow().isoformat(),
        "rows": len(rows),
    }
    return payload, content_type, meta
