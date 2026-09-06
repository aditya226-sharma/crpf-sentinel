"""Phase E — template query endpoint.

Proves the natural-language bar answers through explicit templates (no
inference): open alerts, failed logons, network bursts, graph paths, and a
low-confidence fallback — all data from the existing pipeline models.
"""

from fastapi.testclient import TestClient


def _register_agent(client: TestClient, headers: dict[str, str], agent_id: str, unit: dict) -> str:
    res = client.post(
        "/api/agents",
        headers=headers,
        json={
            "agent_id": agent_id,
            "unit_id": unit["id"],
            "hostname": "Q-PROBE",
            "simulated": True,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["api_token"]


def test_query_fallback_low_confidence(client: TestClient, admin_headers: dict[str, str]):
    res = client.post("/api/query", headers=admin_headers, json={"query": "zzzz banana quantum flux"})
    assert res.status_code == 200
    body = res.json()
    assert body["template"] == "fallback"
    assert body["confidence"] == "low"
    assert not body["results"]


def test_query_open_alerts_template(
    client: TestClient, admin_headers: dict[str, str]
):
    units = client.get("/api/units", headers=admin_headers).json()
    token = _register_agent(client, admin_headers, "WIN-Q-ALT-001", units[0])

    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": token},
        json={
            "agent_id": "WIN-Q-ALT-001",
            "unit_id": units[0]["id"],
            "events": [
                {
                    "source": "ipsec",
                    "data": {
                        "tunnel_name": "TUNNEL-QUERY",
                        "peer_ip": "198.51.100.90",
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

    res = client.post("/api/query", headers=admin_headers, json={"query": "show me open alerts"})
    assert res.status_code == 200
    body = res.json()
    assert body["template"] == "open_alerts"
    assert body["confidence"] == "high"
    assert any("VPN" in r["label"] for r in body["results"])


def test_query_network_burst_template(client: TestClient, admin_headers: dict[str, str]):
    res = client.post("/api/query", headers=admin_headers, json={"query": "network burst in last hour"})
    assert res.status_code == 200
    body = res.json()
    assert body["template"] == "network_bursts"
    assert body["results"] == []


def test_query_failed_logons_template(client: TestClient, admin_headers: dict[str, str]):
    units = client.get("/api/units", headers=admin_headers).json()
    token = _register_agent(client, admin_headers, "WIN-Q-AUTH-001", units[0])
    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": token},
        json={
            "agent_id": "WIN-Q-AUTH-001",
            "unit_id": units[0]["id"],
            "events": [
                {
                    "source": "windows",
                    "data": {
                        "event_id": 4625,
                        "computer": "Q-PROBE",
                        "time_created": "2026-01-05T09:12:00Z",
                        "message": "An account failed to log on.",
                        "data": {
                            "subject_user_name": "-",
                            "target_user_name": "rpatil",
                            "target_domain_name": "QUNIT",
                            "ip_address": "203.0.113.50",
                            "logon_type": "3",
                        },
                    },
                }
            ],
        },
    )
    assert ing.json().get("accepted") == 1

    res = client.post("/api/query", headers=admin_headers, json={"query": "failed logons by rpatil"})
    body = res.json()
    assert body["template"] == "failed_logons"
    assert body["confidence"] == "high"
    assert any("rpatil" in r["label"] for r in body["results"])


def test_query_graph_path_hint(client: TestClient, admin_headers: dict[str, str]):
    res = client.post("/api/query", headers=admin_headers, json={"query": 'path between "Imran Qureshi" and "Sukhna Lake"'})
    body = res.json()
    assert body["template"] == "graph_path"
    assert any("Imran Qureshi" in r["label"] for r in body["results"])


class _FakeLLMSettings:
    QUERY_LLM_ENABLED = True
    QUERY_LLM_API_KEY = "sk-fake-0123456789abcdef"
    QUERY_LLM_BASE_URL = "https://llm.invalid/v1"
    QUERY_LLM_MODEL = "test-model"


def test_query_llm_off_by_default(client: TestClient, admin_headers: dict[str, str]):
    res = client.post("/api/query", headers=admin_headers, json={"query": "open alerts"})
    assert res.status_code == 200
    assert "narrative" not in res.json()


def test_query_llm_grounded_narrative_when_enabled(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    import app.services.query_llm as llm_mod

    calls: dict = {}
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _FakeLLMSettings())
    monkeypatch.setattr(
        llm_mod,
        "_chat_completion",
        lambda url, key, payload: calls.update(url=url, key=key, payload=payload)
        or "Three open alerts are pending; the highest risk is the VPN misconfiguration.",
    )

    res = client.post("/api/query", headers=admin_headers, json={"query": "open alerts"})
    body = res.json()
    assert body["template"] == "open_alerts"
    assert "narrative" in body
    assert "highest risk is the VPN" in body["narrative"]
    assert calls["url"] == "https://llm.invalid/v1"
    assert calls["key"] == "sk-fake-0123456789abcdef"
    roles = {m["role"] for m in calls["payload"]["messages"]}
    assert roles == {"system", "user"}
    assert '"user_question": "open alerts"' in calls["payload"]["messages"][1]["content"]


def test_query_llm_degrades_on_failure(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    import app.services.query_llm as llm_mod

    monkeypatch.setattr(llm_mod, "get_settings", lambda: _FakeLLMSettings())
    monkeypatch.setattr(llm_mod, "_chat_completion", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))

    res = client.post("/api/query", headers=admin_headers, json={"query": "open alerts"})
    body = res.json()
    assert body["template"] == "open_alerts"
    assert "narrative" not in body