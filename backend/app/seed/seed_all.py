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


def _purge_future_demo_data(db: Session) -> dict:
    """Repair corrupt demo data from older seed versions.

    Old seeds could write alerts/events/logs with timestamps in the future
    (``day.replace(hour=...)`` on "today"), which made them permanently sort
    as the "most recent" rows and pushed unit risk scores to the max. The
    flood alerts (and their alert<->event links) are removed first, then
    future-dated events not linked to any remaining alert are removed (their
    log back-reference is nulled first to avoid the circular logs<->events
    FK), orphan future logs are dropped, and any remaining future-dated
    events (referenced by kept alerts) are clamped to now.

    Runs with bounded statements (lock/statement timeouts on Postgres) and
    chunked deletes so it can never wedge a deploy. Best-effort: never
    raises, rolls back on failure. Returns counts.
    """
    import logging

    from datetime import datetime, timezone

    from sqlalchemy import delete, or_, select, text, update

    from app.models.alert import Alert, AlertEvent
    from app.models.event import NormalizedEvent
    from app.models.incident import IncidentAlert
    from app.models.log import Log

    logger = logging.getLogger("cyberrakshak.seed")
    now = datetime.now(timezone.utc)
    try:
        for stmt in ("SET lock_timeout = '30s'", "SET statement_timeout = '120s'"):
            try:
                db.execute(text(stmt))
            except Exception:  # noqa: BLE001 - no-op on non-Postgres engines
                pass

        future_alert_ids = [
            r[0]
            for r in db.execute(
                select(Alert.id).where(or_(Alert.first_seen > now, Alert.last_seen > now)).limit(2000)
            )
        ]
        removed_alerts = len(future_alert_ids)
        for i in range(0, len(future_alert_ids), 400):
            chunk = future_alert_ids[i : i + 400]
            db.execute(delete(IncidentAlert).where(IncidentAlert.alert_id.in_(chunk)))
            db.execute(delete(AlertEvent).where(AlertEvent.alert_id.in_(chunk)))
            db.execute(delete(Alert).where(Alert.id.in_(chunk)))

        referenced = select(AlertEvent.normalized_event_id)
        orphan_ids = [
            r[0]
            for r in db.execute(
                select(NormalizedEvent.id)
                .where(
                    NormalizedEvent.timestamp > now,
                    NormalizedEvent.id.notin_(referenced),
                )
                .limit(20000)
            )
        ]
        removed_events = len(orphan_ids)
        for i in range(0, len(orphan_ids), 400):
            chunk = orphan_ids[i : i + 400]
            db.execute(
                update(Log)
                .where(Log.normalized_event_id.in_(chunk))
                .values(normalized_event_id=None)
            )
            db.execute(delete(NormalizedEvent).where(NormalizedEvent.id.in_(chunk)))

        db.execute(
            delete(Log).where(Log.normalized_event_id.is_(None), Log.received_at > now)
        )
        clamped = db.execute(
            update(NormalizedEvent).where(NormalizedEvent.timestamp > now).values(timestamp=now)
        ).rowcount
        db.commit()
        result = {
            "alerts_removed": removed_alerts,
            "events_removed": removed_events,
            "events_clamped": clamped,
        }
    except Exception as exc:  # noqa: BLE001 - repair must never break the app
        db.rollback()
        result = {"alerts_removed": 0, "events_removed": 0, "events_clamped": 0, "error": str(exc)}
        logger.warning("purge of future-dated demo data failed: %s", exc)
    logger.info("purged future-dated demo data: %s", result)
    return result


def purge_future_demo_data() -> dict:
    """Run the future-timestamp repair on its own session (post-startup)."""
    db: Session = SessionLocal()
    try:
        return _purge_future_demo_data(db)
    finally:
        db.close()


def seed_all(include_demo: bool | None = None) -> dict:
    if include_demo is None:
        include_demo = settings.SEED_DEMO_DATA

    init_database()
    db: Session = SessionLocal()
    try:
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
        db.commit()
        return result
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeding complete: {result}")
    print(DEMO_NOTICE)
