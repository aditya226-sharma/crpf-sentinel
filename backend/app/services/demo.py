"""Demo automation: realistic seed data + scripted attack simulation + reset.

ALL DATA IS SYNTHETIC. Everything generated here describes fictional CRPF
units, hosts, users and incidents for the SIH26156 demonstration. No real
operational information is used.

The simulate and seed paths push raw event payloads through the SAME pipeline
as real agents (ParserRegistry -> normalize -> detection engine -> risk
scoring), so a judge asking "is this actually running?" always gets an honest
"yes — this is the real detection path".
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

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
from app.services.ingest import ingest_payload

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


def seed_demo_log_data(db: Session) -> dict:
    """Seed a realistic multi-day event/alert backdrop via the real pipeline."""
    units = {u.unit_code: u for u in db.query(Unit).all()}
    agents = ensure_sim_agents(db, units)

    rng = random.Random(20260905)
    now = datetime.now(timezone.utc)
    unit_codes = list(units.keys())
    events = bursts = 0

    for day_offset in range(14):
        day = now - timedelta(days=day_offset)
        for code in unit_codes:
            unit = units[code]
            agent = agents[code]
            hour = rng.randint(7, 20)
            for _ in range(rng.randint(6, 14)):
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _push(db, agent, unit, 4624, when,
                      {"SubjectUserName": rng.choice(USERS_POOL), "IpAddress": "10.0.0.8", "LogonType": "3"},
                      commit=False, publish_event=False)
                events += 1
            for _ in range(rng.randint(8, 20)):
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _push(db, agent, unit, 4688, when,
                      {"SubjectUserName": rng.choice(USERS_POOL),
                       "NewProcessName": "C:\\Windows\\System32\\"
                       + rng.choice(["explorer.exe", "chrome.exe", "winword.exe"]),
                       "CommandLine": "C:\\Windows\\System32\\svchost.exe -k netsvcs"},
                      commit=False, publish_event=False)
                events += 1

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


def reset_demo(db: Session) -> dict:
    """Restore the curated demo state: remove simulated artifacts and reseed."""
    sim_agent_ids = [
        a.id for a in db.query(Agent).filter(Agent.agent_id.like(f"{SIM_AGENT_PREFIX}%")).all()
    ]
    removed_alerts = removed_events = 0

    if sim_agent_ids:
        alert_ids = [
            a.id for a in db.query(Alert).filter(Alert.agent_id.in_(sim_agent_ids)).all()
        ]
        sim_logs = db.query(Log).filter(Log.agent_id.in_(sim_agent_ids)).all()
        log_ids = [l.id for l in sim_logs]
        # Normalized events created alongside the sim logs (deadlock-free child-first).
        # Look them up by log_id — ingest-created logs carry a null back-link.
        ne_ids = [
            nid for (nid,) in db.query(NormalizedEvent.id)
            .filter(NormalizedEvent.log_id.in_(log_ids))
            .all()
        ] if log_ids else []

        # 1) Children of alerts: alert<->events and alert<->incidents.
        if alert_ids:
            db.query(AlertEvent).filter(AlertEvent.alert_id.in_(alert_ids)).delete(synchronize_session=False)
            db.query(IncidentAlert).filter(IncidentAlert.alert_id.in_(alert_ids)).delete(synchronize_session=False)
            removed_alerts = len(alert_ids)

        # 2) Any event-correlation alert links that point at the sim normalized events.
        if ne_ids:
            db.query(AlertEvent).filter(AlertEvent.normalized_event_id.in_(ne_ids)).delete(synchronize_session=False)

        # 3) Release the FK from logs -> normalized_events before deleting either.
        if ne_ids:
            db.query(Log).filter(Log.normalized_event_id.in_(ne_ids)).update(
                {"normalized_event_id": None}, synchronize_session=False
            )

        # 4) Delete the alerts, then the normalized events, then the logs.
        if alert_ids:
            db.query(Alert).filter(Alert.id.in_(alert_ids)).delete(synchronize_session=False)
        if ne_ids:
            db.query(NormalizedEvent).filter(NormalizedEvent.id.in_(ne_ids)).delete(synchronize_session=False)
            removed_events = len(ne_ids)
        if log_ids:
            db.query(Log).filter(Log.id.in_(log_ids)).delete(synchronize_session=False)

        # Drop incidents that were purely created from simulated alerts.
        # Subquery fresh from the DB (identity map may hold stale rows).
        linked_incident_ids = (
            db.query(IncidentAlert.incident_id).distinct().subquery()
        )
        orphan_incidents = (
            db.query(Incident.id)
            .filter(Incident.source == "correlation", Incident.id.notin_(linked_incident_ids))
            .with_for_update()
            .all()
        )
        orphan_incident_ids = [iid for (iid,) in orphan_incidents]
        if orphan_incident_ids:
            db.query(IncidentAlert).filter(
                IncidentAlert.incident_id.in_(orphan_incident_ids)
            ).delete(synchronize_session=False)
            db.query(IncidentNote).filter(
                IncidentNote.incident_id.in_(orphan_incident_ids)
            ).delete(synchronize_session=False)
            db.query(Incident).filter(
                Incident.id.in_(orphan_incident_ids)
            ).delete(synchronize_session=False)

        db.commit()

    # Recreate the curated backdrop.
    seed_demo_log_data(db)
    seed_hero_incidents(db)
    return {"removed_alerts": removed_alerts, "removed_events": removed_events}
