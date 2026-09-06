"""Incident / case management endpoints.

Workflow: triaging → investigating → escalated → resolved → closed.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_permission, scope_unit_ids, unit_in_scope
from app.core.exceptions import ApiError, NotFoundError
from app.database.session import get_db
from app.models.agent import Agent
from app.models.alert import Alert
from app.models.incident import Incident, IncidentAlert, IncidentNote
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.models.user import User
from app.schemas.alert import AlertOut
from app.schemas.incident import (
    IncidentCreate,
    IncidentDetail,
    IncidentNoteCreate,
    IncidentNoteOut,
    IncidentOut,
    IncidentUpdate,
)
from app.services.audit import record_audit

router = APIRouter(tags=["incidents"])

VALID_STATUSES = {"triaging", "investigating", "escalated", "resolved", "closed"}
CLOSED_STATUSES = {"resolved", "closed"}


def _next_incident_id() -> str:
    return f"INC-{datetime.now(timezone.utc):%y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _to_alert_out(a: Alert, units: dict, rules: dict) -> AlertOut:
    return AlertOut(
        id=a.id,
        alert_id=a.alert_id,
        rule_id=a.rule_id,
        rule_name=rules.get(a.rule_id),
        title=a.title,
        description=a.description,
        severity=a.severity,
        unit_id=a.unit_id,
        unit_name=units[a.unit_id].unit_code if a.unit_id in units else None,
        agent_id=a.agent_id,
        hostname=a.hostname,
        source_ip=a.source_ip,
        username=a.username,
        event_count=a.event_count,
        first_seen=a.first_seen,
        last_seen=a.last_seen,
        status=a.status,
        risk_score=a.risk_score,
        risk_factors=a.risk_factors,
        mitre_technique=a.mitre_technique,
        mitre_name=a.mitre_name,
        detection_explanation=a.detection_explanation,
        recommended_steps=a.recommended_steps,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _to_out(
    inc: Incident,
    units: dict[str, Unit],
) -> IncidentOut:
    return IncidentOut(
        id=inc.id,
        incident_id=inc.incident_id,
        title=inc.title,
        description=inc.description,
        severity=inc.severity,
        status=inc.status,
        category=inc.category,
        source=inc.source,
        unit_id=inc.unit_id,
        unit_name=units[inc.unit_id].unit_code if inc.unit_id in units else None,
        hostname=inc.hostname,
        source_ip=inc.source_ip,
        username=inc.username,
        mitre_technique=inc.mitre_technique,
        mitre_name=inc.mitre_name,
        alert_count=inc.alert_count,
        event_count=inc.event_count,
        risk_score=inc.risk_score,
        assigned_to=inc.assigned_to,
        created_by=inc.created_by,
        first_seen=inc.first_seen,
        last_seen=inc.last_seen,
        resolved_at=inc.resolved_at,
        closed_at=inc.closed_at,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
    )


def _ctx(db: Session) -> tuple[dict, dict]:
    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.id: r.rule_id for r in db.query(DetectionRule).all()}
    return units, rules


@router.get("/incidents")
def list_incidents(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    unit_id: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _=Depends(require_permission("alerts.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(Incident.unit_id.in_(unit_scope))
    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity.lower())
    if unit_id:
        query = query.filter(Incident.unit_id == unit_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            func.lower(Incident.title).like(like)
            | func.lower(Incident.incident_id).like(like)
            | func.lower(Incident.hostname).like(like)
            | func.lower(Incident.source_ip).like(like)
            | func.lower(Incident.username).like(like)
        )

    total = query.count()
    rows = (
        query.order_by(Incident.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    units, rules = _ctx(db)
    items = [_to_out(i, units).model_dump() for i in rows]
    return {
        "items": items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: str,
    _=Depends(require_permission("alerts.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Incident).filter(or_(Incident.id == incident_id, Incident.incident_id == incident_id))
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(Incident.unit_id.in_(unit_scope))
    inc = query.first()
    if inc is None:
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")
    units, rules = _ctx(db)
    out = _to_out(inc, units)

    linked = (
        db.query(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
        .filter(IncidentAlert.incident_id == inc.id)
        .order_by(Alert.last_seen.desc())
        .all()
    )
    alerts = [_to_alert_out(a, units, rules).model_dump() for a in linked]

    notes = (
        db.query(IncidentNote)
        .filter(IncidentNote.incident_id == inc.id)
        .order_by(IncidentNote.timestamp.asc())
        .all()
    )
    note_out = [IncidentNoteOut.model_validate(n).model_dump() for n in notes]

    return IncidentDetail(**out.model_dump(), alerts=alerts, notes=note_out)


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(
    body: IncidentCreate,
    request: Request,
    _=Depends(require_permission("alerts.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    alert_ids = body.alert_ids or []
    unit_scope = scope_unit_ids(user)
    alert_query = db.query(Alert).filter(Alert.id.in_(alert_ids)) if alert_ids else None
    if alert_query is not None and unit_scope:
        alert_query = alert_query.filter(Alert.unit_id.in_(unit_scope))
    alerts = alert_query.all() if alert_query is not None else []
    found = {a.id for a in alerts}

    if alert_ids and len(found) != len(set(alert_ids)):
        raise NotFoundError("ALERT_NOT_FOUND", "One or more linked alerts not found")

    alert_count = len(alerts)
    event_count = sum(a.event_count or 0 for a in alerts)
    max_risk = max((a.risk_score or 0) for a in alerts) if alerts else 0
    if body.severity is not None and body.severity not in ("critical", "high", "medium", "low"):
        raise ApiError("INVALID_SEVERITY", "Severity must be critical, high, medium or low")
    sevs = [a.severity for a in alerts if a.severity in ("critical", "high", "medium", "low")]
    severity = body.severity
    if not severity and sevs:
        order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        severity = max(sevs, key=lambda s: order[s])

    hostname = body.hostname or (alerts[0].hostname if alerts else None)
    source_ip = body.source_ip or (alerts[0].source_ip if alerts else None)
    username = body.username or (alerts[0].username if alerts else None)
    unit_id = body.unit_id or (alerts[0].unit_id if alerts else None)

    first_seen = min((a.first_seen for a in alerts), default=now)
    last_seen = max((a.last_seen for a in alerts), default=now)

    inc = Incident(
        id=uuid.uuid4().hex[:16],
        incident_id=_next_incident_id(),
        title=body.title,
        description=body.description,
        severity=severity or "medium",
        status="triaging",
        category=body.category,
        source=body.source,
        unit_id=unit_id,
        hostname=hostname,
        source_ip=source_ip,
        username=username,
        mitre_technique=body.mitre_technique,
        mitre_name=body.mitre_name,
        alert_count=alert_count,
        event_count=event_count,
        risk_score=max_risk,
        assigned_to=body.assigned_to,
        created_by=user.id,
        first_seen=first_seen,
        last_seen=last_seen,
    )
    db.add(inc)
    db.flush()

    for a in alerts:
        db.add(IncidentAlert(incident_id=inc.id, alert_id=a.id, timestamp=now))

    record_audit(
        db,
        "incident_created",
        "incidents",
        username=user.username,
        user_id=user.id,
        ip_address=client_ip(request),
        details={"incident_id": inc.incident_id, "linked_alerts": alert_count},
    )
    db.commit()

    units, rules = _ctx(db)
    return _to_out(inc, units)


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    request: Request,
    _=Depends(require_permission("alerts.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(or_(Incident.id == incident_id, Incident.incident_id == incident_id)).first()
    if inc is None:
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")
    unit_scope = scope_unit_ids(user)
    if not unit_in_scope(unit_scope, inc.unit_id):
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")

    if body.status is not None and body.status not in VALID_STATUSES:
        raise ApiError(
            "INVALID_STATUS",
            f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )
    if body.severity is not None and body.severity not in ("critical", "high", "medium", "low"):
        raise ApiError("INVALID_SEVERITY", "Severity must be critical, high, medium or low")

    changed = {}
    for field in ("title", "description", "severity", "status", "category", "source",
                  "hostname", "source_ip", "username", "mitre_technique", "mitre_name",
                  "assigned_to"):
        value = getattr(body, field, None)
        if value is not None and getattr(inc, field) != value:
            changed[field] = {"from": getattr(inc, field), "to": value}
            setattr(inc, field, value)

    if body.status in CLOSED_STATUSES:
        now = datetime.now(timezone.utc)
        if body.status == "resolved":
            inc.resolved_at = now
        inc.closed_at = now

    record_audit(
        db,
        "incident_updated",
        "incidents",
        username=user.username,
        user_id=user.id,
        ip_address=client_ip(request),
        details={"incident_id": inc.incident_id, "changes": changed},
    )
    db.add(inc)
    db.commit()

    units, rules = _ctx(db)
    return _to_out(inc, units)


@router.post("/incidents/{incident_id}/alerts")
def add_alerts_to_incident(
    incident_id: str,
    body: dict,
    request: Request,
    _=Depends(require_permission("alerts.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(or_(Incident.id == incident_id, Incident.incident_id == incident_id)).first()
    if inc is None:
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")
    unit_scope = scope_unit_ids(user)
    if not unit_in_scope(unit_scope, inc.unit_id):
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")
    alert_ids = body.get("alert_ids", [])
    if not alert_ids:
        raise NotFoundError("ALERT_NOT_FOUND", "alert_ids is required")

    existing = {
        ia.alert_id
        for ia in db.query(IncidentAlert).filter(IncidentAlert.incident_id == inc.id).all()
    }
    added = 0
    for alert_id in alert_ids:
        if alert_id in existing:
            continue
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert is None or not unit_in_scope(unit_scope, alert.unit_id):
            continue
        db.add(IncidentAlert(incident_id=inc.id, alert_id=alert_id, timestamp=datetime.now(timezone.utc)))
        added += 1

    if added:
        alerts = (
            db.query(Alert)
            .join(IncidentAlert, IncidentAlert.alert_id == Alert.id)
            .filter(IncidentAlert.incident_id == inc.id)
            .all()
        )
        inc.alert_count = len(alerts)
        inc.event_count = sum(a.event_count or 0 for a in alerts)
        inc.risk_score = max((a.risk_score or 0) for a in alerts) if alerts else 0
        db.add(inc)
        record_audit(
            db, "incident_alerts_added", "incidents",
            username=user.username, user_id=user.id, ip_address=client_ip(request),
            details={"incident_id": inc.incident_id, "added": added},
        )
    db.commit()
    return {"incident_id": inc.incident_id, "added": added}


@router.get("/incidents/{incident_id}/events")
def incident_events(
    incident_id: str,
    limit: int = Query(100, ge=1, le=500),
    _=Depends(require_permission("alerts.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.alert import AlertEvent
    from app.models.event import NormalizedEvent

    query = db.query(Incident).filter(or_(Incident.id == incident_id, Incident.incident_id == incident_id))
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(Incident.unit_id.in_(unit_scope))
    inc = query.first()
    if inc is None:
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")

    rows = (
        db.query(NormalizedEvent)
        .join(AlertEvent, AlertEvent.normalized_event_id == NormalizedEvent.id)
        .join(IncidentAlert, IncidentAlert.alert_id == AlertEvent.alert_id)
        .filter(IncidentAlert.incident_id == inc.id)
        .order_by(NormalizedEvent.timestamp.desc())
        .limit(limit)
        .all()
    )
    seen: set[int] = set()
    unique: list = []
    for e in rows:
        if e.id in seen:
            continue
        seen.add(e.id)
        unique.append(e)
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp,
            "hostname": e.hostname,
            "event_id": e.event_id,
            "category": e.category,
            "action": e.action,
            "severity": e.severity,
            "username": e.username,
            "source_ip": e.source_ip,
            "process_name": e.process_name,
            "command_line": e.command_line,
            "matched_rule_id": e.matched_rule_id,
        }
        for e in unique
    ]


@router.post("/incidents/{incident_id}/notes", response_model=IncidentNoteOut, status_code=201)
def add_incident_note(
    incident_id: str,
    body: IncidentNoteCreate,
    request: Request,
    _=Depends(require_permission("alerts.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(or_(Incident.id == incident_id, Incident.incident_id == incident_id)).first()
    if inc is None:
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")
    unit_scope = scope_unit_ids(user)
    if not unit_in_scope(unit_scope, inc.unit_id):
        raise NotFoundError("INCIDENT_NOT_FOUND", "Incident not found")
    note = IncidentNote(
        incident_id=inc.id,
        user_id=user.id,
        username=user.username,
        content=body.content,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(note)
    db.commit()
    return IncidentNoteOut.model_validate(note)
