"""Phase B — Log Intelligence detection modules.

Proves the two new detectors write into the EXISTING Alert model (no parallel
alerting system), that flows/tunnels are persisted, and that risk scoring
reflects the two new additive factors with an explainable breakdown.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.detection.traffic_anomaly import detect_flow_burst
from app.detection.vpn_audit import audit_ipsec_tunnel
from app.models.alert import Alert
from app.models.flow import Flow
from app.models.unit import Unit
from app.models.vpn_tunnel import VpnTunnel
from app.services.risk import compute_risk_score


def _first_unit_id() -> str:
    db = SessionLocal()
    try:
        unit = db.query(Unit).first()
        return unit.id if unit else "u-test"
    finally:
        db.close()


def test_models_registered():
    from app.database.base import Base

    tables = set(Base.metadata.tables.keys())
    assert "flows" in tables
    assert "vpn_tunnels" in tables


def test_traffic_anomaly_rate_threshold_creates_alert():
    db = SessionLocal()
    unit_id = _first_unit_id()
    src = "203.0.113.77"
    now = datetime.now(timezone.utc)
    try:
        db.query(Flow).delete()
        db.flush()
        for i in range(101):
            db.add(
                Flow(
                    unit_id=unit_id,
                    source_ip=src,
                    destination_ip=f"10.0.0.{i % 200}",
                    destination_port=(i % 60000) + 1,
                    protocol="tcp",
                    timestamp=now - timedelta(seconds=i % 30),
                )
            )
        db.commit()

        event = {
            "unit_id": unit_id,
            "agent_id": None,
            "hostname": None,
            "source_ip": src,
            "destination_ip": "10.0.0.9",
            "event_id": 3001,
            "timestamp": now,
        }
        alerts = detect_flow_burst(db, event, event_row_id=None)
        assert len(alerts) == 1
        from app.models.rule import DetectionRule

        rule = db.query(DetectionRule).filter(DetectionRule.rule_id == "RULE-NET-001").first()
        alert = db.query(Alert).filter(Alert.rule_id == rule.id).order_by(Alert.created_at.desc()).first()
        assert alert is not None
        assert any("traffic anomaly" in f["label"].lower() for f in (alert.risk_factors or []))
    finally:
        db.close()


def test_vpn_audit_weak_tunnel_creates_alert_and_row():
    db = SessionLocal()
    unit_id = _first_unit_id()
    try:
        event = {
            "format_name": "ipsec",
            "unit_id": unit_id,
            "agent_id": None,
            "hostname": None,
            "source_ip": "10.0.0.1",
            "destination_ip": "203.0.113.44",
            "event_id": 4001,
            "severity": "high",
            "timestamp": datetime.now(timezone.utc),
            "extra": {
                "tunnel_name": "TUNNEL-DELHI",
                "dh_group": "2",
                "pfs": False,
                "cipher": "3des-cbc",
                "integrity": "md5",
            },
        }
        from app.detection.analyzers import run_analysis_detectors

        alerts, _ = run_analysis_detectors(db, event, None)
        assert len(alerts) == 1
        from app.models.rule import DetectionRule

        rule = db.query(DetectionRule).filter(DetectionRule.rule_id == "RULE-VPN-001").first()
        alert = db.query(Alert).filter(Alert.rule_id == rule.id).order_by(Alert.created_at.desc()).first()
        assert alert is not None
        labels = {f["label"] for f in (alert.risk_factors or [])}
        assert any("DH group" in l or "DH group 2" in l for l in labels)
        assert any("Forward Secrecy" in l for l in labels)
        assert any("cipher" in l for l in labels)
        assert db.query(VpnTunnel).filter(VpnTunnel.tunnel_name == "TUNNEL-DELHI").count() == 1
    finally:
        db.close()


def test_risk_scoring_reflects_new_factors():
    score, reasons = compute_risk_score(
        severity="high",
        event_count=1,
        traffic_anomaly_score=25,
        vpn_misconfig_score=20,
    )
    labels = [r["label"] for r in reasons]
    assert "traffic anomaly detected" in labels
    assert "VPN misconfiguration" in labels
    assert score >= 70
    assert len([r for r in reasons if r["points"] > 0]) >= 3  # base + anomaly + vpn


def test_weak_ipsec_ingest_surfaces_on_alerts_page(
    client: TestClient, admin_headers: dict[str, str]
):
    units = client.get("/api/units", headers=admin_headers).json()
    reg = client.post(
        "/api/agents",
        headers=admin_headers,
        json={
            "agent_id": "WIN-CI-VPN-001",
            "unit_id": units[0]["id"],
            "hostname": "VPN-GW",
            "simulated": True,
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["api_token"]

    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": token},
        json={
            "agent_id": "WIN-CI-VPN-001",
            "unit_id": units[0]["id"],
            "events": [
                {
                    "source": "ipsec",
                    "data": {
                        "tunnel_name": "TUNNEL-API-TEST",
                        "peer_ip": "198.51.100.21",
                        "local_ip": "10.0.0.1",
                        "dh_group": "5",
                        "pfs": False,
                        "cipher": "des-cbc",
                        "integrity": "sha1",
                    },
                }
            ],
        },
    )
    assert ing.status_code == 200, ing.text
    assert ing.json()["accepted"] == 1

    alerts = client.get("/api/alerts?q=VPN&page_size=10", headers=admin_headers).json()
    found = [a for a in alerts["items"] if a.get("rule_name") == "RULE-VPN-001"]
    assert found, "VPN alert must appear on the existing Alerts endpoint with zero frontend changes"
    assert any("VPN" in f["label"] for f in (found[0].get("risk_factors") or []))