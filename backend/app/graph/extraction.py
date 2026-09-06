"""Deterministic entity extraction from normalized case records.

All matchers are regex/structured-field based — no ML, no real data. Entities
feed the Criminal Intelligence graph:
  person | phone | email | vehicle | bank_account | location | case
"""

import re
import unicodedata
from typing import Any

PHONE_RE = re.compile(r"(?<![\d+])(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
VEHICLE_RE = re.compile(
    r"\b(?:[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,2}[-\s]?\d{4})\b"
    r"|\b(?:[A-Z]{2}[-\s]?\d{2}[-\s]?[A-Z]{1,3}[-\s]?\d{1,4})\b"
)
PINCODE_RE = re.compile(r"\b([1-9]\d{5})\b")
ACCOUNT_LABEL_RE = re.compile(r"\b(?:a/c|ac(?:count)?|bank|ifsc)[- :]?\s*([A-Z0-9-]{9,22})\b", re.IGNORECASE)

DISTRICT_NAMES = [
    "delhi", "gurugram", "new delhi", "mumbai", "kolkata", "pune", "chennai",
    "bangalore", "hyderabad", "chandigarh", "amritsar", "ludhiana",
    "jaisalmer", "jodhpur", "churu", "bikaner", "jaipur", "lucknow", "kanpur",
    "varanasi", "patna", "guwahati", "shillong", "dehradun", "shimla", "solan",
    "indore", "bhopal", "nagpur", "solapur", "kolhapur", "raipur", "ranchi",
    "vizag", "kochi", "coimbatore", "mysore", "agra", "mathura", "meerut",
    "silchar", "dibrugarh", "itarsi", "bhusaval", "nagmotha", "wani",
]

ENTITY = (
    "person",
    "phone",
    "email",
    "vehicle",
    "bank_account",
    "location",
    "case",
)


def _clean_text(value: str) -> str:
    return unicodedata.normalize("NFKD", (value or "")).lower()


def _normalize_phone(value: str) -> str | None:
    digits = re.sub(r"[^0-9]", "", str(value))
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits if digits and len(digits) == 10 and digits[0] in "6789" else None


def _build_location_props(text: str, address: str) -> dict:
    props = {"address": address}
    pin = PINCODE_RE.search(address)
    if pin:
        props["pincode"] = pin.group(1)
    lowered = _clean_text(address + " " + text)
    for district in DISTRICT_NAMES:
        if district in lowered:
            props["district"] = district.title()
            break
    return props


def extract_entities(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list of entity hits: {entity_type, value, name, properties}."""
    extra = normalized.get("extra") or {}
    text = normalized.get("command_line") or ""
    hits: list[dict[str, Any]] = []

    def add(entity_type: str, value: str, name: str | None = None, properties: dict | None = None) -> None:
        if not value:
            return
        hits.append(
            {
                "entity_type": entity_type,
                "value": value,
                "name": name or value,
                "properties": properties or {},
                "_order": len(hits),
            }
        )

    case_id = (extra.get("case_id") or "").strip()
    if case_id:
        ts = normalized.get("timestamp")
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
        add(
            "case",
            case_id.upper(),
            case_id.upper(),
            {
                "record_type": extra.get("record_type"),
                "officer": normalized.get("username"),
                "unit": normalized.get("hostname"),
                "date": ts_str,
            },
        )

    for name in extra.get("persons") or []:
        clean = _clean_text(name).strip()
        if clean and len(clean) >= 3:
            add("person", clean, str(name).strip())

    for phone in extra.get("phones") or []:
        digits = _normalize_phone(phone)
        if digits:
            add("phone", digits, f"+91-{digits[:5]}xxxxx")

    for email in extra.get("emails") or []:
        norm = str(email).lower().strip()
        if "@" in norm:
            add("email", norm, norm)

    for veh in extra.get("vehicles") or []:
        norm = re.sub(r"[\s-]+", "", str(veh)).upper()
        if len(norm) >= 6:
            add("vehicle", norm, re.sub(r"[\s-]+", "", str(veh)).upper())

    for acct in extra.get("accounts") or []:
        norm = _clean_text(acct).replace(" ", "").upper()
        if norm and not norm.lower().startswith(("iban", "acct")):
            norm = str(acct).strip().upper()
        add("bank_account", norm or str(acct).strip(), str(acct).strip())

    for addr in extra.get("addresses") or []:
        norm = re.sub(r"\s+", " ", str(addr)).strip()
        if norm:
            add("location", norm.lower(), norm.title(), _build_location_props(text, norm))

    phones_from_text = PHONE_RE.findall(text)
    for p in phones_from_text:
        digits = _normalize_phone(p)
        if digits:
            add("phone", digits, f"+91-{digits[:5]}xxxxx")

    emails_from_text = EMAIL_RE.findall(text)
    for e in emails_from_text:
        add("email", e.lower(), e.lower())

    vehicles_from_text = VEHICLE_RE.findall(text)
    for plate in vehicles_from_text:
        if isinstance(plate, tuple):
            plate = plate[0] or plate[1]
        norm = re.sub(r"[\s-]+", "", plate).upper()
        if len(norm) >= 6:
            add("vehicle", norm, norm)

    acct_match = ACCOUNT_LABEL_RE.search(text)
    if acct_match:
        add("bank_account", acct_match.group(1).upper(), acct_match.group(1).upper())

    pin = PINCODE_RE.search(text)
    if pin:
        add("location", f"PIN-{pin.group(1)}", f"Pincode {pin.group(1)}")

    # de-duplicate, keep first occurrence order
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for hit in sorted(hits, key=lambda h: h["_order"]):
        key = (hit["entity_type"], hit["value"])
        if key not in seen:
            seen[key] = hit
    return [seen[k] for k in seen]