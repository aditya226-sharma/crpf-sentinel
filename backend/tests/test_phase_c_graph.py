"""Phase C — Criminal Intelligence graph.

Proves: case records flow through the SAME ingest pipeline into the graph;
the relational GraphStore exposes entities/relationships/centrality/
communities/connectivity; and the demo's hidden nexus (two far-apart records
secretly sharing one phone number) is discoverable end-to-end.
"""

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.graph.extraction import extract_entities
from app.seed.case_records import HIDDEN_PHONE, seed_case_records


def test_graph_tables_registered():
    from app.database.base import Base

    tables = set(Base.metadata.tables.keys())
    assert "graph_nodes" in tables
    assert "graph_edges" in tables


def test_extract_entities_structured_and_regex():
    normalized = {
        "username": "Insp. A. K. Sinha",
        "timestamp": "2026-02-01T10:00:00Z",
        "command_line": "Seized truck DL-01-AB-1234; contact +91 98140 55667; mailops.case@example.in; "
        "A/C IFSC PUNB0123456 50012000111 near Sukhna Lake",
        "extra": {
            "case_id": "FIR-9999",
            "record_type": "fir",
            "persons": ["Ramesh Patil"],
            "phones": ["+91 98111 22334"],
            "addresses": ["Sector 22 Police Station, Chandigarh"],
            "vehicles": ["PB-02-CX-7721"],
            "accounts": [],
        },
    }
    hits = extract_entities(normalized)
    types = {h["entity_type"] for h in hits}
    assert {"case", "person", "phone", "email", "vehicle", "bank_account", "location"} <= types
    phone_values = {h["value"] for h in hits if h["entity_type"] == "phone"}
    assert "9811122334" in phone_values
    assert "9814055667" in phone_values  # extracted from free text


def test_case_record_ingest_builds_graph(
    client: TestClient, admin_headers: dict[str, str]
):
    units = client.get("/api/units", headers=admin_headers).json()
    reg = client.post(
        "/api/agents",
        headers=admin_headers,
        json={
            "agent_id": "WIN-CI-CASE-001",
            "unit_id": units[0]["id"],
            "hostname": "CASE-CATALOG",
            "simulated": True,
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["api_token"]

    ing = client.post(
        "/api/logs/ingest",
        headers={"x-agent-token": token},
        json={
            "agent_id": "WIN-CI-CASE-001",
            "unit_id": units[0]["id"],
            "events": [
                {
                    "source": "case_record",
                    "data": {
                        "case_id": "FIR-2026-0042",
                        "record_type": "fir",
                        "date": "2026-03-01T08:30:00Z",
                        "officer": "Insp. A. Kumar",
                        "unit_code": "Chandigarh",
                        "summary": "Seizure of timber near Sukhna; driver Ramesh Patil; "
                        "vehicle PB-02-CX-7721; contact 98111 22334.",
                        "persons": ["Ramesh Patil"],
                        "phones": ["+91 98111 22334"],
                        "vehicles": ["PB-02-CX-7721"],
                        "addresses": ["Sukhna Lake Shore, Chandigarh"],
                        "accounts": [],
                    },
                }
            ],
        },
    )
    assert ing.status_code == 200, ing.text
    assert ing.json()["accepted"] == 1

    overview = client.get("/api/graph/overview", headers=admin_headers).json()
    assert overview["nodes"] >= 4
    assert overview["edges"] >= 3

    first = client.get("/api/graph/entities?entity_type=case", headers=admin_headers).json()
    assert first["items"], "case node must exist"
    case_id = first["items"][0]["id"]

    rel = client.get(f"/api/graph/relationships?entity_id={case_id}", headers=admin_headers).json()
    rel_types = {e["relation"] for e in rel["edges"]}
    assert "case_involves_person" in rel_types
    assert "case_assoc_phone" in rel_types
    assert "case_assoc_vehicle" in rel_types
    assert "case_located" in rel_types

    assert client.get("/api/graph/central", headers=admin_headers).json()["items"]
    assert client.get("/api/graph/communities", headers=admin_headers).json()["items"]

    conn = client.get(
        "/api/graph/connectivity",
        params={"entity_a": case_id, "entity_b": case_id},
        headers=admin_headers,
    )
    assert conn.status_code == 200
    assert len(conn.json()["path"]) == 1

    assert client.get("/api/graph/search", params={"q": "patil"}, headers=admin_headers).json()["items"]


def test_hidden_nexus_two_records_share_one_phone():
    db = SessionLocal()
    try:
        from app.models.event import NormalizedEvent
        from app.models.graph_node import GraphEdge, GraphNode
        from app.models.log import Log

        # Reset the graph + case-record artifacts from previous module tests so
        # the corpus seeds fresh, then exercise the real pipeline.
        db.query(GraphEdge).delete()
        db.query(GraphNode).delete()
        case_log_ids = [l.id for l in db.query(Log).filter(Log.source == "case_record").all()]
        if case_log_ids:
            db.query(NormalizedEvent).filter(NormalizedEvent.log_id.in_(case_log_ids)).delete()
        db.query(Log).filter(Log.source == "case_record").delete()
        db.commit()

        seeded = seed_case_records(db)
        assert seeded > 100, "case-record corpus must be substantial"

        from app.graph.store import RelationalGraphStore
        from app.graph.extraction import _normalize_phone

        digits = _normalize_phone(HIDDEN_PHONE)
        assert digits == "9827044219"

        store = RelationalGraphStore(db)
        hits = store.search(digits, limit=10)
        phone = next((h for h in hits if h["entity_type"] == "phone"), None)
        assert phone is not None, "the shared hidden phone must be a graph node"

        rel = store.neighbors(phone["id"], depth=1)
        case_neighbors = [
            n for n in rel["nodes"].values() if n["entity_type"] == "case"
        ]
        assert len(case_neighbors) >= 2, "hidden nexus: two cases join via one phone"

        central = store.central(limit=100)
        assert central, "centrality ranking must return something"
    finally:
        db.close()