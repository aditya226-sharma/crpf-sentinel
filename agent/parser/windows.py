"""Normalization for Windows Event Log records.

Transforms raw records (XML, WMI dicts, or JSON) into the compact
``IngestItem`` shape expected by the CyberRakshak backend.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# Security channel events of highest interest
SECURITY_EVENTS = {
    4624: "Logon Success",
    4625: "Logon Failure",
    4634: "Logoff",
    4648: "Explicit Credential Use",
    4672: "Special Privileges Assigned",
    4688: "Process Created",
    4720: "User Account Created",
    4728: "Member Added (Privileged Group)",
    4732: "Member Added (Local Group)",
    1102: "Audit Log Cleared",
}
SYSTEM_EVENTS = {
    7045: "Service Installed",
    7036: "Service Started/Stopped",
}
APPLICATION_EVENTS: dict[int, str] = {}


def parse_time(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(text[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _first(values: dict, *keys):
    for key in keys:
        value = values.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize(raw: dict) -> dict:
    """Return an IngestItem-compatible dict from a raw collector record."""
    data = dict(raw.get("data") or {})
    user = (
        raw.get("user")
        or _first(data, "TargetUserName", "SubjectUserName", "SecurityUserId", "AccountName")
    )
    provider = raw.get("provider") or _first(data, "ProviderName", "Channel")

    item = {
        "event_id": int(raw.get("event_id") or 0) or None,
        "provider": provider,
        "computer": raw.get("computer") or _first(data, "Computer", "MachineName"),
        "time_created": parse_time(raw.get("time_created") or _first(data, "TimeCreated", "TimeGenerated")),
        "user": str(user) if user is not None else None,
        "data": data,
        "source": raw.get("source") or "windows",
    }
    raw_xml = raw.get("raw_xml")
    if raw_xml:
        item["raw_xml"] = raw_xml
    return {k: v for k, v in item.items() if v not in (None, "", {})}


def extract_raw_xml(record: dict) -> str | None:
    """Pull a raw XML string out of a record if present."""
    xml = record.get("raw_xml")
    if xml:
        return xml
    rendered = record.get("rendered")
    if rendered:
        return rendered
    return None


def interesting(event_id: int) -> bool:
    return event_id in SECURITY_EVENTS or event_id in SYSTEM_EVENTS


_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def extract_ips(data: dict) -> list[str]:
    """Best-effort extraction of IPv4 addresses from event data fields."""
    ips: list[str] = []
    for key in ("IpAddress", "SourceIp", "ClientAddress", "RemoteHost", "Address", "WorkstationName"):
        value = data.get(key)
        if value and _IP_RE.match(str(value)):
            ips.append(str(value))
    return list(dict.fromkeys(ips))
