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
