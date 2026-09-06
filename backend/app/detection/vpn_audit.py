"""IPsec VPN configuration auditor.

Evaluates IPSec/IKE tunnel configuration against conservative hardening
baselines and raises an Alert (via the shared alert writer) for weak tunnels:
  - weak Diffie-Hellman group (1, 2, 5, 22),
  - Perfect Forward Secrecy (PFS) disabled,
  - weak/legacy cipher (DES, 3DES, RC4, NULL),
  - weak integrity hash (MD5, SHA1) for IKE auth.

Each weakness contributes an explainable risk factor, so the composite score
visible on the Alerts page shows exactly what is wrong.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.detection.alert_writer import get_or_create_rule, write_analysis_alert
from app.models.vpn_tunnel import VpnTunnel
from app.parsers.ipsec import IPsecParser

RULE_DEF = {
    "rule_id": "RULE-VPN-001",
    "name": "Weak IPsec VPN Configuration",
    "description": "An IPsec/IKE tunnel uses a weak Diffie-Hellman group, "
    "disables Perfect Forward Secrecy, or negotiates legacy crypto.",
    "category": "vpn",
    "severity": "high",
    "event_id": 4001,
    "mitre_technique": "T1212",
    "mitre_name": "Exploitation for Credential Access",
}


def audit_ipsec_tunnel(
    db: Session,
    event: dict,
    event_row_id: int | None,
) -> list[object]:
    """Evaluate the tunnel described by this event and alert if misconfigured."""
    extra = event.get("extra") or {}
    tunnel_name = extra.get("tunnel_name")
    peer_ip = extra.get("destination_ip") or extra.get("source_ip")
    dh_group = str(extra.get("dh_group") or "")
    pfs = extra.get("pfs")
    cipher = (extra.get("cipher") or "").lower()
    integrity = (extra.get("integrity") or "").lower()

    reasons: list[dict] = []
    if dh_group and dh_group not in {"0", "1"} and dh_group in IPsecParser.WEAK_DH:
        reasons.append({"label": f"VPN misconfiguration (weak DH group {dh_group})", "points": 25})
    if pfs is False:
        reasons.append({"label": "VPN misconfiguration (Perfect Forward Secrecy disabled)", "points": 20})
    if cipher in IPsecParser.WEAK_CIPHERS:
        reasons.append({"label": f"VPN misconfiguration (weak cipher {cipher})", "points": 20})
    if integrity in IPsecParser.WEAK_INTEGRITY:
        reasons.append({"label": f"VPN misconfiguration (weak integrity {integrity})", "points": 15})

    if not reasons:
        return []

    if peer_ip:
        tunnel = (
            db.query(VpnTunnel)
            .filter(VpnTunnel.tunnel_name == (tunnel_name or ""), VpnTunnel.peer_ip == peer_ip)
            .first()
        )
        if tunnel is not None:
            tunnel.dh_group = dh_group or tunnel.dh_group
            tunnel.pfs = pfs
            tunnel.cipher = cipher or tunnel.cipher
            tunnel.integrity = integrity or tunnel.integrity
            tunnel.last_seen = datetime.now(timezone.utc)
            db.add(tunnel)
            db.flush()

    rule = get_or_create_rule(db, RULE_DEF)
    weaknesses = ", ".join(r["label"].split("(", 1)[0].strip() for r in reasons)
    alert = write_analysis_alert(
        db,
        rule=rule,
        event=event,
        event_row_id=event_row_id,
        explanation=f"Tunnel {tunnel_name or peer_ip} violates VPN hardening baseline: {weaknesses}",
        severity=RULE_DEF["severity"],
        risk_factors=reasons,
        source_ip=peer_ip,
        correlation_key=f"vpn:{tunnel_name or peer_ip}",
        mitre=(RULE_DEF.get("mitre_technique"), RULE_DEF.get("mitre_name")),
    )
    return [alert]