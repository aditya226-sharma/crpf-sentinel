"""Normalization engine: converts parser output into the common event schema.

The engine dispatches by ``format_name``:

1. Pull the format-specific ``extract_fields`` implementation via a registry
   (one per registered parser — a Syslog event and a Windows event normalize
   through the same function),
2. classify through the per-format YAML catalog (``app/config/formats/*.yaml``),
3. emit one common dict that feeds the relational store, the detection engine,
   risk scoring and the live stream.

Adding a new source = add its YAML + parser; the engine itself never changes.
"""

import ipaddress
from datetime import datetime, timezone
from typing import Any, Callable

from app.config.format_config import classify
from app.normalization.extractors import EXTRACTORS
from app.parsers.base import ParsedEvent

PRIVILEGED_USERS = {
    "administrator",
    "admin",
    "root",
    "system",
    "domain\\admin",
    "krbtgt",
    "nt authority\\system",
}

BLACKHOLE_IPS = {"127.0.0.1", "::1", "-", "", "0.0.0.0"}
PRIVATE_RANGES = ["10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.", "192.168."]


def _clean_ip(value: Any) -> str | None:
    if not value:
        return None
    ip = str(value).strip().lower()
    if ip in BLACKHOLE_IPS or ip.startswith("%"):
        return None
    if ip.startswith("fe80:"):
        return None
    try:
        return str(ipaddress.ip_address(ip.split("%")[0]))
    except ValueError:
        return ip[:45]


def _clean_username(value: Any) -> str | None:
    if not value:
        return None
    username = str(value).strip().lower()
    if username in {"-", "anonymous logon", "n\\a", "none", "null"}:
        return None
    return username


def parse_timestamp(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def normalize_event(
    parsed: ParsedEvent,
    unit_id: str | None,
    agent_id: str | None,
    parser_version: str = "1.0",
    format_name: str = "windows",
) -> dict[str, Any] | None:
    if parsed.event_id is None:
        return None

    extract: Callable[[ParsedEvent], dict] = EXTRACTORS.get(
        format_name, EXTRACTORS["windows"]
    )
    fields = extract(parsed)
    category, action, severity = classify(format_name, parsed.event_id)

    username = _clean_username(fields.get("username"))
    source_ip = _clean_ip(fields.get("source_ip"))
    destination_ip = _clean_ip(fields.get("destination_ip"))
    timestamp = parse_timestamp(fields.get("timestamp"))

    if format_name == "windows":
        severity = _windows_severity_override(parsed.event_id, fields, severity)

    extra: dict[str, Any] = {
        "format": format_name,
        "protocol": fields.get("protocol"),
        "source_port": fields.get("source_port"),
        "destination_port": fields.get("destination_port"),
    }

    if format_name == "netflow":
        extra.update(
            {
                "packets": fields.get("packets"),
                "bytes": fields.get("bytes"),
            }
        )
    if format_name == "ipsec":
        extra.update(
            {
                "tunnel_name": fields.get("tunnel_name"),
                "dh_group": fields.get("dh_group"),
                "pfs": fields.get("pfs"),
                "cipher": fields.get("cipher"),
                "integrity": fields.get("integrity"),
            }
        )
    if format_name == "syslog":
        extra.update(
            {
                "message": fields.get("message"),
                "cef_severity": fields.get("cef_severity"),
            }
        )
    if format_name == "case_record":
        extra.update(
            {
                "case_id": fields.get("case_id"),
                "record_type": fields.get("record_type"),
                "persons": fields.get("persons") or [],
                "phones": fields.get("phones") or [],
                "addresses": fields.get("addresses") or [],
                "vehicles": fields.get("vehicles") or [],
                "accounts": fields.get("accounts") or [],
            }
        )
    if format_name == "osint_record":
        extra.update(
            {
                "entity_name": fields.get("entity_name"),
                "record_type": fields.get("record_type"),
                "age": fields.get("age"),
                "gender": fields.get("gender"),
                "crime_type": fields.get("crime_type"),
                "crime_description": fields.get("crime_description"),
                "status": fields.get("status_code"),
                "location": fields.get("location"),
                "fir_number": fields.get("fir_number"),
                "plate_number": fields.get("plate_number"),
                "phone_number": fields.get("phone_number"),
                "source_type": fields.get("source_type"),
                "source_url": fields.get("source_url"),
                "fetched_at": fields.get("fetched_at"),
            }
        )

    return {
        "timestamp": timestamp or datetime.now(timezone.utc),
        "unit_id": unit_id,
        "agent_id": agent_id,
        "hostname": fields.get("hostname") or None,
        "event_id": parsed.event_id,
        "provider": parsed.provider or None,
        "category": category,
        "action": action,
        "username": username,
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "process_name": fields.get("process_name") or None,
        "command_line": fields.get("command_line") or None,
        "logon_type": fields.get("logon_type") or None,
        "status_code": fields.get("status_code") or None,
        "severity": severity,
        "parser_version": parser_version,
        "format_name": format_name,
        "is_suspicious": False,
        "extra": extra,
    }


def _windows_severity_override(event_id: int, fields: dict, default: str) -> str:
    """Windows-specific severity refinements that depend on event content."""
    if event_id in (4672,):
        username = _clean_username(fields.get("username"))
        privileged = username and username.lower() in PRIVILEGED_USERS
        return "high" if privileged else "medium"
    if event_id == 4688:
        return _process_creation_severity(fields.get("command_line"))
    return default


def _process_creation_severity(command_line: str | None) -> str:
    """Process creation is informational unless a suspicious pattern matches."""
    if not command_line:
        return "low"
    lowered = command_line.lower()
    indicators = [
        "-enc", "-encodedcommand", "-nop", "-windowstyle hidden",
        "invoke-webrequest", "iwr", "downloadstring", "net.webclient",
        "frombase64string", "iisreset", "wscript", "cscript",
    ]
    if any(ind in lowered for ind in indicators):
        return "medium"
    return "low"


def is_public_ip(ip: str | None) -> bool:
    if not ip:
        return False
    return not any(ip.startswith(p) for p in PRIVATE_RANGES)


def is_privileged_user(username: str | None) -> bool:
    if not username:
        return False
    return username.lower() in PRIVILEGED_USERS or username.lower().endswith("\\administrator")