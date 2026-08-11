"""Seed entrypoint: tables + roles + admin + demo data + rules.

Run with:  python -m app.seed.seed_all
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.init_db import init_database, seed_roles
from app.database.session import SessionLocal
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.models.user import User
from app.seed.demo_data import (
    DEMO_NOTICE,
    seed_agents,
    seed_demo_data,
    seed_demo_users,
    seed_units,
)
from app.seed.demo_rules import seed_rules
from app.seed.soc import seed_demo_incidents, seed_iocs

settings = get_settings()


def _purge_future_demo_events(db: Session) -> dict:
    """Repair demo timestamps on existing databases.

    Older seed versions could write events with timestamps in the future
    (``day.replace(hour=...)`` on "today"), which made them permanently sort
    as the "most recent" events. Bulk events not linked to alerts are removed
    (with their raw logs); any remaining future-dated events (attack bursts
    referenced by alerts) are clamped to now. Returns counts of removed and
    clamped events.
    """
    from datetime import datetime, timezone

    from app.models.alert import AlertEvent
    from app.models.event import NormalizedEvent
    from app.models.log import Log

    now = datetime.now(timezone.utc)
    referenced = set(
        rid
        for (rid,) in db.query(AlertEvent.normalized_event_id).filter(AlertEvent.normalized_event_id.isnot(None)).all()
    )
    orphan_ids = [
        (eid,)
        for (eid,) in db.query(NormalizedEvent.id)
        .filter(NormalizedEvent.timestamp > now)
        .filter(NormalizedEvent.id.notin_(referenced) if referenced else True)
        .all()
    ]
    removed = len(orphan_ids)
    if orphan_ids:
        flat = [i for (i,) in orphan_ids]
        db.query(Log).filter(Log.normalized_event_id.in_(flat)).delete(synchronize_session=False)
        db.query(NormalizedEvent).filter(NormalizedEvent.id.in_(flat)).delete(synchronize_session=False)

    clamped = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.timestamp > now)
        .update({NormalizedEvent.timestamp: now}, synchronize_session=False)
    )
    db.commit()
    return {"events_removed": removed, "events_clamped": clamped}


def seed_all(include_demo: bool | None = None) -> dict:
    if include_demo is None:
        include_demo = settings.SEED_DEMO_DATA

    init_database()
    db: Session = SessionLocal()
    try:
        repaired = _purge_future_demo_events(db)
        roles = seed_roles(db)
        admin = db.query(User).filter(User.username == settings.SEED_ADMIN_USERNAME).first()
        rules_seeded = seed_rules(db, created_by=admin)
        units = seed_units(db)
        agents = seed_agents(db, units)
        seed_demo_users(db, units, roles)

        result: dict = {"rules": rules_seeded}
        if include_demo:
            from app.models.event import NormalizedEvent

            already_seeded = db.query(NormalizedEvent.id).first() is not None
            if already_seeded:
                demo = {"events_created": 0, "attack_bursts": 0}
            else:
                demo = seed_demo_data(db, units, agents)
            result.update(demo)
        iocs = seed_iocs(db)
        incidents = seed_demo_incidents(db)
        result["iocs_seeded"] = iocs
        result["incidents_seeded"] = incidents
        result["repair"] = repaired
        db.commit()
        return result
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeding complete: {result}")
    print(DEMO_NOTICE)
