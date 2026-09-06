"""Test bootstrap: isolated SQLite database + seeded app.

Environment is forced BEFORE any ``app`` import so the test process can never
touch the production database or pick up local ``.env`` values.
"""

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='cyberrakshak-smoke-')}/smoke.db"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "ci-smoke-secret-0123456789abcdef0123456789abcdef"
os.environ["SEED_ADMIN_USERNAME"] = "admin"
os.environ["SEED_ADMIN_PASSWORD"] = "SmokeT3st!Long-Password"
os.environ["SEED_ADMIN_EMAIL"] = "smoke-test@cyberrakshak.in"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["RATE_LIMIT_LOGIN_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_GENERAL_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_INGEST_PER_MINUTE"] = "100000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pristine_db() -> None:
    """Reset schema + reseed for every test module.

    Module scope gives each module a pristine database, so modules can assert
    on absolute totals without cross-module pollution.
    """
    from app.database.base import Base
    from app.database.session import engine

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    from app.seed.seed_all import seed_all

    seed_all()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """App against the pristine, seeded SQLite database."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={
            "username": os.environ["SEED_ADMIN_USERNAME"],
            "password": os.environ["SEED_ADMIN_PASSWORD"],
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}