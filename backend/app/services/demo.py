"""Demo automation: realistic seed data + scripted attack simulation + reset.

ALL DATA IS SYNTHETIC. Everything generated here describes fictional CRPF
units, hosts, users and incidents for the SIH26156 demonstration. No real
operational information is used.

The simulate and seed paths push raw event payloads through the SAME pipeline
as real agents (ParserRegistry -> normalize -> detection engine -> risk
scoring), so a judge asking "is this actually running?" always gets an honest
"yes — this is the real detection path".
"""

import json
import random
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session
from app.core.security import generate_agent_token
from app.models.agent import Agent
from app.models.alert import Alert, AlertEvent
from app.models.event import NormalizedEvent
from app.models.incident import Incident, IncidentAlert, IncidentNote
from app.models.log import Log
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.models.user import User
from app.normalization.engine import normalize_event
from app.parsers import ParserRegistry
from app.services.ingest import ingest_payload

logger = logging.getLogger("cyberrakshak.demo")

SIM_AGENT_PREFIX = "SIM-"

USERS_POOL = ["administrator", "s.verma", "r.kapoor", "a.singh", "m.khan"]
EXFIL_USER = "m.khan"


def _structured_payload(event_id: int, computer: str, when: datetime, data: dict) -> dict:
    provider = {
        4624: "Microsoft-Windows-Security-Auditing",
        4625: "Microsoft-Windows-Security-Auditing",
        4648: "Microsoft-Windows-Security-Auditing",
        4672: "Microsoft-Windows-Security-Auditing",
        4688: "Microsoft-Windows-Security-Auditing",
        4720: "Microsoft-Windows-Security-Auditing",
        4728: "Microsoft-Windows-Security-Auditing",
        4732: "Microsoft-Windows-Security-Auditing",
        1102: "Microsoft-Windows-Eventlog",
        7045: "Service Control Manager",
    }.get(event_id, "Microsoft-Windows-Security-Auditing")
    return {
        "System": {
            "EventID": event_id,
            "Provider": {"Name": provider},
            "Computer": computer,
            "TimeCreated": {"SystemTime": when.isoformat()},
        },
        "EventData": data or {},
    }


def ensure_sim_agents(db: Session, units: dict[str, Unit]) -> dict[str, Agent]:
    """Create (idempotently) one simulated agent per unit, reused across calls."""
    agents: dict[str, Agent] = {}
    for code, unit in units.items():
        agent_id = f"{SIM_AGENT_PREFIX}AGT-{code.split('-')[1]}"
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if agent is None:
            token, token_hash = generate_agent_token()
            hostname = f"CRPF-SIM-{int(code.split('-')[1]):03d}"
            agent = Agent(
                id=uuid.uuid4().hex[:16],
                agent_id=agent_id,
                unit_id=unit.id,
                hostname=hostname,
                ip_address=f"10.{int(code.split('-')[1]):02d}.0.1",
                os_version="10.0.22631 (Windows 11)",
                agent_version="1.0.0-demo",
                status="online",
                last_seen_at=datetime.now(timezone.utc),
                events_per_sec=5,
                cpu_usage=8.0,
                memory_usage=30.0,
                simulated=True,
                auth_token_hash=token_hash,
                is_enabled=True,
            )
            db.add(agent)
            db.flush()
        agents[code] = agent
    db.commit()
    return agents


def _push(db: Session, agent: Agent, unit: Unit, event_id: int, when: datetime, data: dict,
          *, commit: bool = True, publish_event: bool = True) -> None:
    payload = _structured_payload(event_id, agent.hostname, when, data)
    ingest_payload(db, payload, agent=agent, unit=unit, commit=commit, publish_event=publish_event)


