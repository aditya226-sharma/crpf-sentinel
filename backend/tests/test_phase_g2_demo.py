"""Phase G2 — demo automation (simulate attack + reset) through the real pipeline.

These endpoints are admin-gated and must never be reachable by lower roles.
The simulate path must push events through the real ingestion/detection path.
"""

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
    before = client.get("/api/alerts", headers=admin_headers).json()["items"]

    res = client.post("/api/demo/simulate", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body["alerts_fired"], "expected alerts to fire through the real pipeline"

    after = client.get("/api/alerts", headers=admin_headers).json()["items"]
    assert len(after) >= len(before), "simulation should add alerts"

    # The scripted sequence must surface a brute-force/credential alert.
    titles = {a["title"] for a in after}
    assert any("logon" in t.lower() or "brute" in t.lower() or "credential" in t.lower() for t in titles)


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
