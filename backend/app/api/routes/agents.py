"""Windows agent management endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_agent, get_current_user, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_agent_token
from app.database.session import get_db
from app.models.agent import Agent
from app.models.unit import Unit
from app.models.user import User
from app.schemas.agent import AgentHeartbeat, AgentOut, AgentRegister, AgentRegistered, AgentUpdate
from app.services.audit import record_audit

router = APIRouter(tags=["agents"])

STALE_WARNING = timedelta(seconds=120)
STALE_OFFLINE = timedelta(seconds=600)


def _to_out(a: Agent, units: dict[str, Unit]) -> AgentOut:
    return AgentOut(
        id=a.id,
        agent_id=a.agent_id,
        unit_id=a.unit_id,
        unit_name=units[a.unit_id].unit_code if a.unit_id in units else None,
        hostname=a.hostname,
        ip_address=a.ip_address,
        os_version=a.os_version,
        agent_version=a.agent_version,
        status=a.status,
        last_seen_at=a.last_seen_at,
        events_per_sec=a.events_per_sec,
        cpu_usage=a.cpu_usage,
        memory_usage=a.memory_usage,
        buffer_size=a.buffer_size,
        simulated=a.simulated,
        last_sync_status=a.last_sync_status,
        is_enabled=a.is_enabled,
        created_at=a.created_at,
    )


def _refresh_status(agent: Agent) -> None:
    now = datetime.now(timezone.utc)
    last_seen = agent.last_seen_at
    if last_seen is not None and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    if last_seen is None:
        agent.status = "offline"
    elif now - last_seen > STALE_OFFLINE:
        agent.status = "offline"
    elif now - last_seen > STALE_WARNING:
        agent.status = "warning"
    else:
        agent.status = "online" if agent.is_enabled else "disabled"


@router.get("/agents")
def list_agents(
    status: str | None = Query(None),
    unit_id: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
    _=Depends(require_permission("agents.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Agent)
    if user.role.name == "unit_admin":
        query = query.filter(Agent.unit_id == user.unit_id)
    if unit_id:
        query = query.filter(Agent.unit_id == unit_id)
    if q:
        query = query.filter(Agent.hostname.ilike(f"%{q}%"))
    rows = query.order_by(Agent.agent_id.asc()).all()
    units = {u.id: u for u in db.query(Unit).all()}
    for agent in rows:
        _refresh_status(agent)
    db.commit()
    items = [_to_out(a, units).model_dump() for a in rows]
    if status:
        items = [i for i in items if i["status"] == status]
    return items


@router.post("/agents", response_model=AgentRegistered, status_code=201)
def register_agent(
    body: AgentRegister,
    request: Request,
    _=Depends(require_permission("agents.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = db.query(Agent).filter(Agent.agent_id == body.agent_id).first()
    if exists:
        raise ConflictError("AGENT_EXISTS", f"Agent {body.agent_id} already registered")
    unit = db.query(Unit).filter(Unit.id == body.unit_id).first()
    if unit is None:
        raise NotFoundError("UNIT_NOT_FOUND", "Unit not found")

    token, token_hash = generate_agent_token()
    agent = Agent(
        id=uuid.uuid4().hex[:16],
        agent_id=body.agent_id,
        unit_id=body.unit_id,
        hostname=body.hostname,
        ip_address=body.ip_address,
        os_version=body.os_version,
        agent_version=body.agent_version or "1.0.0",
        status="offline",
        auth_token_hash=token_hash,
        is_enabled=True,
        simulated=body.simulated,
        registered_by=user.id,
    )
    db.add(agent)
    record_audit(
        db, "agent_registered", "agents", username=user.username, user_id=user.id,
        ip_address=client_ip(request),
        details={"agent_id": body.agent_id, "unit_id": body.unit_id, "hostname": body.hostname},
    )
    db.commit()
    units = {u.id: u for u in db.query(Unit).all()}
    return AgentRegistered(agent=_to_out(agent, units), api_token=token)


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: str,
    _=Depends(require_permission("agents.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(or_(Agent.id == agent_id, Agent.agent_id == agent_id)).first()
    if agent is None:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found")
    if user.role.name == "unit_admin" and agent.unit_id != user.unit_id:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found")
    _refresh_status(agent)
    db.commit()
    units = {u.id: u for u in db.query(Unit).all()}
    return _to_out(agent, units)


@router.get("/agents/{agent_id}/events")
def agent_events(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    _=Depends(require_permission("agents.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.event import NormalizedEvent

    agent = db.query(Agent).filter(or_(Agent.id == agent_id, Agent.agent_id == agent_id)).first()
    if agent is None:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found")
    if user.role.name == "unit_admin" and agent.unit_id != user.unit_id:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found")
    rows = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.agent_id == agent.id)
        .order_by(NormalizedEvent.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp,
            "hostname": e.hostname,
            "event_id": e.event_id,
            "provider": e.provider,
            "category": e.category,
            "action": e.action,
            "severity": e.severity,
            "username": e.username,
            "source_ip": e.source_ip,
            "matched_rule_id": e.matched_rule_id,
            "is_suspicious": e.is_suspicious,
        }
        for e in rows
    ]


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    request: Request,
    _=Depends(require_permission("agents.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(agent, field, value)
    if body.is_enabled is not None:
        record_audit(
            db, "agent_enabled" if body.is_enabled else "agent_disabled", "agents",
            username=user.username, user_id=user.id, ip_address=client_ip(request),
            details={"agent_id": agent.agent_id},
        )
    db.add(agent)
    db.commit()
    units = {u.id: u for u in db.query(Unit).all()}
    return _to_out(agent, units)


@router.delete("/agents/{agent_id}", status_code=204)
def revoke_agent(
    agent_id: str,
    request: Request,
    _=Depends(require_permission("agents.manage")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found")
    record_audit(
        db, "agent_revoked", "agents", username=user.username, user_id=user.id,
        ip_address=client_ip(request), details={"agent_id": agent.agent_id},
    )
    agent.is_enabled = False
    agent.status = "revoked"
    agent.auth_token_hash = None
    db.add(agent)
    db.commit()
    return None


@router.post("/agents/heartbeat")
def agent_heartbeat(
    body: AgentHeartbeat,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    agent.status = "online"
    agent.last_seen_at = datetime.now(timezone.utc)
    if body.hostname:
        agent.hostname = body.hostname
    if body.ip_address:
        agent.ip_address = body.ip_address
    if body.os_version:
        agent.os_version = body.os_version
    if body.agent_version:
        agent.agent_version = body.agent_version
    agent.events_per_sec = body.events_per_sec
    agent.cpu_usage = body.cpu_usage
    agent.memory_usage = body.memory_usage
    agent.buffer_size = body.buffer_size
    agent.last_sync_status = body.sync_status
    db.add(agent)
    db.commit()
    return {"status": "ok", "agent_id": agent.agent_id, "server_time": datetime.now(timezone.utc).isoformat()}
