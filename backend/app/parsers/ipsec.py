"""IPsec / IKE VPN parser.

Accepts a structured dict describing a tunnel negotiation result or an
IKE/ESP handshake capture record::

    {tunnel_name, peer_ip, local_ip, dh_group, pfs, cipher, integrity,
     ike_version, session_id, status, time_created}

Tunnels normalise to event_id 4001 (``vpn`` category) and are persisted as
``VpnTunnel`` rows so the VPN audit detector can evaluate configuration
weakness (weak DH group, missing PFS, weak cipher/integrity).
"""

from datetime import datetime

from app.parsers.base import BaseParser, ParsedEvent


class IPsecParser(BaseParser):
    format_name = "ipsec"
    version = "1.0"

    WEAK_DH = {"1", "2", "5", "22"}
    WEAK_CIPHERS = {"des", "3des", "rc4", "null", "des-cbc", "3des-cbc"}
    WEAK_INTEGRITY = {"md5", "sha1", "hmac-md5", "hmac-sha1"}

    def parse(self, payload: str | dict) -> ParsedEvent | None:
        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            return self._from_dict(data)
        if isinstance(payload, str):
            return self._from_text(payload)
        return None

    def _from_dict(self, obj: dict) -> ParsedEvent | None:
        if obj.get("tunnel_name") is None and obj.get("peer_ip") is None:
            return None
        event = ParsedEvent(
            event_id=4001,
            provider="IPsec",
            computer=obj.get("hostname") or obj.get("host"),
            time_created=obj.get("time_created") or obj.get("timestamp") or datetime.now().isoformat(),
            raw=obj,
        )
        event.event_data = {
            "tunnel_name": obj.get("tunnel_name") or obj.get("name"),
            "peer_ip": obj.get("peer_ip") or obj.get("peer"),
            "local_ip": obj.get("local_ip"),
            "dh_group": str(obj.get("dh_group") or obj.get("dhgroup") or ""),
            "pfs": bool(obj.get("pfs")) if obj.get("pfs") is not None else None,
            "cipher": str(obj.get("cipher") or "").lower(),
            "integrity": str(obj.get("integrity") or "").lower(),
            "ike_version": str(obj.get("ike_version") or obj.get("ike") or "1"),
            "session_id": obj.get("session_id"),
            "status": obj.get("status") or "active",
        }
        return event

    def _from_text(self, raw: str) -> ParsedEvent | None:
        if "enc=" not in raw and "cipher" not in raw and "Tunnel" not in raw:
            return None
        values = {k.lower(): v for k, v in self._kv(raw).items()}
        return self._from_dict(
            {
                "tunnel_name": values.get("tunnel") or values.get("name") or values.get("peer"),
                "peer_ip": values.get("peer") or values.get("peer_ip"),
                "local_ip": values.get("local"),
                "dh_group": values.get("dh") or values.get("dh_group"),
                "pfs": values.get("pfs"),
                "cipher": values.get("cipher") or values.get("enc"),
                "integrity": values.get("integrity") or values.get("integ") or values.get("hash"),
                "ike_version": values.get("ike") or values.get("ike_version"),
                "session_id": values.get("session_id"),
            }
        )

    @staticmethod
    def _kv(raw: str) -> dict:
        import re

        return dict(re.findall(r"([\w\-]+)=([^\s,;]+)", raw))

    # -- field extraction for the normalization engine -------------------
    @staticmethod
    def extract_fields(event: ParsedEvent) -> dict:
        ed = event.event_data
        return {
            "event_id": event.event_id,
            "provider": event.provider,
            "hostname": event.computer,
            "timestamp": event.time_created,
            "username": None,
            "source_ip": ed.get("local_ip") or ed.get("peer_ip"),
            "destination_ip": ed.get("peer_ip"),
            "source_port": None,
            "destination_port": ed.get("ike_version"),
            "protocol": "ipsec",
            "process_name": None,
            "command_line": None,
            "logon_type": None,
            "status_code": None,
            "tunnel_name": ed.get("tunnel_name"),
            "dh_group": ed.get("dh_group"),
            "pfs": ed.get("pfs"),
            "cipher": ed.get("cipher"),
            "integrity": ed.get("integrity"),
        }