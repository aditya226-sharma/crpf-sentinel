"""Log management and ingestion endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import (
    get_current_agent,
    get_current_user,
    require_permission,
    scope_unit_ids,
)
from app.core.exceptions import NotFoundError
from app.core.rate_limit import RateLimiter
from app.database.session import get_db
from app.models.agent import Agent
from app.models.event import NormalizedEvent
from app.models.log import Log
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.schemas.log import EventDetail, EventOut, IngestRequest, IngestResponse
from app.services.ingest import ingest_payload

router = APIRouter(tags=["logs"])

ingest_limiter = RateLimiter(get_settings().RATE_LIMIT_INGEST_PER_MINUTE, 60)


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _event_to_out(e: NormalizedEvent, units: dict[str, Unit], rules: dict[str, str]) -> EventOut:
    return EventOut(
        id=e.id,
        timestamp=e.timestamp,
        unit_id=e.unit_id,
        unit_name=units[e.unit_id].unit_code if e.unit_id in units else None,
        agent_id=e.agent_id,
        hostname=e.hostname,
        event_id=e.event_id,
        provider=e.provider,
        category=e.category,
        action=e.action,
        username=e.username,
        source_ip=e.source_ip,
        destination_ip=e.destination_ip,
        process_name=e.process_name,
        command_line=e.command_line,
        logon_type=e.logon_type,
        status_code=e.status_code,
        severity=e.severity,
        is_suspicious=e.is_suspicious,
        simulated=e.simulated,
        matched_rule_id=e.matched_rule_id,
        extra=e.extra,
    )


@router.get("/logs")
def list_logs(
    q: str | None = Query(None, max_length=120),
    event_id: int | None = Query(None),
    severity: str | None = Query(None),
    category: str | None = Query(None),
    unit_id: str | None = Query(None),
    hostname: str | None = Query(None),
    username: str | None = Query(None),
    source_ip: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort: str = Query("desc", pattern=r"^(asc|desc)$"),
    _=Depends(require_permission("logs.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(NormalizedEvent)
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(NormalizedEvent.unit_id.in_(unit_scope))
    if unit_id:
        query = query.filter(NormalizedEvent.unit_id == unit_id)
    if event_id is not None:
        query = query.filter(NormalizedEvent.event_id == event_id)
    if severity:
        query = query.filter(NormalizedEvent.severity == severity)
    if category:
        query = query.filter(NormalizedEvent.category == category)
    if hostname:
        query = query.filter(NormalizedEvent.hostname.ilike(f"%{hostname}%"))
    if username:
        query = query.filter(NormalizedEvent.username.ilike(f"%{username}%"))
    if source_ip:
        query = query.filter(NormalizedEvent.source_ip == source_ip)
    if from_date:
        query = query.filter(NormalizedEvent.timestamp >= from_date)
    if to_date:
        query = query.filter(NormalizedEvent.timestamp <= to_date)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                NormalizedEvent.hostname.ilike(like),
                NormalizedEvent.username.ilike(like),
                NormalizedEvent.source_ip.ilike(like),
                func.cast(NormalizedEvent.event_id, String).like(like),
            )
        )

    total = query.count()
    order = NormalizedEvent.timestamp.asc() if sort == "asc" else NormalizedEvent.timestamp.desc()
    rows = query.order_by(order).offset((page - 1) * page_size).limit(page_size).all()

    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.rule_id: r.name for r in db.query(DetectionRule).all()}
    items = [_event_to_out(e, units, rules) for e in rows]
    return {
        "items": [i.model_dump() for i in items],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/logs/{log_id}", response_model=EventDetail)
def get_log(log_id: int, _=Depends(require_permission("logs.view")), user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(NormalizedEvent).filter(NormalizedEvent.id == log_id)
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(NormalizedEvent.unit_id.in_(unit_scope))
    event = query.first()
    if event is None:
        raise NotFoundError("LOG_NOT_FOUND", "Log entry not found")
    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.rule_id: r.name for r in db.query(DetectionRule).all()}
    out = _event_to_out(event, units, rules)
    log_row = db.query(Log).filter(Log.id == event.log_id).first() if event.log_id else None
    return EventDetail(
        **out.model_dump(),
        parser_version=event.parser_version,
        raw_log=log_row.raw_log if log_row else None,
        log_id=event.log_id,
    )


@router.get("/logs/{log_id}/related")
def related_logs(log_id: int, limit: int = Query(10, ge=1, le=100), _=Depends(require_permission("logs.view")), user=Depends(get_current_user), db: Session = Depends(get_db)):
    unit_scope = scope_unit_ids(user)
    event_query = db.query(NormalizedEvent).filter(NormalizedEvent.id == log_id)
    if unit_scope:
        event_query = event_query.filter(NormalizedEvent.unit_id.in_(unit_scope))
    event = event_query.first()
    if event is None:
        raise NotFoundError("LOG_NOT_FOUND", "Log entry not found")
    query = db.query(NormalizedEvent).filter(NormalizedEvent.id != log_id)
    if unit_scope:
        query = query.filter(NormalizedEvent.unit_id.in_(unit_scope))
    or_clauses = []
    if event.hostname:
        or_clauses.append(NormalizedEvent.hostname == event.hostname)
    if event.source_ip:
        or_clauses.append(NormalizedEvent.source_ip == event.source_ip)
    if event.username:
        or_clauses.append(NormalizedEvent.username == event.username)
    if or_clauses:
        query = query.filter(or_(*or_clauses))
    query = query.filter(
        NormalizedEvent.timestamp >= event.timestamp - timedelta(hours=1),
        NormalizedEvent.timestamp <= event.timestamp + timedelta(hours=1),
    )
    rows = query.order_by(NormalizedEvent.timestamp.desc()).limit(limit).all()
    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.rule_id: r.name for r in db.query(DetectionRule).all()}
    return [_event_to_out(e, units, rules).model_dump() for e in rows]


@router.post("/logs/ingest", response_model=IngestResponse)
def ingest(
    body: IngestRequest,
    request: Request,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    key = f"ingest:{agent.id}"
    if not ingest_limiter.check(key):
        raise HTTPException(status_code=429, detail="Ingestion rate limit exceeded")

    unit = db.query(Unit).filter(Unit.id == agent.unit_id).first()

    if body.heartbeat:
        hb = body.heartbeat
        agent.status = "online"
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.events_per_sec = _coerce_int(hb.get("events_per_sec"), agent.events_per_sec)
        agent.cpu_usage = _coerce_float(hb.get("cpu_usage"), agent.cpu_usage)
        agent.memory_usage = _coerce_float(hb.get("memory_usage"), agent.memory_usage)
        agent.buffer_size = _coerce_int(hb.get("buffer_size"), agent.buffer_size)
        agent.last_sync_status = str(hb.get("sync_status", agent.last_sync_status or ""))[:60]
        agent.status = "online"
        agent.last_seen_at = datetime.now(timezone.utc)
        db.add(agent)

    accepted = 0
    parsed = 0
    alerts_triggered = 0
    matched_rules: list[str] = []
    new_alert_ids: list[str] = []

    for item in body.events:
        payload = item.raw_xml or item.raw_json or item.model_dump(exclude_none=True)
        result = ingest_payload(db, payload, agent=agent, unit=unit)
        accepted += result.get("accepted", 0)
        parsed += result.get("parsed", 0)
        alerts_triggered += result.get("alerts_triggered", 0)
        matched_rules.extend(result.get("matched_rules", []))
        new_alert_ids.extend(result.get("new_alert_ids", []))

    db.commit()
    return IngestResponse(
        accepted=accepted,
        parsed=parsed,
        alerts_triggered=alerts_triggered,
        matched_rules=list(dict.fromkeys(matched_rules)),
        new_alert_ids=list(dict.fromkeys(new_alert_ids)),
    )