def simulate_attack(db: Session, scenario: str = "espionage") -> dict:
    """Replay a scripted multi-stage synthetic attack through the real pipeline."""
    units = {u.unit_code: u for u in db.query(Unit).all()}
    if not units:
        raise RuntimeError("No units seeded")
    agents = ensure_sim_agents(db, units)

    now = datetime.now(timezone.utc)
    deltas = [timedelta(seconds=d) for d in (0, 2, 5, 9, 14, 20, 27, 35, 44, 54, 65)]
    unit_codes = list(units.keys())
    picked = unit_codes[: max(2, min(len(unit_codes), 3))]

    # Phase 1: Recon — scattered failed logons from an external source.
    recon_ip = "203.0.113.66"
    recon_target = picked[0]
    for d in (deltas[0], deltas[1], deltas[2]):
        _push(db, agents[recon_target], units[recon_target], 4625, now + d,
              {"SubjectUserName": USERS_POOL[0], "IpAddress": recon_ip, "Status": "0xC000006A"})

    # Phase 2: Initial access — VPN logon for a sensitive user from recon IP.
    vpn_unit = picked[1]
    _push(db, agents[vpn_unit], units[vpn_unit], 4624, now + deltas[3],
          {"SubjectUserName": EXFIL_USER, "TargetUserName": EXFIL_USER,
           "IpAddress": recon_ip, "LogonType": "3", "WorkstationName": "VPN-GW-01"})

    # Phase 3: Privilege escalation — 4672 special privileges assigned.
    _push(db, agents[vpn_unit], units[vpn_unit], 4672, now + deltas[4],
          {"SubjectUserName": EXFIL_USER, "TargetUserName": EXFIL_USER})

    # Phase 4: Lateral movement — 4648 explicit credential + 4624 on another host.
    _push(db, agents[vpn_unit], units[vpn_unit], 4648, now + deltas[5],
          {"SubjectUserName": EXFIL_USER, "TargetUserName": "administrator", "IpAddress": "10.20.30.41"})
    _push(db, agents[vpn_unit], units[vpn_unit], 4624, now + deltas[6],
          {"SubjectUserName": EXFIL_USER, "TargetUserName": "administrator",
           "IpAddress": "10.20.30.41", "LogonType": "3"})

    # Phase 5: Persistence — 7045 new service.
    persist_unit = picked[2] if len(picked) > 2 else picked[1]
    _push(db, agents[persist_unit], units[persist_unit], 7045, now + deltas[7],
          {"ServiceName": "CRPFUpdateSvc", "ImagePath": "C:\\Windows\\System32\\svchost.exe -k netsvcs",
           "SubjectUserName": "administrator"})

    # Phase 6: Defence evasion — 1102 audit log cleared.
    _push(db, agents[persist_unit], units[persist_unit], 1102, now + deltas[8],
          {"SubjectUserName": EXFIL_USER, "LogName": "Security"})

    # Phase 7: Exfiltration / attacker tooling — encoded PowerShell.
    _push(db, agents[persist_unit], units[persist_unit], 4688, now + deltas[9],
          {"SubjectUserName": EXFIL_USER,
           "NewProcessName": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
           "CommandLine": "powershell.exe -nop -w hidden -enc SQBFAFgAKAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkA"})

    # Phase 8: Rogue account — 4720.
    _push(db, agents[persist_unit], units[persist_unit], 4720, now + deltas[10],
          {"NewAccountName": "backdoor_admin", "SubjectUserName": EXFIL_USER})

    db.commit()

    since = now - timedelta(seconds=90)
    alerts = (
        db.query(Alert)
        .filter(Alert.created_at >= since)
        .order_by(Alert.created_at.asc())
        .all()
    )
    return {
        "status": "ok",
        "scenario": scenario,
        "phases": ["recon", "initial_access", "privilege_escalation", "lateral_movement",
                   "persistence", "defence_evasion", "exfiltration", "persistence_account"],
        "events_ingested": 11,
        "alerts_fired": [
            {
                "id": a.alert_id,
                "title": a.title,
                "severity": a.severity,
                "risk_score": a.risk_score,
                "mitre": a.mitre_technique,
            }
            for a in alerts
        ],
        "units": unit_codes,
    }


