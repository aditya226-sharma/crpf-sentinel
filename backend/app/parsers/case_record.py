"""Synthetic case-record parser (FIR / CDR / financial transaction).

Input is a structured dict — ALWAYS derived from synthetic demo data, never
from real case files. Shape::

    {
      "case_id": "FIR-2026-0042",
      "record_type": "fir" | "cdr" | "transaction",
      "date": "2026-01-15T08:30:00Z",
      "officer": "Insp. A. Kumar",
      "unit_code": "UNIT-07",
      "summary/text": "Free-text body used for entity extraction",
      "persons": ["Ravi Gupta", "Sneha Menon"],
      "phones": ["+91-9812345678"],
      "addresses": ["14 Mahatma Gandhi Road, Delhi"],
      "vehicles": ["DL-01-AB-1234"],
      "accounts": ["IBAN-XXXX-1142"],
      "amount": 420000, "currency": "INR",
      "counterparty": "..."
    }
"""

from datetime import datetime

from app.parsers.base import BaseParser, ParsedEvent


class CaseRecordParser(BaseParser):
    format_name = "case_record"
    version = "1.0"

    TYPE_EVENT_ID = {
        "fir": 5001,
        "transaction": 5002,
        "cdr": 5003,
    }

    def parse(self, payload: str | dict) -> ParsedEvent | None:
        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            return self._from_dict(data)
        return None

    def _from_dict(self, obj: dict) -> ParsedEvent | None:
        if not obj.get("case_id") and not obj.get("record_type"):
            return None
        record_type = str(obj.get("record_type") or "fir").lower()
        event = ParsedEvent(
            event_id=self.TYPE_EVENT_ID.get(record_type, 5001),
            provider=f"CaseRecord-{record_type.upper()}",
            computer=obj.get("unit_code") or obj.get("unit"),
            time_created=obj.get("date") or obj.get("time_created") or datetime.now().isoformat(),
            user=obj.get("officer"),
            raw=obj,
        )
        event.event_data = {
            "case_id": obj.get("case_id"),
            "record_type": record_type,
            "text": obj.get("summary") or obj.get("text") or obj.get("narrative") or "",
            "persons": obj.get("persons", []),
            "phones": obj.get("phones", []),
            "addresses": obj.get("addresses", []),
            "vehicles": obj.get("vehicles", []),
            "accounts": obj.get("accounts", []),
            "amount": obj.get("amount"),
            "currency": obj.get("currency"),
            "counterparty": obj.get("counterparty"),
        }
        return event

    # -- field extraction for the normalization engine -------------------
    @staticmethod
    def extract_fields(event: ParsedEvent) -> dict:
        ed = event.event_data
        return {
            "event_id": event.event_id,
            "provider": event.provider,
            "hostname": event.computer,
            "timestamp": event.time_created,
            "username": event.user,
            "source_ip": None,
            "destination_ip": None,
            "source_port": None,
            "destination_port": None,
            "protocol": None,
            "process_name": None,
            "command_line": ed.get("text"),
            "logon_type": None,
            "status_code": ed.get("record_type"),
            "case_id": ed.get("case_id"),
            "record_type": ed.get("record_type"),
            "persons": ed.get("persons"),
            "phones": ed.get("phones"),
            "addresses": ed.get("addresses"),
            "vehicles": ed.get("vehicles"),
            "accounts": ed.get("accounts"),
        }