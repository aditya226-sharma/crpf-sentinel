"""Create tables and seed baseline roles + admin user."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import ROLE_PERMISSIONS
from app.core.security import hash_password
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models.user import Role, User

settings = get_settings()

ROLE_DESCRIPTIONS = {
    "super_admin": "Full platform control and configuration.",
    "security_expert": "Log analysis, detection and alert investigation.",
    "unit_admin": "Scoped access to a single assigned unit.",
    "crime_analyst": "Criminal-intelligence graph analysis and case correlation.",
}

# Landing dashboard shown to a newly logged-in user of each role.
ROLE_DEFAULT_DASHBOARD = {
    "super_admin": "log",
    "security_expert": "log",
    "unit_admin": "log",
    "crime_analyst": "criminal",
}

# Columns added after the platform shipped (no alembic in this codebase).
POSTGRELAUNCH_COLUMNS = {
    "roles": [
        ("default_dashboard", "VARCHAR(32)"),
    ],
}


def _column_exists(db: Session, table: str, column: str) -> bool:
    from sqlalchemy import text

    if db.bind.dialect.name == "sqlite":
        rows = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
        names = {str(r[1]) for r in rows}
        return column in names
    rows = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchall()
    return bool(rows)


def ensure_columns(db: Session) -> None:
    """Idempotently add post-launch columns to existing databases."""
    from sqlalchemy import text

    for table, columns in POSTGRELAUNCH_COLUMNS.items():
        for column, definition in columns:
            if _column_exists(db, table, column):
                continue
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
            db.commit()


def create_tables() -> None:
    import app.models  # noqa: F401  (register all models)

    Base.metadata.create_all(bind=engine)


def seed_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name, permissions in ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == name).first()
        if role is None:
            role = Role(
                id=uuid.uuid4().hex[:16],
                name=name,
                description=ROLE_DESCRIPTIONS.get(name),
                permissions=sorted(permissions),
                default_dashboard=ROLE_DEFAULT_DASHBOARD.get(name),
            )
            db.add(role)
            roles[name] = role
        else:
            role.permissions = sorted(permissions)
            if role.default_dashboard is None:
                role.default_dashboard = ROLE_DEFAULT_DASHBOARD.get(name)
            roles[name] = role
    db.commit()
    return roles


def seed_admin(db: Session, roles: dict[str, Role]) -> User | None:
    admin = db.query(User).filter(User.username == settings.SEED_ADMIN_USERNAME).first()
    if admin is None:
        admin = User(
            id=uuid.uuid4().hex[:16],
            username=settings.SEED_ADMIN_USERNAME,
            email=settings.SEED_ADMIN_EMAIL,
            full_name="Platform Administrator",
            password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
            role_id=roles["super_admin"].id,
            is_active=True,
            must_change_password=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        db.commit()
    return admin


def init_database(seed: bool | None = None) -> None:
    create_tables()
    db: Session = SessionLocal()
    try:
        ensure_columns(db)
        roles = seed_roles(db)
        seed_admin(db, roles)
    finally:
        db.close()
