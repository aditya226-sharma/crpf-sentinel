"""NetFlow v5/v9 / IPFIX flow parser.

Accepts a structured dict (as sent by a flow collector) or a CSV/TSV line:
``srcaddr,dstaddr,srcport,dstport,proto,packets,bytes,first,last``
with optionally prepended ``SrcIP SrcPrt DstIP DstPrt ...`` fields.

Flows normalise to event_id 3001 under the ``network`` category so they flow
through the same detection and risk pipeline as every other format.
"""

import csv
import io
import re
from datetime import datetime

from app.parsers.base import BaseParser, ParsedEvent


def _as_int(value) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class NetFlowParser(BaseParser):
    format_name = "netflow"
    version = "1.0"

    def parse(self, payload: str | dict) -> ParsedEvent | None:
        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            return self._from_dict(data)
        if isinstance(payload, str):
            return self._from_csv(payload) or self._from_dict(self._kv(payload))
        return None

    def _from_dict(self, obj: dict) -> ParsedEvent | None:
        if not isinstance(obj, dict):
            return None
        if not any(k in obj for k in ("srcaddr", "dstaddr", "src_address", "dst_address")):
            return None
        first = obj.get("first") or obj.get("flow_start")
        event = ParsedEvent(
            event_id=3001,
            provider="NetFlow",
            computer=obj.get("hostname") or obj.get("host") or obj.get("router"),
            time_created=self._ts(first),
            raw=obj,
        )
        event.event_data = {
            "source_ip": obj.get("srcaddr") or obj.get("src_address") or obj.get("src"),
            "destination_ip": obj.get("dstaddr") or obj.get("dst_address") or obj.get("dst"),
            "source_port": _as_int(obj.get("srcport") or obj.get("src_port") or obj.get("spt")),
            "destination_port": _as_int(obj.get("dstport") or obj.get("dst_port") or obj.get("dpt")),
            "protocol": str(obj.get("proto") or obj.get("protocol") or "0"),
            "packets": _as_int(obj.get("packets") or obj.get("pkts")),
            "bytes": _as_int(obj.get("bytes") or obj.get("octets")),
            "tcp_flags": obj.get("tcp_flags"),
            "sampler": obj.get("sampler"),
            "iface_in": obj.get("input_snmp") or obj.get("in"),
        }
        return event

    def _from_csv(self, raw: str) -> ParsedEvent | None:
        stripped = raw.strip()
        if not stripped or any(
            c in stripped for c in "{}"
        ):
            return None
        try:
            rows = list(csv.reader(io.StringIO(stripped)))
        except Exception:
            return None
        if not rows or not rows[0]:
            return None
        cols = rows[0]
        if len(cols) < 6:
            return None
        if "srcaddr" in cols:
            header, row = cols, rows[1] if len(rows) > 1 else cols
            mapping = {name: i for i, name in enumerate(header)}
        else:
            header, row = None, cols
            mapping = {"srcaddr": 0, "dstaddr": 2 if len(cols) > 4 else 1, "srcport": 1 if len(cols) > 4 else None, "dstport": 3 if len(cols) > 4 else None}
        if len(row) < 4:
            return None

        def val(key):
            i = mapping.get(key)
            return row[i] if i is not None and i < len(row) else None

        event = ParsedEvent(
            event_id=3001,
            provider="NetFlow",
            computer=None,
            time_created=datetime.now().isoformat(),
            raw=raw,
        )
        dst_idx = mapping.get("dstaddr")
        src_idx = mapping.get("srcaddr")
        event.event_data = {
            "source_ip": val("srcaddr"),
            "destination_ip": val("dstaddr"),
            "source_port": _as_int(val("srcport")),
            "destination_port": _as_int(val("dstport")),
            "protocol": str(row[4]) if len(row) > 4 else "0",
            "packets": _as_int(row[5]) if len(row) > 5 else None,
            "bytes": _as_int(row[6]) if len(row) > 6 else None,
        }
        return event

    @staticmethod
    def _kv(raw: str) -> dict:
        pairs = dict(re.findall(r"(\w+)=([^\s,;]+)", raw))
        return pairs

    @staticmethod
    def _ts(value) -> str | None:
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value)

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
            "source_ip": ed.get("source_ip"),
            "destination_ip": ed.get("destination_ip"),
            "source_port": ed.get("source_port"),
            "destination_port": ed.get("destination_port"),
            "protocol": ed.get("protocol"),
            "process_name": None,
            "command_line": None,
            "logon_type": None,
            "status_code": None,
            "packets": ed.get("packets"),
            "bytes": ed.get("bytes"),
        }