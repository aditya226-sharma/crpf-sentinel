"""Platform-wide statistics."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission, scope_unit_ids
from app.database.session import get_db
from app.models.agent import Agent
from app.models.alert import Alert
from app.models.event import NormalizedEvent
from app.models.rule import DetectionRule
from app.models.unit import Unit

router = APIRouter(tags=["stats"])

# Must match dashboard.ONLINE_WINDOW.
ONLINE_WINDOW = timedelta(seconds=120)


@router.get("/stats")
def get_stats(
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unit_scope = scope_unit_ids(user)

    def scoped(q, column):
        if unit_scope:
            return q.filter(column.in_(unit_scope))
        return q

    total_events = scoped(db.query(func.count(NormalizedEvent.id)), NormalizedEvent.unit_id).scalar() or 0
    total_alerts = scoped(db.query(func.count(Alert.id)), Alert.unit_id).scalar() or 0
    open_alerts = (
        scoped(
            db.query(func.count(Alert.id)).filter(Alert.status.in_(["open", "investigating"])),
            Alert.unit_id,
        ).scalar()
        or 0
    )
    agents = scoped(db.query(func.count(Agent.id)), Agent.unit_id).scalar() or 0

    now = datetime.now(timezone.utc)
    agents_online = 0
    events_recent = 0
    agent_rows = scoped(db.query(Agent), Agent.unit_id).all()
    for a in agent_rows:
        last = a.last_seen_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is not None and now - last <= ONLINE_WINDOW:
            agents_online += 1
            events_recent += max(a.events_per_sec, 0)

    units = db.query(func.count(Unit.id)).scalar() or 0
    rules = db.query(func.count(DetectionRule.id)).scalar() or 0

    return {
        "total_events": total_events,
        "total_alerts": total_alerts,
        "open_alerts": open_alerts,
        "total_agents": agents,
        "agents_online": agents_online,
        "total_units": units,
        "total_rules": rules,
        "events_per_second": events_recent,
        "storage_estimate_mb": round(total_events * 0.6 / 1024, 2),
    }
