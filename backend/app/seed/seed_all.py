"""Seed entrypoint: tables + roles + admin + rules + units.

This is a live production platform: startup only bootstraps the schema, the
admin account, detection rules and the CRPF unit structure. Synthetic demo
data seeding has been removed entirely.
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


def seed_all() -> dict:
    """Bootstrap the live platform: roles, admin, detection rules, units."""
    init_database()
    db: Session = SessionLocal()
    try:
        roles = seed_roles(db)
        admin = db.query(User).filter(User.username == settings.SEED_ADMIN_USERNAME).first()
        rules_seeded = seed_rules(db, created_by=admin)
        units = seed_units(db)
        case_records = 0
        demo = {}
        if settings.SEED_DEMO_DATA:
            # Realistic event/alert backdrop + coherent hero incidents + the
            # criminal-intelligence nexus, all via the real ingest pipeline
            # (only in the demo-enabled environment).  Seed only when no events
            # exist yet: a reset already leaves the curated backdrop in place,
            # so re-running on every instance restart would pile ~2.8k orphaned
            # events each time.  Checked first so case-record seeding can never
            # mask an empty DB and trick the guard into skipping the backdrop.
            from app.models.event import NormalizedEvent

            has_backdrop = db.query(NormalizedEvent.id).limit(1).first() is not None
            if not has_backdrop:
                from app.seed.case_records import seed_case_records
                from app.services import demo as demo_svc

                case_records = seed_case_records(db)
                demo["log_backdrop"] = demo_svc.seed_demo_log_data(db)
                demo["hero_incidents"] = demo_svc.seed_hero_incidents(db)
        db.commit()
        return {"rules": rules_seeded, "units": len(units), "case_records": case_records, "demo": demo}
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeding complete: {result}")
