"""Phase G3 — VAJRA OSINT integration (Task 2–8).

Proves the *universal-framework* claim: an independent OSINT service flows
into the main pipeline as just another format — ``osint_record`` parses,
normalizes, is stored, and is written to the graph exactly like a case record.
No special-cased ingestion path exists; citation fields survive end-to-end.
"""

from fastapi.testclient import TestClient

from app.database.session import SessionLocal


SAMPLE_RECORD = {
    "entity_name": "Rakesh Kumar Verma",
    "record_type": "person",
    "age": 41,
    "gender": "male",
    "crime_type": "cyber fraud",
    "crime_description": "Accused in a multi-lakh online banking fraud ring.",
    "status": "absconding",
    "location": "New Delhi",
    "fir_number": "123/2026",
    "plate_number": "DL 01 CA 2345",
    "phone_number": "+91 98765 43210",
    "source_type": "wikipedia",
    "source_url": "https://en.wikipedia.org/wiki/Rakesh_Kumar_Verma",
    "fetched_at": "2026-09-06T10:30:00Z",
}


def test_osint_parser_registered():
    from app.parsers import ParserRegistry

    assert "osint_record" in ParserRegistry.all()


def test_osint_parser_preserves_citation_fields():
    """Task 3 acceptance: parsing produces a ParsedEvent with no data loss on
    citation fields (source_url / source_type / fetched_at)."""
    from app.normalization.engine import normalize_event
    from app.parsers.osint_record import OSINTRecordParser

    parsed = OSINTRecordParser().parse(SAMPLE_RECORD)
    assert parsed is not None
    assert parsed.event_id == 5101  # person

    normalized = normalize_event(parsed, unit_id=None, agent_id=None, format_name="osint_record")
    extra = normalized["extra"]
    assert extra["source_url"] == SAMPLE_RECORD["source_url"]
    assert extra["source_type"] == SAMPLE_RECORD["source_type"]
    assert extra["fetched_at"] == SAMPLE_RECORD["fetched_at"]
    assert extra["entity_name"] == "Rakesh Kumar Verma"
    # structured fields survive too
    assert extra["fir_number"] == "123/2026"
    assert extra["status"] == "absconding"


def test_osint_ingest_builds_graph_node_with_citations(
    client: TestClient, admin_headers: dict[str, str]
):
    """Tasks 5–6 acceptance: an ingested OSINT record lands in the graph as a
    person node retaining source_url / source_type / fetched_at."""
    from app.graph import store
    from app.models.agent import Agent
    from app.services.ingest import ingest_payload

    with SessionLocal() as db:
        agent = db.query(Agent).filter(Agent.agent_id == "OSINT-BRIDGE-01").first()
        if agent is None:
            from app.integrations.osint_client import ensure_osint_bridge_agent

            agent, _ = ensure_osint_bridge_agent(db)
            db.commit()

        from app.models.unit import Unit

        unit = db.query(Unit).filter(Unit.id == agent.unit_id).first()
        result = ingest_payload(
            db,
            {"data": SAMPLE_RECORD},
            agent=agent,
            unit=unit,
            parser_format="osint_record",
        )
        assert result["accepted"] == 1

        gstore = store.get_graph_store(db)
        node = gstore.search("Rakesh Kumar Verma", limit=5)
        assert node, "graph node missing"
        person = next(n for n in node if n["entity_type"] == "person")
        props = person["properties"]
        assert props["source"] == "osint"
        assert props["source_url"] == SAMPLE_RECORD["source_url"]
        assert props["source_type"] == "wikipedia"
        assert props["fetched_at"] == SAMPLE_RECORD["fetched_at"]


def test_osint_entity_links_imported_as_edges(
    client: TestClient, admin_headers: dict[str, str]
):
    """Task 7 acceptance: auto_confirmed → same_as, needs_review → possible_match,
    both carrying match_score; no needs_review pair is merged into one node."""
    from app.graph import store

    links = [
        {
            "entity_a": "Rakesh Verma",
            "entity_b": "Rakesh Kumar Verma",
            "match_score": 96.5,
            "match_status": "auto_confirmed",
        },
        {
            "entity_a": "Pradeep Singh",
            "entity_b": "Pradeep Singh Junior",
            "match_score": 61.0,
            "match_status": "needs_review",
        },
    ]
    with SessionLocal() as db:
        from app.graph.indexer import import_osint_entity_links

        count = import_osint_entity_links(db, links)
        assert count == 2

        gstore = store.get_graph_store(db)
        a = gstore.search("Rakesh Verma", limit=5)[0]
        rel = gstore.neighbors(a["id"])
        rels = {e["relation"] for e in rel["edges"]}
        assert "same_as" in rels

        prop = next(e["properties"] for e in rel["edges"] if e["relation"] == "same_as")
        assert prop["match_score"] == 96.5
        assert prop["match_status"] == "auto_confirmed"

        b = gstore.search("Pradeep Singh Junior", limit=5)[0]
        rel2 = gstore.neighbors(b["id"])
        rels2 = {e["relation"] for e in rel2["edges"]}
        assert "possible_match" in rels2
        # the two review-pending entities remain SEPARATE nodes
        nodes = rel2["nodes"]
        assert len(nodes) == 2


def test_osint_poller_publishes_new_and_skips_seen(
    client: TestClient, admin_headers: dict[str, str]
):
    """Task 2 acceptance: a poll cycle tracks fetched_at per record — a new
    record is published, an already-seen record is skipped."""
    import httpx

    from app.integrations.osint_client import Poller, _citation_key
    from app.models.osint_sync import OsintSyncState

    seen: list[dict] = []

    def fake_client(base_url: str, api_key: str):
        class _Fake:
            def list_entities(self, *, limit=500):
                return [{"entity_name": "Rakesh Kumar Verma", "record_count": 1}]

            def entity_records(self, name):
                return [SAMPLE_RECORD]

            def entity_links(self, name):
                return []

            def close(self):
                pass

        return _Fake()

    def publish(record):
        seen.append(record)
        return {"accepted": 1}

    poller = Poller(fake_client("http://osint", "k"), publish_fn=publish)
    with SessionLocal() as db:
        r1 = poller.run_cycle(db=db)
        assert r1["new_records"] == 1
        assert len(seen) == 1

        key = _citation_key(SAMPLE_RECORD["entity_name"], SAMPLE_RECORD["source_url"], SAMPLE_RECORD["fetched_at"])
        assert db.get(OsintSyncState, key) is not None

        r2 = poller.run_cycle(db=db)  # second cycle: nothing new
        assert r2["new_records"] == 0
        assert len(seen) == 1  # unchanged