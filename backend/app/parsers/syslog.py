"""Syslog / CEF parser.

Understands three input shapes:
  - CEF (:0|Vendor|Product|Version|SignatureID|Name|Severity|Extension) —
    the format produced by most Windows-to-syslog forwarders (e.g. NPS/IIS).
  - RFC 3164 legacy syslog: ``<PRI>MMM dd hh:mm:ss host app[pid]: message``
  - RFC 5424 syslog: ``<PRI>1 timestamp host app procid msgid - message``

The parser emits an event-id in a small numeric namespace so the common
normalization schema (which keys on an integer event_id) is satisfied for
every format that flows through the pipeline.
"""

import hashlib
import re
from datetime import datetime

from app.parsers.base import BaseParser, ParsedEvent

_SYSLOG_RE = re.compile(
    r"^<(\d{1,3})>"
    r"(?:\d+\s+)?"
    r"([A-Za-z]{3}\s+\d{1,2}\s+\d\d:\d\d:\d\d"
    r"|(?:\d{4}-\d{2}-\d{2}T?\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?))"
    r"\s+([^\s]+)"
    r"(?:\s+([\w.\-]+)(?:\[(\d+)\])?)?"
    r"\s*(?::\s*)?(.*)$"
)

_CEF_PRIORITY = {
    "0": "emergency", "1": "alert", "2": "critical", "3": "error",
    "4": "warning", "5": "notice", "6": "informational", "7": "debug",
}
_CEF_SEVERITY = {
    "0": "critical", "1": "critical", "2": "high", "3": "high",
    "4": "medium", "5": "medium", "6": "low", "7": "informational",
    "8": "informational", "9": "informational", "10": "informational",
}


