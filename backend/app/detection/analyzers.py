"""Analysis detectors dispatcher.

Runs format-specific analysis modules (traffic anomaly for ``netflow``, VPN
audit for ``ipsec``) inside the existing ingest path. Each detector writes to
the shared ``Alert`` model via ``detection/alert_writer`` so its output
surfaces on the existing Alerts/Incidents pages automatically.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.detection.traffic_anomaly import detect_flow_burst
from app.detection.vpn_audit import audit_ipsec_tunnel
from app.models.flow import Flow
from app.models.vpn_tunnel import VpnTunnel


def run_analysis_detectors(
    db: Session,
    event: dict[str, Any],
    event_row_id: int | None,
) -> tuple[list[object], list[str]]:
    """Run the detectors matching this event's format and persist its row."""
    format_name = event.get("format_name")
    alerts: list[object] = []
    matched: list[str] = []

    if format_name == "netflow":
        _record_flow(db, event)
        alerts = detect_flow_burst(db, event, event_row_id)
    elif format_name == "ipsec":
        _upsert_tunnel(db, event)
        alerts = audit_ipsec_tunnel(db, event, event_row_id)

    matched = [a.rule.rule_id if hasattr(a, "rule") else (getattr(a, "rule_id", None) or "") for a in alerts]
    return alerts, [m for m in matched if m]


def _record_flow(db: Session, event: dict[str, Any]) -> None:
    extra = event.get("extra") or {}
    source = event.get("source_ip")
    dest = event.get("destination_ip")
    if not source or not dest:
        return
    db.add(
        Flow(
            unit_id=event.get("unit_id"),
            agent_id=event.get("agent_id"),
            hostname=event.get("hostname"),
            source_ip=source,
            destination_ip=dest,
            source_port=extra.get("source_port"),
            destination_port=extra.get("destination_port"),
            protocol=extra.get("protocol"),
            packets=extra.get("packets") or 0,
            bytes=extra.get("bytes") or 0,
            timestamp=event.get("timestamp"),
            simulated=event.get("simulated", False),
        )
    )
    db.flush()


def _upsert_tunnel(db: Session, event: dict[str, Any]) -> None:
    from datetime import datetime, timezone

    extra = event.get("extra") or {}
    name = extra.get("tunnel_name") or ""
    peer = event.get("destination_ip") or event.get("source_ip")
    if not name and not peer:
        return
    tunnel = (
        db.query(VpnTunnel)
        .filter(VpnTunnel.tunnel_name == name, VpnTunnel.peer_ip == (peer or ""))
        .first()
    )
    now = datetime.now(timezone.utc)
    if tunnel is None:
        tunnel = VpnTunnel(
            unit_id=event.get("unit_id"),
            agent_id=event.get("agent_id"),
            tunnel_name=name,
            peer_ip=peer or "",
            local_ip=event.get("source_ip"),
            dh_group=str(extra.get("dh_group") or ""),
            pfs=extra.get("pfs"),
            cipher=(extra.get("cipher") or ""),
            integrity=(extra.get("integrity") or ""),
            ike_version=extra.get("destination_port") or extra.get("ike_version"),
            last_seen=now,
            simulated=event.get("simulated", False),
        )
        db.add(tunnel)
    else:
        tunnel.last_seen = now
        tunnel.dh_group = str(extra.get("dh_group") or tunnel.dh_group)
        tunnel.pfs = extra.get("pfs")
        tunnel.cipher = extra.get("cipher") or tunnel.cipher
        tunnel.integrity = extra.get("integrity") or tunnel.integrity
        db.add(tunnel)
    db.flush()