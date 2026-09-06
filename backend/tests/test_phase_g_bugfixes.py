"""Regression tests for bug-fix pass (case-insensitive severity, incident
event de-duplication, logout IP capture, dashboard bucket endpoint)."""

from fastapi.testclient import TestClient


def test_alerts_severity_filter_is_case_insensitive(
    client: TestClient, admin_headers: dict[str, str]
):
    """BUG 7: ?severity=HIGH must match stored lowercase 'high' alerts."""
    res_mixed = client.get("/api/alerts", headers=admin_headers, params={"severity": "HIGH"})
    assert res_mixed.status_code == 200, res_mixed.text

    res_lower = client.get("/api/alerts", headers=admin_headers, params={"severity": "high"})
    assert res_lower.status_code == 200, res_lower.text

    assert len(res_mixed.json()["items"]) == len(res_lower.json()["items"])
    for item in res_mixed.json()["items"]:
        assert item["severity"] == "high"


def test_incidents_severity_filter_is_case_insensitive(
    client: TestClient, admin_headers: dict[str, str]
):
    """BUG 7: ?severity=CRITICAL must match stored lowercase 'critical' incidents."""
    res_mixed = client.get("/api/incidents", headers=admin_headers, params={"severity": "CRITICAL"})
    assert res_mixed.status_code == 200, res_mixed.text
    for item in res_mixed.json()["items"]:
        assert item["severity"] == "critical"


def test_incident_events_are_deduplicated(client: TestClient, admin_headers: dict[str, str]):
    """BUG 1: events shared across multiple alert join paths must appear once."""
    units = client.get("/api/units", headers=admin_headers).json()
    token = client.post(
        "/api/agents",
        headers=admin_headers,
        json={
            "agent_id": "WIN-DEDUP-001",
            "unit_id": units[0]["id"],
            "hostname": "DEDUP-PROBE",
            "simulated": True,
        },
    ).json()["api_token"]

    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": token},
        json={
            "agent_id": "WIN-DEDUP-001",
            "unit_id": units[0]["id"],
            "events": [
                {
                    "source": "ipsec",
                    "data": {
                        "tunnel_name": "TUNNEL-DEDUP",
                        "peer_ip": "198.51.100.95",
                        "dh_group": "1",
                        "pfs": False,
                        "cipher": "des-cbc",
                        "integrity": "md5",
                    },
                }
            ],
        },
    )
    assert ing.json().get("accepted") == 1

    incident = client.post(
        "/api/incidents",
        headers=admin_headers,
        json={"title": "Dedup incident", "severity": "high"},
    ).json()
    iid = incident["incident_id"]

    alerts = client.get("/api/alerts", headers=admin_headers).json()["items"]
    alert_ids = [a["id"] for a in alerts][:3]
    add = client.post(
        f"/api/incidents/{iid}/alerts",
        headers=admin_headers,
        json={"alert_ids": alert_ids},
    )
    assert add.status_code == 200, add.text

    events = client.get(f"/api/incidents/{iid}/events", headers=admin_headers).json()
    event_ids = [e["id"] for e in events]
    assert len(event_ids) == len(set(event_ids)), "duplicate events returned"
    assert len(events) == 1


def test_logout_records_client_ip(client: TestClient, admin_headers: dict[str, str]):
    """BUG 5: logout audit must capture the client IP (not null)."""
    res = client.post("/api/auth/logout", headers=admin_headers)
    assert res.status_code == 204, res.text

    fresh = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "SmokeT3st!Long-Password"},
    )
    token = fresh.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {token}"}

    out = client.get(
        "/api/audit-logs",
        headers=new_headers,
        params={"action": "logout"},
    )
    assert out.status_code == 200, out.text
    items = out.json()["items"] if "items" in out.json() else out.json()
    assert items, "no logout audit record found"
    assert items[0].get("ip_address"), "logout audit ip_address must not be null"


def test_dashboard_timeseries_endpoint_ok(client: TestClient, admin_headers: dict[str, str]):
    """BUG 6: dashboard timeseries grouping must not 500 (bucket label regression)."""
    res = client.get("/api/dashboard/timeline", headers=admin_headers, params={"period": "hour"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "points" in body or isinstance(body, list)