class SyslogParser(BaseParser):
    format_name = "syslog"
    version = "1.0"

    def parse(self, payload: str | dict) -> ParsedEvent | None:
        if isinstance(payload, dict):
            raw = payload.get("raw") or payload.get("message") or payload.get("raw_json")
            if not raw:
                # A structured dict with explicit syslog fields.
                return self._from_dict(payload)
        elif isinstance(payload, str):
            raw = payload
        else:
            return None
        if not raw:
            return None
        raw = str(raw).strip()
        if raw.startswith("CEF:"):
            return self._parse_cef(raw)
        return self._parse_legacy(raw)

    # ── CEF ────────────────────────────────────────────────────────────
    def _parse_cef(self, raw: str) -> ParsedEvent | None:
        # CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|[Extension]
        head, _, ext = raw.partition("|")
        if head != "CEF:0":
            return None
        parts = raw.split("|")
        if len(parts) < 8:
            return None
        _, vendor, product, _version, signature, msg, sev = parts[1:8]
        ext_text = "|".join(parts[8:]) if len(parts) > 8 else (ext if ext.startswith("=") else "")

        event = ParsedEvent(
            event_id=self._signature_id(signature, sev),
            provider=f"{product or vendor or 'Syslog'}",
            computer=None,
            user=None,
            time_created=datetime.now().isoformat(),
            raw=raw,
        )
        ext_fields = dict(re.findall(r"([A-Za-z0-9_]+)=([^=]*)", ext_text))
        event.event_data = {
            "cef_vendor": vendor,
            "cef_product": product,
            "signature_id": signature,
            "cef_severity": sev,
            "name": msg,
            "username": ext_fields.get("suser") or ext_fields.get("duser"),
            "source_ip": ext_fields.get("src") or ext_fields.get("srcip"),
            "destination_ip": ext_fields.get("dst") or ext_fields.get("dstip"),
            "source_port": ext_fields.get("spt"),
            "destination_port": ext_fields.get("dpt"),
            "protocol": ext_fields.get("proto"),
            "app": ext_fields.get("app"),
            "category_device": ext_fields.get("cs1") or ext_fields.get("cn1"),
        }
        # syslog-style header may precede CEF body
        return event

    # ── RFC 3164 / 5424 ────────────────────────────────────────────────
    def _parse_legacy(self, raw: str) -> ParsedEvent | None:
        match = _SYSLOG_RE.match(raw)
        pri = int(match.group(1)) if match else None
        if match:
            timestamp, host, app, pid = (match.group(2), match.group(3), match.group(4), match.group(5))
            message = match.group(6) or ""
        else:
            timestamp, host, app, pid, message = None, None, None, None, raw
        if pri is not None:
            severity_code = pri & 0x07
            facility = (pri & 0xF8) >> 3
            severity = _PRI_SEVERITY.get(severity_code, "informational")
        else:
            facility, severity = None, "informational"

        event = ParsedEvent(
            event_id=self._legacy_event_id(message, severity),
            provider=app,
            computer=host,
            user=None,
            time_created=timestamp,
            raw=raw,
        )
        event.event_data = {
            "facility": facility,
            "severity": severity,
            "pid": pid,
            "message": message,
        }
        event.user = self._find_user(message)
        event.event_data["source_ip"] = self._find_ip(message)
        return event

    # ── Structured dict ────────────────────────────────────────────────
    def _from_dict(self, obj: dict) -> ParsedEvent | None:
        event = ParsedEvent(
            event_id=self._signature_id(str(obj.get("signature_id") or obj.get("event_id") or ""), str(obj.get("severity") or "6")),
            provider=obj.get("app") or obj.get("provider"),
            computer=obj.get("host") or obj.get("computer"),
            user=obj.get("user"),
            time_created=obj.get("time_created") or obj.get("timestamp") or datetime.now().isoformat(),
            raw=None,
        )
        event.event_data = {k: v for k, v in obj.items() if k not in {"event_id", "provider", "computer", "time_created"}}
        return event

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _signature_id(signature: str, cef_sev: str) -> int | None:
        if signature.isdigit():
            return int(signature)
        digest = hashlib.md5(signature.encode()).hexdigest()
        return 4550 + (int(digest[:6], 16) % 50)

    @staticmethod
    def _legacy_event_id(message: str, severity: str) -> int:
        lowered = (message or "").lower()
        if any(k in lowered for k in ("refused", "failed", "invalid", "denied", "rejected", "unable")):
            return 4210
        if any(k in lowered for k in ("accepted", "success", "succeeded", "ok ")):
            if severity in ("critical", "high"):
                return 4211
            return 4211
        if any(k in lowered for k in ("drop", "block", "denied", "135", "22 ")):
            return 4551
        return 4550

    @staticmethod
    def _find_ip(text: str) -> str | None:
        match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text or "")
        return match.group(0) if match else None

    @staticmethod
    def _find_user(text: str) -> str | None:
        match = re.search(r"user[=:]\s*([^\s,;]+)", text or "", re.IGNORECASE)
        return match.group(1) if match else None

    # -- field extraction for the normalization engine -------------------
    @staticmethod
    def extract_fields(event: ParsedEvent) -> dict:
        ed = event.event_data
        return {
            "event_id": event.event_id,
            "provider": event.provider,
            "hostname": event.computer,
            "timestamp": event.time_created,
            "username": ed.get("username") or event.user,
            "source_ip": ed.get("source_ip"),
            "destination_ip": ed.get("destination_ip"),
            "source_port": ed.get("source_port"),
            "destination_port": ed.get("destination_port"),
            "protocol": ed.get("protocol"),
            "process_name": ed.get("app") or ed.get("cef_product"),
            "command_line": None,
            "logon_type": None,
            "status_code": ed.get("signature_id"),
            "message": ed.get("message"),
            "cef_severity": ed.get("cef_severity"),
            "severity": ed.get("severity"),
        }


_PRI_SEVERITY = {
    0: "critical",
    1: "critical",
    2: "critical",
    3: "high",
    4: "medium",
    5: "medium",
    6: "low",
    7: "informational",
}