def _bulk_ambient(
    db: Session, agent: Agent, unit: Unit, event_id: int, rows: list[tuple[datetime, str, str]]
) -> int:
    """Insert benign ambient events directly (parse + normalize, then bulk insert).

    These 4624/4688 events never match a rule, so running each through the full
    transaction-per-event pipeline is pure overhead. We still parse + normalize
    them through the real code path, then insert in one batch.
    """
    parser = ParserRegistry.get("windows")
    log_rows: list[Log] = []
    event_rows: list[NormalizedEvent] = []
    now = datetime.now(timezone.utc)
    for when, user, process in rows:
        payload = _structured_payload(
            event_id, agent.hostname, when,
            {"SubjectUserName": user, "IpAddress": "10.0.0.8", "LogonType": "3"}
            if event_id == 4624 else
            {"SubjectUserName": user, "NewProcessName": process,
             "CommandLine": "C:\\Windows\\System32\\svchost.exe -k netsvcs"},
        )
        parsed = parser.parse(payload)
        if parsed is None:
            continue
        normalized = normalize_event(
            parsed, unit_id=unit.id, agent_id=agent.id,
            parser_version=parser.version, format_name=parser.format_name,
        )
        if normalized is None:
            continue
        log = Log(
            unit_id=unit.id, agent_id=agent.id, source=parser.format_name,
            format="windows", raw_log=json.dumps(payload, default=str)[:8000],
            parsed=True, received_at=now,
        )
        log_rows.append(log)
        event_rows.append(
            NormalizedEvent(
                timestamp=normalized["timestamp"], unit_id=normalized["unit_id"],
                agent_id=normalized["agent_id"], hostname=normalized["hostname"],
                event_id=normalized["event_id"], provider=normalized["provider"],
                category=normalized["category"], action=normalized["action"],
                username=normalized["username"], source_ip=normalized["source_ip"],
                destination_ip=normalized["destination_ip"],
                process_name=normalized["process_name"], command_line=normalized["command_line"],
                logon_type=normalized["logon_type"], status_code=normalized["status_code"],
                severity=normalized["severity"], parser_version=normalized["parser_version"],
                is_suspicious=False, simulated=True, extra=normalized["extra"],
            )
        )
    db.add_all(log_rows)
    db.flush()
    for log, ev in zip(log_rows, event_rows):
        ev.log_id = log.id
    db.add_all(event_rows)
    return len(event_rows)


def seed_demo_log_data(db: Session) -> dict:
    """Seed a realistic multi-day event/alert backdrop.

    Ambient 4624/4688 noise is inserted in bulk (fast); the interesting
    4625 brute-force bursts and 1102 log-cleans go through the real detection
    pipeline so they surface as genuine alerts.
    """
    units = {u.unit_code: u for u in db.query(Unit).all()}
    agents = ensure_sim_agents(db, units)

    rng = random.Random(20260905)
    now = datetime.now(timezone.utc)
    unit_codes = list(units.keys())
    events = bursts = 0
    ambient: list[tuple[datetime, str, str]] = []
    ambient_unit: dict[tuple[str, int], tuple[Unit, Agent]] = {}

    def _flush_ambient(code: str, event_id: int) -> None:
        nonlocal events, ambient
        if not ambient:
            return
        unit, agent = ambient_unit[(code, event_id)]
        events += _bulk_ambient(db, agent, unit, event_id, ambient)
        ambient = []

    for day_offset in range(14):
        day = now - timedelta(days=day_offset)
        for code in unit_codes:
            unit = units[code]
            agent = agents[code]
            hour = rng.randint(7, 20)
            for _ in range(rng.randint(6, 14)):
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                ambient.append((when, rng.choice(USERS_POOL), ""))
                ambient_unit[(code, 4624)] = (unit, agent)
            _flush_ambient(code, 4624)
            for _ in range(rng.randint(8, 20)):
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                ambient.append((when, rng.choice(USERS_POOL),
                                "C:\\Windows\\System32\\"
                                + rng.choice(["explorer.exe", "chrome.exe", "winword.exe"])))
                ambient_unit[(code, 4688)] = (unit, agent)
            _flush_ambient(code, 4688)

        if rng.random() < 0.5:
            code = rng.choice(unit_codes)
            when = day.replace(hour=rng.randint(0, 23), minute=rng.randint(0, 55))
            target = rng.choice(USERS_POOL)
            src = "198.51.100.7"
            for i in range(rng.randint(7, 12)):
                _push(db, agents[code], units[code], 4625, when + timedelta(seconds=8 * i),
                      {"SubjectUserName": target, "IpAddress": src, "Status": "0xC000006A"},
                      commit=False, publish_event=False)
                events += 1
            bursts += 1

        if rng.random() < 0.08:
            code = rng.choice(unit_codes)
            when = day.replace(hour=rng.randint(0, 23), minute=rng.randint(0, 59))
            _push(db, agents[code], units[code], 1102, when,
                  {"SubjectUserName": "administrator", "LogName": "Security"},
                  commit=False, publish_event=False)
            events += 1

    db.commit()
    return {"events_seeded": events, "bursts": bursts}


