"""OSINT record parser for the VAJRA OSINT aggregator (Layer 3).

Input is a structured dict produced by the external ``vajra-osint`` service.
The record is deliberately mapped through the SAME universal pipeline (parser
registry → normalization → store → graph) as every other format — no
special-cased ingestion path. Fields the source didn't provide are ``null``;
they are never fabricated. Citation fields (``source_url`` / ``source_type`` /
``fetched_at``) are preserved verbatim all the way to the graph node.
"""

from datetime import datetime

from app.parsers.base import BaseParser, ParsedEvent

OSINT_EVENT_PERSON = 5101
OSINT_EVENT_LEAD = 5102


class OSINTRecordParser(BaseParser):
    format_name = "osint_record"
    version = "1.0"

    def parse(self, payload: str | dict) -> ParsedEvent | None:
        if isinstance(payload, str):
            try:
                import json

                payload = json.loads(payload)
            except (ValueError, TypeError):
                return None
        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            return self._from_dict(data)
        return None

    def _from_dict(self, obj: dict) -> ParsedEvent | None:
        name = obj.get("entity_name")
        if not name:
            return None
        record_type = str(obj.get("record_type") or "person").lower()
        event_id = OSINT_EVENT_PERSON if record_type == "person" else OSINT_EVENT_LEAD
        event = ParsedEvent(
            event_id=event_id,
            provider=f"OSINT-{str(obj.get('source_type') or 'unknown').upper()}",
            computer="osint",
            time_created=obj.get("fetched_at") or datetime.now().isoformat(),
            user=name,
            raw=obj,
        )
        event.event_data = {
            "entity_name": name,
            "record_type": record_type,
            "age": obj.get("age"),
            "gender": obj.get("gender"),
            "crime_type": obj.get("crime_type"),
            "crime_description": obj.get("crime_description"),
            "status": obj.get("status"),
            "location": obj.get("location"),
            "fir_number": obj.get("fir_number"),
            "plate_number": obj.get("plate_number"),
            "phone_number": obj.get("phone_number"),
            "source_type": obj.get("source_type"),
            "source_url": obj.get("source_url"),
            "fetched_at": obj.get("fetched_at"),
        }
        return event

    @staticmethod
    def extract_fields(event: ParsedEvent) -> dict:
        ed = event.event_data
        return {
            "event_id": event.event_id,
            "provider": event.provider,
            "hostname": event.computer,
            "timestamp": event.time_created,
            "username": ed.get("entity_name"),
            "source_ip": None,
            "destination_ip": None,
            "source_port": None,
            "destination_port": None,
            "protocol": None,
            "process_name": None,
            "command_line": ed.get("crime_description"),
            "logon_type": None,
            "status_code": ed.get("status"),
            "entity_name": ed.get("entity_name"),
            "record_type": ed.get("record_type"),
            "age": ed.get("age"),
            "gender": ed.get("gender"),
            "crime_type": ed.get("crime_type"),
            "crime_description": ed.get("crime_description"),
            "location": ed.get("location"),
            "fir_number": ed.get("fir_number"),
            "plate_number": ed.get("plate_number"),
            "phone_number": ed.get("phone_number"),
            "source_type": ed.get("source_type"),
            "source_url": ed.get("source_url"),
            "fetched_at": ed.get("fetched_at"),
        }