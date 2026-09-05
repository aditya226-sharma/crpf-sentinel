"""End-to-end smoke tests: auth -> agent -> heartbeat -> ingest -> stats/dashboard.

Exercise the real data pipeline on an isolated SQLite database so the CI gate
fails fast if any link in the chain regresses (seeding, auth, agent
registration, token auth, ingestion, persistence, aggregation).
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _iso(minutes_back: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_back)).isoformat()


def test_login_and_bootstrap(client: TestClient, admin_headers: dict[str, str]):
    resp = client.get("/api/stats", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_units"] >= 1
    assert body["total_rules"] >= 1
    assert body["total_events"] == 0


def test_pipeline_auth_to_dashboard(client: TestClient, admin_headers: dict[str, str]):
    units = client.get("/api/units", headers=admin_headers).json()
    assert units, "seed must create units"
    unit_id = units[0]["id"]

    # 1. Register a simulated agent.
    reg = client.post(
        "/api/agents",
        headers=admin_headers,
        json={
            "agent_id": "WIN-CI-SIM-001",
            "unit_id": unit_id,
            "hostname": "CISIM-001",
            "ip_address": "10.9.9.9",
            "os_version": "smoke (simulated)",
            "agent_version": "1.0.0",
            "simulated": True,
        },
    )
    assert reg.status_code == 201, reg.text
    agent_body = reg.json()
    assert agent_body["agent"]["simulated"] is True
    agent_token = agent_body["api_token"]
    assert agent_token

    # 2. Heartbeat flips the agent online.
    hb = client.post(
        "/api/agents/heartbeat",
        headers={"x-agent-token": agent_token},
        json={
            "hostname": "CISIM-001",
            "events_per_sec": 5,
            "cpu_usage": 1.0,
            "memory_usage": 2.0,
            "buffer_size": 0,
            "sync_status": "healthy",
        },
    )
    assert hb.status_code == 200, hb.text
    assert hb.json()["status"] == "ok"

    agents = client.get("/api/agents", headers=admin_headers).json()
    me = next(a for a in agents if a["agent_id"] == "WIN-CI-SIM-001")
    assert me["status"] == "online"
    assert me["simulated"] is True
    assert me["last_seen_at"] is not None

    # 3. Ingest a batch of Windows-style events (flat collector layout).
    event = {
        "event_id": 4624,
        "provider": "Microsoft-Windows-Security-Auditing",
        "computer": "CISIM-001",
        "time_created": _iso(),
        "data": {
            "SubjectUserName": "Administrator",
            "LogonType": "3",
            "IpAddress": "10.0.0.5",
        },
    }
    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": agent_token},
        json={
            "agent_id": "WIN-CI-SIM-001",
            "unit_id": unit_id,
            "hostname": "CISIM-001",
            "events": [event] * 20,
        },
    )
    assert ing.status_code == 200, ing.text
    ing_body = ing.json()
    assert ing_body["accepted"] == 20
    assert ing_body["parsed"] == 20

    # 4. Persisted and reflected in scoped stats.
    stats = client.get("/api/stats", headers=admin_headers).json()
    assert stats["total_events"] == 20
    assert stats["agents_online"] == 1
    assert stats["events_per_second"] > 0

    # 5. Dashboard aggregates the same data with truthful online semantics.
    dash = client.get("/api/dashboard/summary?period=1h", headers=admin_headers)
    assert dash.status_code == 200, dash.text
    summary = dash.json()
    assert summary["total_events"]["value"] >= 1
    assert str(summary["active_agents"]["value"]).startswith("1 /")
    assert len(summary["live_events"]) >= 1