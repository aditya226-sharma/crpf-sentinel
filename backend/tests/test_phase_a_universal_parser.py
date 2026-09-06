"""Phase A — universal pre-processing framework.

Proves the framework contract that SIH26156 is judged on:
  - a second parser (Syslog/CEF) conforms to BaseParser,
  - it's discoverable through ParserRegistry alongside the Windows parser,
  - normalization dispatches by format_name through one shared function,
  - classification lives in YAML (new mappings don't need Python changes),
  - a raw Syslog sample flows through /api/logs/ingest into the existing
    logs view with zero frontend changes.
"""

from fastapi.testclient import TestClient

from app.normalization.engine import normalize_event
from app.parsers import ParserRegistry
from app.parsers.base import ParsedEvent
from app.parsers.syslog import SyslogParser

SYSLOG_CEF = (
    "CEF:0|CyberRakshak|SSHD|1.0|SSH_LOGIN_FAILED|Failed publickey for root|7|"
    "src=203.0.113.9 spt=51022 suser=root dst=198.51.100.10 dpt=22"
)
SYSLOG_LEGACY = "<134>Jan 15 08:30:00 gw-01 sshd[1234]: Failed password for root from 203.0.113.9"


def _register_agent(client: TestClient, headers: dict[str, str]) -> dict:
    units = client.get("/api/units", headers=headers).json()
    reg = client.post(
        "/api/agents",
        headers=headers,
        json={
            "agent_id": "WIN-CI-SYSLOG-001",
            "unit_id": units[0]["id"],
            "hostname": "CISYSLOG",
            "simulated": True,
        },
    )
    assert reg.status_code == 201, reg.text
    return reg.json()


def test_syslog_parser_is_a_baseparser():
    parser = SyslogParser()
    parsed = parser.parse(SYSLOG_LEGACY)
    assert isinstance(parsed, ParsedEvent)
    assert parsed.event_id == 4210
    assert parsed.provider == "sshd"
    assert parsed.computer == "gw-01"
    assert parsed.event_data["message"].startswith("Failed password")


def test_registry_discovery_contains_all_formats():
    names = ParserRegistry.all()
    assert "windows" in names
    assert "syslog" in names
    assert "netflow" in names
    assert "ipsec" in names
    assert "case_record" in names


def test_normalization_dispatches_by_format_through_one_function():
    windows = ParsedEvent(
        event_id=4624,
        provider="Microsoft-Windows-Security-Auditing",
        computer="WIN-PC-1",
        time_created="2026-01-15T08:00:00Z",
        event_data={"TargetUserName": "alice", "IpAddress": "203.0.113.5"},
    )
    syslog = ParsedEvent(
        event_id=4210,
        provider="sshd",
        computer="gw-01",
        time_created="2026-01-15T08:30:00Z",
        event_data={"message": "Failed password", "source_ip": "203.0.113.9"},
    )

    win = normalize_event(windows, "u1", "a1", format_name="windows")
    sys = normalize_event(syslog, "u1", "a1", format_name="syslog")

    assert win is not None and sys is not None
    assert win["format_name"] == "windows"
    assert sys["format_name"] == "syslog"
    assert win["category"] == "authentication" and win["severity"] == "low"
    assert sys["category"] == "authentication" and sys["severity"] == "medium"
    assert set(["event_id", "category", "action", "severity", "hostname", "source_ip"]) <= set(sys.keys())


def test_classification_is_yaml_driven():
    from app.config.format_config import classify

    assert classify("windows", 7045) == ("service_installation", "service_installed", "high")
    assert classify("netflow", 3001) == ("network", "flow_observed", "informational")
    # Unknown codes fall back to per-format defaults.
    assert classify("syslog", 99999)[2] == "informational"


def test_syslog_ingest_appears_in_existing_logs(client: TestClient, admin_headers: dict[str, str]):
    registered = _register_agent(client, admin_headers)
    token = registered["api_token"]

    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": token},
        json={
            "agent_id": "WIN-CI-SYSLOG-001",
            "hostname": "CISYSLOG",
            "events": [
                {"source": "syslog", "raw_json": SYSLOG_CEF},
                {"source": "syslog", "raw_json": SYSLOG_LEGACY},
            ],
        },
    )
    assert ing.status_code == 200, ing.text
    body = ing.json()
    assert body["accepted"] == 2
    assert body["parsed"] == 2

    logs = client.get("/api/logs?page_size=20", headers=admin_headers).json()
    matches = [
        e for e in logs["items"]
        if e["provider"] in ("SSHD", "sshd") or (e.get("extra") or {}).get("format") == "syslog"
    ]
    assert any(e["event_id"] == 4210 for e in matches)
    assert all((e.get("extra") or {}).get("format") == "syslog" for e in matches)