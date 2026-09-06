"""Persist a normalized case record into the criminal intelligence graph.

This is the single point where case data enters the graph. The indexer is
storage-agnostic: it talks only to the GraphStore interface (relational by
default, optional Neo4j), so swapping backends never touches the ingest path.
"""

from typing import Any

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