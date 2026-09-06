"""Persist a normalized case record into the criminal intelligence graph.

This is the single point where case data enters the graph. The indexer is
storage-agnostic: it talks only to the GraphStore interface (relational by
default, optional Neo4j), so swapping backends never touches the ingest path.
"""

from typing import Any

import re
from sqlalchemy.orm import Session

from app.graph.extraction import extract_entities
from app.graph.store import get_graph_store
CASE_TO_RELATION = {
    "person": "case_involves_person",
    "phone": "case_assoc_phone",
    "email": "case_assoc_email",
    "vehicle": "case_assoc_vehicle",
    "bank_account": "case_assoc_account",
    "location": "case_located",
}

PERSON_TO_ATTRIBUTES = {
    "phone": "person_has_phone",
    "email": "person_has_email",
    "vehicle": "person_has_vehicle",
    "bank_account": "person_has_account",
}


def index_osint_record(db: Session, normalized: dict[str, Any], event_row_id: str | None = None) -> None:
    """Write one OSINT record into the graph as a person/actor node.

    The node is keyed by ``entity_name`` — if a resolved identity already
    exists (e.g. from a case record), it is upserted, not duplicated. Citation
    fields survive as node properties so the UI can show a verified public
    record with a clickable source link.
    """
    extra = normalized.get("extra") or {}
    name = (extra.get("entity_name") or "").strip()
    if not name:
        return

    store = get_graph_store(db)
    node = store.create_node(
        "person",
        name.lower(),
        name=name,
        properties={
            "source": "osint",
            "record_type": extra.get("record_type"),
            "age": extra.get("age"),
            "gender": extra.get("gender"),
            "crime_type": extra.get("crime_type"),
            "crime_description": extra.get("crime_description"),
            "status": extra.get("status"),
            "location": extra.get("location"),
            "fir_number": extra.get("fir_number"),
            "plate_number": extra.get("plate_number"),
            "phone_number": extra.get("phone_number"),
            "source_type": extra.get("source_type"),
            "source_url": extra.get("source_url"),
            "fetched_at": extra.get("fetched_at"),
            "event_row_id": event_row_id,
        },
    )

    place = (extra.get("location") or "").strip()
    if place:
        loc = store.create_node("location", place.lower(), name=place.title())
        store.create_edge(node["id"], loc["id"], "person_located", event_row_id=event_row_id)

    phone = (extra.get("phone_number") or "").strip()
    if phone:
        digits = re.sub(r"[^0-9]", "", phone)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if len(digits) == 10:
            p = store.create_node("phone", digits, name=f"+91-{digits[:5]}xxxxx")
            store.create_edge(node["id"], p["id"], "person_has_phone", event_row_id=event_row_id)

    db.commit()


def import_osint_entity_links(db: Session, links: list[dict[str, Any]]) -> int:
    """Import vajra-osint ``entity_links`` vertices directly — no re-matching.

    ``auto_confirmed`` vertices become a ``same_as`` edge; ``needs_review``
    vertices become a distinct ``possible_match`` edge. Both carry the stored
    ``match_score``. Review-pending pairs are NEVER merged into a single node —
    they remain two nodes joined by an edge a human investigator resolves.
    """
    store = get_graph_store(db)
    created = 0
    for link in links:
        entity_a = (link.get("entity_a") or "").strip()
        entity_b = (link.get("entity_b") or "").strip()
        status = link.get("match_status")
        if not entity_a or not entity_b or status not in ("auto_confirmed", "needs_review"):
            continue
        node_a = store.create_node(
            "person", entity_a.lower(), name=entity_a, properties={"source": "osint"}
        )
        node_b = store.create_node(
            "person", entity_b.lower(), name=entity_b, properties={"source": "osint"}
        )
        if node_a["id"] == node_b["id"]:
            continue
        relation = "same_as" if status == "auto_confirmed" else "possible_match"
        store.create_edge(
            node_a["id"],
            node_b["id"],
            relation,
            properties={
                "match_score": link.get("match_score"),
                "match_status": status,
            },
        )
        created += 1
    db.commit()
    return created


def index_case_record(db: Session, normalized: dict[str, Any], event_row_id: str | None = None) -> None:
    """Index one normalized case record into the graph store."""
    extra = normalized.get("extra") or {}
    hits = extract_entities(normalized)
    if not hits:
        return

    store = get_graph_store(db)
    text = (normalized.get("command_line") or "")[:1000]

    ids: dict[tuple[str, str], str] = {}
    for hit in hits:
        node = store.create_node(
            hit["entity_type"],
            hit["value"],
            name=hit["name"],
            properties={**hit["properties"], "event_row_id": event_row_id},
        )
        ids[(hit["entity_type"], hit["value"])] = node["id"]

    case_id = ids.get(("case", (extra.get("case_id") or "").strip().upper()))
    if not case_id:
        return

    for key, node_id in ids.items():
        entity_type, value = key
        if entity_type == "case" or node_id == case_id:
            continue
        store.create_edge(
            case_id,
            node_id,
            CASE_TO_RELATION.get(entity_type, "ASSOCIATED"),
            event_row_id=event_row_id,
            source_text=text,
        )

    persons = [ids[(t, v)] for (t, v) in ids if t == "person"]
    for p_id in persons:
        for entity_type in ("phone", "email", "vehicle", "bank_account"):
            for (t, v), nid in ids.items():
                if t == entity_type:
                    store.create_edge(
                        p_id,
                        nid,
                        PERSON_TO_ATTRIBUTES[entity_type],
                        event_row_id=event_row_id,
                    )

    if (extra.get("record_type") or "").lower() == "cdr":
        phones = [ids[(t, v)] for (t, v) in ids if t == "phone"]
        for src, dst in zip(phones, phones[1:]):
            store.create_edge(src, dst, "phone_contacts_phone", event_row_id=event_row_id)

    if (extra.get("record_type") or "").lower() == "transaction" and len(persons) >= 2:
        store.create_edge(
            persons[0], persons[1], "person_financial_to_person", event_row_id=event_row_id
        )
    elif (extra.get("record_type") or "").lower() == "transaction" and len(persons) == 1:
        counterpart = ids.get(("person", "counterparty"))
        if counterpart and counterpart != persons[0]:
            store.create_edge(
                persons[0], counterpart, "person_financial_to_person", event_row_id=event_row_id
            )

    db.commit()