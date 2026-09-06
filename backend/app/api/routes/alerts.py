"""Alert management and investigation endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_permission, scope_unit_ids, unit_in_scope
from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.agent import Agent
from app.models.alert import Alert, AlertEvent
from app.models.event import NormalizedEvent
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.models.user import User
from app.schemas.alert import AlertDetail, AlertEventOut, AlertOut, AlertUpdate
from app.services.audit import record_audit

router = APIRouter(tags=["alerts"])

STATUS_TRANSITIONS = {"open", "investigating", "resolved", "false_positive"}


def _to_out(a: Alert, units: dict, rules: dict) -> AlertOut:
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


@router.get("/alerts")
def list_alerts(
    severity: str | None = Query(None),
    status: str | None = Query(None),
    unit_id: str | None = Query(None),
    rule_id: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _=Depends(require_permission("alerts.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Alert)
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(Alert.unit_id.in_(unit_scope))
    if severity:
        query = query.filter(Alert.severity == severity.lower())
    if status:
        query = query.filter(Alert.status == status)
    if unit_id:
        query = query.filter(Alert.unit_id == unit_id)
    if rule_id:
        query = query.filter(Alert.rule_id == rule_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            func.lower(Alert.alert_id).like(like)
            | func.lower(Alert.title).like(like)
            | func.lower(Alert.hostname).like(like)
            | func.lower(Alert.source_ip).like(like)
        )

    total = query.count()
    rows = (
        query.order_by(Alert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.id: r.rule_id for r in db.query(DetectionRule).all()}
    items = [_to_out(a, units, rules) for a in rows]
    return {
        "items": [i.model_dump() for i in items],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: str, _=Depends(require_permission("alerts.view")), user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Alert).filter(or_(Alert.id == alert_id, Alert.alert_id == alert_id))
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(Alert.unit_id.in_(unit_scope))
    alert = query.first()
    if alert is None:
        raise NotFoundError("ALERT_NOT_FOUND", "Alert not found")
    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.id: r.rule_id for r in db.query(DetectionRule).all()}
    out = _to_out(alert, units, rules)

    linked = (
        db.query(NormalizedEvent)
        .join(AlertEvent, AlertEvent.normalized_event_id == NormalizedEvent.id)
        .filter(AlertEvent.alert_id == alert.id)
        .order_by(NormalizedEvent.timestamp.desc())
        .all()
    )
    unit_map = {u.id: u for u in db.query(Unit).all()}
    rule_names = {r.rule_id: r.name for r in db.query(DetectionRule).all()}
    events = []
    for e in linked:
        events.append(
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "unit_id": e.unit_id,
                "unit_name": unit_map[e.unit_id].unit_code if e.unit_id in unit_map else None,
                "agent_id": e.agent_id,
                "hostname": e.hostname,
                "event_id": e.event_id,
                "provider": e.provider,
                "category": e.category,
                "action": e.action,
                "username": e.username,
                "source_ip": e.source_ip,
                "destination_ip": e.destination_ip,
                "process_name": e.process_name,
                "command_line": e.command_line,
                "logon_type": e.logon_type,
                "status_code": e.status_code,
                "severity": e.severity,
                "is_suspicious": e.is_suspicious,
                "matched_rule_id": e.matched_rule_id,
                "extra": e.extra,
            }
        )
    return AlertDetail(**out.model_dump(), events=events)


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: str,
    body: AlertUpdate,
    request: Request,
    _=Depends(require_permission("alerts.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(or_(Alert.id == alert_id, Alert.alert_id == alert_id)).first()
    if alert is None:
        raise NotFoundError("ALERT_NOT_FOUND", "Alert not found")
    unit_scope = scope_unit_ids(user)
    if not unit_in_scope(unit_scope, alert.unit_id):
        raise NotFoundError("ALERT_NOT_FOUND", "Alert not found")

    if body.status:
        new_status = body.status.lower()
        if new_status not in STATUS_TRANSITIONS:
            raise NotFoundError("INVALID_STATUS", f"Invalid status: {body.status}")
        if new_status != alert.status:
            record_audit(
                db,
                "alert_status_change",
                "alerts",
                username=user.username,
                user_id=user.id,
                ip_address=client_ip(request),
                details={"alert_id": alert.alert_id, "from": alert.status, "to": new_status},
            )
        alert.status = new_status
    if body.assigned_to:
        alert.assigned_to = body.assigned_to
    db.add(alert)
    db.commit()

    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.id: r.rule_id for r in db.query(DetectionRule).all()}
    return _to_out(alert, units, rules)


@router.get("/alerts/{alert_id}/events")
def alert_events(alert_id: str, limit: int = Query(100, ge=1, le=500), _=Depends(require_permission("alerts.view")), user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Alert).filter(or_(Alert.id == alert_id, Alert.alert_id == alert_id))
    unit_scope = scope_unit_ids(user)
    if unit_scope:
        query = query.filter(Alert.unit_id.in_(unit_scope))
    alert = query.first()
    if alert is None:
        raise NotFoundError("ALERT_NOT_FOUND", "Alert not found")
    rows = (
        db.query(AlertEvent)
        .filter(AlertEvent.alert_id == alert.id)
        .order_by(AlertEvent.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        AlertEventOut(
            id=ae.id,
            alert_id=ae.alert_id,
            normalized_event_id=ae.normalized_event_id,
            timestamp=ae.timestamp,
        ).model_dump()
        for ae in rows
    ]