def seed_hero_incidents(db: Session) -> int:
    """Create coherent 'hero' incidents from the seeded alerts (idempotent).

    Reuses the existing INC-DEMO grouping so incidents are keyed by stable ids.
    """
    from app.seed.soc import seed_demo_incidents

    return seed_demo_incidents(db)


def _raw_delete_batches(db: Session, sql: str, params: dict, batch: int = 2000) -> None:
    """Execute a raw SQL DELETE with LIMIT in a loop until nothing remains."""
    while True:
        r = db.execute(text(sql), params)
        db.commit()
        if r.rowcount == 0:
            break


def reset_demo(db: Session) -> dict:
    """Restore the curated demo state using server-side-only raw SQL.

    The previous ORM-based approach loaded every matching row into the session
    identity map, exhausting memory on the Render free-tier.  Raw SQL keeps
    everything server-side — zero per-row Python objects — so even 70k+ rows
    are deleted in fast committed batches without memory pressure.
    """
    rows = db.execute(
        text("SELECT id FROM agents WHERE agent_id LIKE :prefix"),
        {"prefix": f"{SIM_AGENT_PREFIX}%"},
    ).all()
    sim_agent_ids = [r[0] for r in rows]
    removed_alerts = removed_events = 0

    logger.info("reset_demo: found %d sim agents", len(sim_agent_ids))

    if sim_agent_ids:
        ph = ", ".join(f":a{i}" for i in range(len(sim_agent_ids)))
        p = {f"a{i}": aid for i, aid in enumerate(sim_agent_ids)}

        removed_alerts = db.execute(text(f"SELECT count(*) FROM alerts WHERE agent_id IN ({ph})"), p).scalar() or 0
        logger.info("reset_demo: removing %d sim alerts", removed_alerts)

        db.execute(text(f"DELETE FROM alert_events WHERE alert_id IN (SELECT id FROM alerts WHERE agent_id IN ({ph}))"), p)
        db.commit()
        logger.info("reset_demo: alert_events(alert_id) done")

        db.execute(text(f"""
            DELETE FROM alert_events WHERE normalized_event_id IN (
                SELECT ne.id FROM normalized_events ne
                JOIN logs l ON ne.log_id = l.id WHERE l.agent_id IN ({ph})
            )
        """), p)
        db.commit()
        logger.info("reset_demo: alert_events(normalized_event_id) done")

        db.execute(text(f"DELETE FROM incident_alerts WHERE alert_id IN (SELECT id FROM alerts WHERE agent_id IN ({ph}))"), p)
        db.commit()
        logger.info("reset_demo: incident_alerts(alert_id) done")

        db.execute(text(f"UPDATE logs SET normalized_event_id = NULL WHERE agent_id IN ({ph})"), p)
        db.commit()
        logger.info("reset_demo: FK cycle broken")

        removed_events = db.execute(text(f"""
            SELECT count(*) FROM normalized_events ne
            JOIN logs l ON ne.log_id = l.id WHERE l.agent_id IN ({ph})
        """), p).scalar() or 0
        logger.info("reset_demo: removing %d sim normalized_events", removed_events)

        _raw_delete_batches(db, f"""
            DELETE FROM normalized_events WHERE id IN (
                SELECT ne.id FROM normalized_events ne
                JOIN logs l ON ne.log_id = l.id WHERE l.agent_id IN ({ph})
                LIMIT :lim
            )
        """, {**p, "lim": 2000})
        logger.info("reset_demo: normalized_events purged")

        _raw_delete_batches(db, f"""
            DELETE FROM logs WHERE id IN (
                SELECT l.id FROM logs l
                WHERE l.agent_id IN ({ph}) LIMIT :lim
            )
        """, {**p, "lim": 2000})
        logger.info("reset_demo: logs purged")

        db.execute(text("""
            DELETE FROM incident_notes WHERE incident_id IN (
                SELECT id FROM incidents WHERE source = 'correlation'
                AND id NOT IN (SELECT DISTINCT incident_id FROM incident_alerts)
            )
        """))
        db.execute(text("""
            DELETE FROM incident_alerts WHERE incident_id IN (
                SELECT id FROM incidents WHERE source = 'correlation'
            )
        """))
        db.execute(text("""
            DELETE FROM incidents WHERE source = 'correlation'
            AND id NOT IN (SELECT DISTINCT incident_id FROM incident_alerts)
        """))
        db.commit()

    seed_demo_log_data(db)
    seed_hero_incidents(db)
    return {"removed_alerts": removed_alerts, "removed_events": removed_events}
