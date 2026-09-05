"""Platform-wide statistics."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
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

_SETTINGS = get_settings()

# SQLite stores DateTime(timezone=True) columns as naive strings; a tz-aware
# bound parameter then never compares equal in range queries.
_SQLITE = _SETTINGS.DATABASE_URL.startswith("sqlite")


def _db_truncated_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) if _SQLITE else datetime.now(timezone.utc)


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
    agent_rows = scoped(db.query(Agent), Agent.unit_id).all()
    for a in agent_rows:
        last = a.last_seen_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is not None and now - last <= ONLINE_WINDOW:
            agents_online += 1

    # True ingestion rate over the last 60s — stable and un-orchestrated,
    # unlike per-agent heartbeat sampling.
    window_start = _db_truncated_now() - timedelta(seconds=60)
    events_last_minute = (
        scoped(
            db.query(func.count(NormalizedEvent.id)).filter(NormalizedEvent.created_at >= window_start),
            NormalizedEvent.unit_id,
        ).scalar()
        or 0
    )
    events_per_second = round(events_last_minute / 60, 1)

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
        "events_per_second": events_per_second,
        "storage_estimate_mb": round(total_events * 0.6 / 1024, 2),
    }
