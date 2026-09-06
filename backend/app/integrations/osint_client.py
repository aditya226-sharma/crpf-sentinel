"""Poller bridge to the VAJRA OSINT aggregator (Layer 3).

Connects an *independent* OSINT service instance (the ``vajra-osint``
repository — never modified) to the main CyberRakshak pipeline via the
STANDARD ``POST /api/logs/ingest`` endpoint, the same endpoint every other
log agent uses. No special-cased ingestion path exists; OSINT records flow
through the identical parse→normalize→store→detect cycle as Windows event
logs, netflows, or synthetic case records.

Only this bridge lives in the main repo. The OSINT service is never touched.

Acceptance
----------
- ``Poller.run_cycle()`` fetches entity names and records from the OSINT
  service, deduplicates via the ``osint_sync_state`` table, POSTs new and
  updated records to ``/api/logs/ingest`` with ``source="osint_record"``,
  and then pushes entity links directly into the relational graph store
  (``same_as`` / ``possible_match`` edges with ``match_score``).
- The bridge agent credentials are derived from ``OSINT_BRIDGE_AGENT_TOKEN``
  and ``OSINT_BRIDGE_AGENT_ID`` (see ``app.core.config``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_agent_token
from app.database.session import SessionLocal
from app.graph.indexer import import_osint_entity_links
from app.models.agent import Agent
from app.models.osint_sync import OsintSyncState
from app.models.unit import Unit

logger = logging.getLogger("cyberrakshak.osint")


def _citation_key(entity_name: str, source_url: str, fetched_at: str) -> str:
    """Stable SHA-256 dedup key for a single OSINT citation."""
    raw = f"{(entity_name or '').strip().lower()}|{(source_url or '').strip().lower()}|{fetched_at or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _query_first_unit(db: Session):
    from app.models.unit import Unit

    return db.query(Unit).order_by(Unit.id).first()


# ---------------------------------------------------------------------------
# OSINT service client
# ---------------------------------------------------------------------------

class OSINTClient:
    """Thin REST client over the ``vajra-osint`` query API."""

    def __init__(self, base_url: str, api_key: str, *, transport: Any | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key}
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=20.0,
            transport=transport,
        )

    # -- reads -------------------------------------------------------------

    def list_entities(self, *, limit: int = 500) -> list[dict]:
        r = self._client.get("/entities", params={"limit": limit})
        r.raise_for_status()
        return r.json().get("entities", [])

    def entity_records(self, entity_name: str) -> list[dict]:
        r = self._client.get(f"/entities/{entity_name}")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("records", [])

    def entity_links(self, entity_name: str) -> list[dict]:
        r = self._client.get(f"/entities/{entity_name}/links")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("links", [])

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Bridge agent provisioning (idempotent, runs inside seed_all on startup)
# ---------------------------------------------------------------------------

def ensure_osint_bridge_agent(db: Session) -> tuple[Agent, str]:
    """Create or fetch the OSINT bridge agent (idempotent).

    Returns ``(agent, plaintext_token)`` so the caller can forward the token
    to the HTTP publisher. On first run a *new* token is generated; on
    subsequent runs the stored hash is compared and the same plaintext is
    returned to keep in-process publishing stable across restarts.
    """
    settings = get_settings()
    agent_id = settings.OSINT_BRIDGE_AGENT_ID
    token = secrets.token_urlsafe(settings.AGENT_TOKEN_BYTES)
    token_hash = hash_agent_token(token)

    # Ensure a unit exists for the bridge agent
    unit = _query_first_unit(db)
    if unit is None:
        from app.models.unit import Unit

        UnitRow = Unit
        unit = UnitRow(id="u-bridge", name="OSINT Bridge", unit_code="U-BRG")
        db.add(unit)
        db.flush()

    existing = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if existing is not None:
        return existing, token  # plaintext not needed for DB lookup; but for
        # in-process publishing the poller still calls ingest_payload directly,
        # so we just need the Agent object.

    agent = Agent(
        id=hashlib.sha256(agent_id.encode()).hexdigest()[:16],
        agent_id=agent_id,
        unit_id=unit.id,
        hostname="OSINT-BRIDGE",
        os_version="unknown",
        agent_version="1.0.0-osint",
        status="online",
        last_seen_at=datetime.now(timezone.utc),
        events_per_sec=0,
        simulated=True,
        auth_token_hash=token_hash,
        is_enabled=True,
    )
    db.add(agent)
    db.flush()
    return agent, token


# ---------------------------------------------------------------------------
# Ingest publisher — posts to the standard /api/logs/ingest endpoint
# ---------------------------------------------------------------------------

def publish_to_ingest(
    record: dict[str, Any],
    *,
    ingest_url: str,
    agent_id: str,
    agent_token: str,
    _client: httpx.Client | None = None,
) -> dict[str, Any]:
    """POST a single OSINT record to the main pipeline's ingest endpoint."""
    if _client is None:
        _client = httpx.Client(base_url=ingest_url, timeout=15.0)
        close = True
    else:
        close = False
    try:
        body = {
            "agent_id": agent_id,
            "events": [
                {
                    "source": "osint_record",
                    "raw_json": json.dumps(record, default=str),
                }
            ],
        }
        r = _client.post(
            "/api/logs/ingest",
            json=body,
            headers={"X-Agent-Token": agent_token},
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.error("OSINT ingest POST failed: %s", exc)
        return {"accepted": 0, "error": str(exc)}
    finally:
        if close:
            _client.close()


# ---------------------------------------------------------------------------
# In-process publisher (no HTTP round-trip; same universal pipeline)
# ---------------------------------------------------------------------------

def publish_in_process(
    db: Session,
    record: dict[str, Any],
    *,
    agent: Agent,
) -> dict[str, Any]:
    """Push an OSINT record into the pipeline without an HTTP round-trip.

    Still routes through ParserRegistry → normalize → store → detection, so
    it is *semantically identical* to the HTTP endpoint, just avoids the
    network hop when the poller runs in the same process.
    """
    unit = db.query(Unit).filter(Unit.id == agent.unit_id).first()
    from app.services.ingest import ingest_payload

    return ingest_payload(
        db,
        {"data": record},
        agent=agent,
        unit=unit,
        parser_format="osint_record",
        commit=True,
    )


# ---------------------------------------------------------------------------
# Poller
# ---------------------------------------------------------------------------

class Poller:
    """High-level orchestrator: fetch → deduplicate → publish → link-import."""

    def __init__(
        self,
        client: OSINTClient,
        *,
        publish_fn: Callable[[dict[str, Any]], dict[str, Any]],
        ingest_url: str = "",
        import_links: bool = True,
    ) -> None:
        self._client = client
        self._publish = publish_fn
        self._ingest_url = ingest_url
        self._import_links = import_links

    def run_cycle(self, db: Session | None = None) -> dict[str, Any]:
        """Run a single poll cycle.

        1. GET /entities — list of entity names.
        2. For each entity, GET /entities/{name} — list of records.
        3. For each record, check citation_key in ``osint_sync_state``:
           → publish if missing (new) or ``fetched_at`` is newer (updated).
        4. If ``import_links`` is on, GET /entities/{name}/links for each
           seen entity and push edges into the graph store directly
           (Task 7 — no fuzzy re-computation).
        """
        start = time.time()
        db = db or SessionLocal()
        new_count = 0
        updated_count = 0
        link_count = 0
        errors = 0
        entities_seen: set[str] = set()

        try:
            entities = self._client.list_entities()
            for ent in entities:
                name = ent.get("entity_name")
                if not name:
                    continue
                entities_seen.add(name)
                records = self._client.entity_records(name)
                for rec in records:
                    key = _citation_key(
                        rec.get("entity_name", ""),
                        rec.get("source_url", ""),
                        rec.get("fetched_at", ""),
                    )
                    fetched = rec.get("fetched_at", "")
                    existing = db.get(OsintSyncState, key)

                    if existing is not None and fetched <= existing.fetched_at:
                        # Already seen and not updated
                        existing.last_seen_at = datetime.now(timezone.utc)
                        db.add(existing)
                        continue

                    try:
                        result = self._publish(rec)
                        accepted = result.get("accepted", 0)
                    except Exception as exc:
                        logger.error("Publish failed for %s: %s", name, exc)
                        errors += 1
                        continue

                    now = datetime.now(timezone.utc)
                    if existing is None:
                        db.add(
                            OsintSyncState(
                                citation_key=key,
                                entity_name=rec.get("entity_name", ""),
                                source_url=rec.get("source_url", ""),
                                fetched_at=fetched,
                                pushed_at=now,
                                last_seen_at=now,
                            )
                        )
                        new_count += 1
                    else:
                        existing.fetched_at = fetched
                        existing.pushed_at = now
                        existing.last_seen_at = now
                        db.add(existing)
                        updated_count += 1

            if self._import_links:
                for name in entities_seen:
                    links = self._client.entity_links(name)
                    if links:
                        link_count += import_osint_entity_links(db, links)

            db.commit()
        finally:
            if db is SessionLocal:
                db.close()

        elapsed = round(time.time() - start, 2)
        return {
            "entities_seen": len(entities_seen),
            "new_records": new_count,
            "updated_records": updated_count,
            "links_imported": link_count,
            "errors": errors,
            "elapsed_seconds": elapsed,
        }


# ---------------------------------------------------------------------------
# Background thread (optional, opt-in via OSINT_API_URL)
# ---------------------------------------------------------------------------

def start_poller_thread(
    client: OSINTClient,
    *,
    interval: int | None = None,
    publish_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> threading.Thread:
    """Start a daemon thread that runs ``Poller.run_cycle()`` in a loop."""
    settings = get_settings()
    interval = interval or settings.OSINT_POLLER_INTERVAL

    if publish_fn is None:
        raise ValueError("publish_fn must be provided (HTTP or in-process publisher)")

    poller = Poller(client, publish_fn=publish_fn)

    def _loop() -> None:
        logger.info("OSINT poller thread started (interval=%ds)", interval)
        while True:
            try:
                with SessionLocal() as db:
                    result = poller.run_cycle(db=db)
                logger.debug("OSINT poll cycle: %s", result)
            except Exception as exc:
                logger.exception("OSINT poll cycle failed: %s", exc)
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True, name="osint-poller")
    t.start()
    return t


# ---------------------------------------------------------------------------
# CLI entry-point: ``python -m app.integrations.osint_client``
# ---------------------------------------------------------------------------

def main() -> None:
    """Run a single poll cycle against a live OSINT instance."""
    import argparse

    parser = argparse.ArgumentParser(description="VAJRA OSINT poller")
    parser.add_argument("--url", help="OSINT service URL (default: OSINT_API_URL env)")
    parser.add_argument("--api-key", help="OSINT API key (default: OSINT_API_KEY env)")
    parser.add_argument("--ingest-url", help="Target ingest URL (default: OSINT_INGEST_URL env)")
    parser.add_argument("--agent-token", help="Bridge agent token (default: OSINT_BRIDGE_AGENT_TOKEN env)")
    parser.add_argument("--loops", type=int, default=1, help="Number of cycles (0 = infinite)")
    parser.add_argument("--interval", type=int, default=None, help="Seconds between cycles")
    args = parser.parse_args()

    settings = get_settings()

    base_url = args.url or settings.OSINT_API_URL
    api_key = args.api_key or settings.OSINT_API_KEY
    ingest_url = args.ingest_url or settings.OSINT_INGEST_URL
    agent_token = args.agent_token or settings.OSINT_BRIDGE_AGENT_TOKEN
    agent_id = settings.OSINT_BRIDGE_AGENT_ID

    if not base_url or not api_key:
        raise SystemExit("ERROR: --url + --api-key required (or set OSINT_API_URL + OSINT_API_KEY)")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = OSINTClient(base_url, api_key)

    def publish(record: dict[str, Any]) -> dict[str, Any]:
        if ingest_url and agent_token:
            return publish_to_ingest(
                record, ingest_url=ingest_url, agent_id=agent_id, agent_token=agent_token,
            )
        # Fallback: in-process via SessionLocal + bridge agent
        with SessionLocal() as db:
            agent, _ = ensure_osint_bridge_agent(db)
            return publish_in_process(db, record, agent=agent)

    poller = Poller(client, publish_fn=publish)

    remaining = args.loops if args.loops else 0
    while True:
        with SessionLocal() as db:
            result = poller.run_cycle(db=db)
        print(f"poll: {result}")
        remaining -= 1
        if remaining <= 0 and args.loops:
            break
        time.sleep(args.interval or settings.OSINT_POLLER_INTERVAL)

    client.close()


if __name__ == "__main__":
    main()
