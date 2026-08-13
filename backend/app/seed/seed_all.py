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
        db.commit()
        return {"rules": rules_seeded, "units": len(units)}
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeding complete: {result}")
