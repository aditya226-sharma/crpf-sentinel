"""Seed entrypoint: tables + roles + admin + rules + units (+ optional demo data).

Run with:  python -m app.seed.seed_all
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.init_db import init_database, seed_roles
from app.database.session import SessionLocal
from app.models.user import User
from app.seed.demo_data import seed_units
from app.seed.demo_rules import seed_rules

settings = get_settings()


def seed_all(include_demo: bool | None = None) -> dict:
    """Bootstrap the platform.

    Live mode (default) seeds roles, the admin account, detection rules and
    the CRPF unit structure. Demo mode additionally seeds synthetic agents,
    users, events, incidents and IOC entries for evaluation purposes.
    """
    if include_demo is None:
        include_demo = settings.SEED_DEMO_DATA

    init_database()
    db: Session = SessionLocal()
    try:
        roles = seed_roles(db)
        admin = db.query(User).filter(User.username == settings.SEED_ADMIN_USERNAME).first()
        rules_seeded = seed_rules(db, created_by=admin)
        units = seed_units(db)

        result: dict = {"rules": rules_seeded, "units": len(units)}

        if include_demo:
            from app.models.event import NormalizedEvent
            from app.seed.demo_data import seed_agents, seed_demo_data, seed_demo_users
            from app.seed.soc import seed_demo_incidents, seed_iocs

            agents = seed_agents(db, units)
            seed_demo_users(db, units, roles)
            already_seeded = db.query(NormalizedEvent.id).count() >= 5000
            if already_seeded:
                demo = {"events_created": 0, "attack_bursts": 0}
            else:
                demo = seed_demo_data(db, units, agents)
            result.update(demo)
            result["iocs_seeded"] = seed_iocs(db)
            result["incidents_seeded"] = seed_demo_incidents(db)

        db.commit()
        return result
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeding complete: {result}")
