"""Phase G2 — demo automation (simulate attack + reset) through the real pipeline.

These endpoints are admin-gated and must never be reachable by lower roles.
The simulate path must push events through the real ingestion/detection path.
"""

import os

import pytest
from fastapi.testclient import TestClient


def _make_unit(client: TestClient, headers: dict[str, str], code: str) -> dict:
    existing = client.get("/api/units", headers=headers).json()
    for u in existing:
        if u["unit_code"] == code:
            return u
    res = client.post(
        "/api/units",
        headers=headers,
        json={
            "unit_code": code,
            "name": f"{code} Demo Unit",
            "region": "North",
            "city": "New Delhi",
            "state": "Delhi",
            "latitude": 28.61,
            "longitude": 77.2,
            "status": "operational",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _lower_priv_headers(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    roles = client.get("/api/roles", headers=admin_headers).json()
    unit_admin_role = next(r["id"] for r in roles if r["name"] == "unit_admin")
    res = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "demotest",
            "email": "demotest@cyberrakshak.demo",
            "full_name": "Demo Test",
            "password": "DemoTest@123",
            "role_id": unit_admin_role,
        },
    )
    # 409 = user already exists from a prior test in this module; reuse it.
    assert res.status_code in (201, 409), res.text
    login = client.post(
        "/api/auth/login", json={"username": "demotest", "password": "DemoTest@123"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_simulate_is_admin_gated(client: TestClient, admin_headers: dict[str, str]):
    lower = _lower_priv_headers(client, admin_headers)
    denied = client.post("/api/demo/simulate", headers=lower)
    assert denied.status_code == 403, denied.text

    unauthed = client.post("/api/demo/simulate")
    assert unauthed.status_code in (401, 403)


def test_simulate_attack_fires_real_alerts(client: TestClient, admin_headers: dict[str, str]):
    _make_unit(client, admin_headers, "UNIT-99")

    res = client.post("/api/demo/simulate", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body["alerts_fired"], "expected alerts to fire through the real pipeline"
    assert body["backdrop_events"] > 0, "expected recent ambient backdrop to fill window widgets"
    assert body["iocs_created"] > 0, "expected threat-intel indicators to be seeded"

    # The scripted sequence must surface a brute-force/credential alert.
    after = client.get("/api/alerts", headers=admin_headers).json()["items"]
    titles = {a["title"] for a in after}
    assert any("logon" in t.lower() or "brute" in t.lower() or "credential" in t.lower() for t in titles)

    # The simulation enriches the IOC library with the campaign indicators.
    iocs = client.get("/api/ioc", headers=admin_headers).json()
    assert iocs["meta"]["total"] > 0
    values = {i["value"] for i in iocs["items"]}
    assert "203.0.113.66" in values

    # Simulate again is idempotent for IOC seeding (same campaign values).
    res2 = client.post("/api/demo/simulate", headers=admin_headers)
    assert res2.status_code == 200, res2.text
    assert res2.json()["iocs_created"] == 0, "IOC seeding must be idempotent"


def test_simulate_records_audit(client: TestClient, admin_headers: dict[str, str]):
    res = client.post("/api/demo/simulate", headers=admin_headers)
    assert res.status_code == 200, res.text
    audit = client.get("/api/audit-logs", headers=admin_headers).json()
    items = audit["items"] if isinstance(audit, dict) and "items" in audit else audit
    assert any(i.get("action") == "demo_simulate" for i in items)


def test_reset_is_admin_gated(client: TestClient, admin_headers: dict[str, str]):
    lower = _lower_priv_headers(client, admin_headers)
    assert client.post("/api/demo/reset", headers=lower).status_code == 403


def test_reset_after_simulate_is_clean_and_idempotent(client: TestClient, admin_headers: dict[str, str]):
    """Simulate then reset — must clear artifacts without FK errors and stay idempotent."""
    client.post("/api/demo/reset", headers=admin_headers)  # clean slate from prior module tests

    fired = client.post("/api/demo/simulate", headers=admin_headers)
    assert fired.status_code == 200, fired.text
    sim_alerts = len(fired.json()["alerts_fired"])
    assert sim_alerts > 0

    first = client.post("/api/demo/reset", headers=admin_headers)
    assert first.status_code == 200, first.text
    assert first.json()["removed_alerts"] >= sim_alerts

    agents = client.get("/api/agents", headers=admin_headers).json()
    assert isinstance(agents, list) and agents, "shared sim agents persist for the backdrop"

    # Second reset is harmless and returns a clean summary (idempotent).
    second = client.post("/api/demo/reset", headers=admin_headers)
    assert second.status_code == 200, second.text
    assert second.json()["removed_alerts"] >= 0
    assert second.json()["removed_events"] >= 0


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="set TEST_POSTGRES_URL to exercise the Postgres TRUNCATE reset path",
)
def test_reset_truncate_path_on_postgres():
    """Postgres reset must use TRUNCATE and restore the curated baseline fast.

    Skips unless TEST_POSTGRES_URL is set (CI runs on SQLite, where the DELETE
    fallback is exercised instead).  Guards against the reset silently degrading
    back to slow row-deletes that die on resource-limited hosts.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.database.base import Base
    from app.database.init_db import seed_roles
    from app.seed.demo_data import seed_units
    from app.seed.demo_rules import seed_rules
    from app.services.demo import reset_demo, seed_demo_log_data

    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Idempotent baseline on a shared test DB; Postgres TRUNCATE ... CASCADE
        # resolves the circular logs<->normalized_events FK itself.
        db.execute(text("TRUNCATE TABLE incidents, alerts, logs RESTART IDENTITY CASCADE"))
        db.commit()
        seed_roles(db)
        seed_units(db)
        seed_rules(db)

        for _ in range(5):
            seed_demo_log_data(db)

        total = db.execute(text("SELECT count(*) FROM normalized_events")).scalar()
        assert total > 10_000, f"expected accumulated dataset, got {total}"

        result = reset_demo(db)
        assert result["removed_events"] >= total, result

        clean = db.execute(text("SELECT count(*) FROM normalized_events")).scalar()
        assert 0 < clean < 5_000, f"expected reseeded baseline, got {clean}"
        assert db.execute(text("SELECT count(*) FROM logs")).scalar() == clean

        # Reset must be idempotent.
        second = reset_demo(db)
        assert second["removed_events"] <= clean
    finally:
        db.close()
        engine.dispose()


def test_sustain_refreshes_heartbeats(client: TestClient, admin_headers: dict[str, str]):
    """Keepalive must reset stale simulated-agent heartbeats (and only those)."""
    from datetime import datetime, timedelta

    from app.database.session import SessionLocal
    from app.models.agent import Agent
    from app.services.demo import simulate_attack, sustain_environment

    with SessionLocal() as db:
        simulate_attack(db)
        agents = db.query(Agent).filter(Agent.simulated.is_(True)).all()
        assert agents, "simulated agents expected after simulate_attack"
        stale_before = {a.agent_id: a.last_seen_at for a in agents}
        for a in agents:
            a.last_seen_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        result = sustain_environment(db)
        assert result["agents_heartbeat"] == len(agents), result

        refreshed = db.query(Agent).filter(Agent.agent_id.in_(stale_before)).all()
        for a in refreshed:
            age = (datetime.utcnow() - a.last_seen_at).total_seconds()
            assert age < 30, f"heartbeat not refreshed: {a.agent_id} age={age}s"
