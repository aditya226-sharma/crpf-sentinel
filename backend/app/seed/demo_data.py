"""Realistic synthetic demo-data generator.

ALL DATA IS SYNTHETIC. No real CRPF operational information is used.
Units, hostnames, IPs and usernames are fictional demonstration values.
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.agent import Agent
from app.models.event import NormalizedEvent
from app.models.log import Log
from app.models.unit import Unit
from app.models.user import User
from app.normalization.engine import EVENT_CLASSIFICATION
from app.services.ingest import ingest_payload

UNITS = [
    ("UNIT-01", "Delhi Unit", "North", "New Delhi", "Delhi", 28.6139, 77.2090, 61),
    ("UNIT-02", "Gujarat Unit", "West", "Ahmedabad", "Gujarat", 23.0225, 72.5714, 42),
    ("UNIT-03", "Rajasthan Unit", "North-West", "Jaipur", "Rajasthan", 26.9124, 75.7873, 28),
    ("UNIT-04", "Maharashtra Unit", "West", "Mumbai", "Maharashtra", 19.0760, 72.8777, 34),
    ("UNIT-05", "Uttar Pradesh Unit", "North", "Lucknow", "Uttar Pradesh", 26.8467, 80.9462, 25),
    ("UNIT-06", "Karnataka Unit", "South", "Bengaluru", "Karnataka", 12.9716, 77.5946, 18),
    ("UNIT-07", "West Bengal Unit", "East", "Kolkata", "West Bengal", 22.5726, 88.3639, 20),
    ("UNIT-08", "Punjab Unit", "North", "Amritsar", "Punjab", 31.6340, 74.8723, 16),
]

USERS_POOL = ["administrator", "s.verma", "r.kapoor", "a.singh", "m.khan", "p.nair", "k.gupta"]
SOURCE_POOL = ["203.0.113.14", "198.51.100.7", "192.0.2.55", "10.20.10.45", "10.20.30.41"]


def _hostname(unit_code: str, index: int) -> str:
    num = unit_code.split("-")[1]
    return f"CRPF-PC-{int(num):03d}-{index:03d}"


def _structured_payload(
    event_id: int,
    computer: str,
    when: datetime,
    data: dict | None = None,
) -> dict:
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


def seed_units(db: Session) -> dict[str, Unit]:
    units: dict[str, Unit] = {}
    for code, name, region, city, state, lat, lon, _ in UNITS:
        unit = db.query(Unit).filter(Unit.unit_code == code).first()
        if unit is None:
            unit = Unit(
                id=uuid.uuid4().hex[:16],
                unit_code=code,
                name=name,
                region=region,
                city=city,
                state=state,
                latitude=lat,
                longitude=lon,
                status="operational",
            )
            db.add(unit)
            db.flush()
        units[code] = unit
    db.commit()
    return units


def seed_agents(db: Session, units: dict[str, Unit], agent_count: int = 0) -> list[Agent]:
    agents: list[Agent] = []
    versions = ["10.0.19045 (Windows 10)", "10.0.22631 (Windows 11)", "10.0.20348 (Server 2022)"]
    for code, _, _, _, _, _, _, count in UNITS:
        unit = units[code]
        for i in range(1, count + 1):
            agent_id = f"WIN-AGT-{code.split('-')[1]}-{i:03d}"
            existing = db.query(Agent).filter(Agent.agent_id == agent_id).first()
            if existing:
                agents.append(existing)
                continue
            agent = Agent(
                id=uuid.uuid4().hex[:16],
                agent_id=agent_id,
                unit_id=unit.id,
                hostname=_hostname(code, i),
                ip_address=f"10.{int(code.split('-')[1]):02d}.10.{i}",
                os_version=random.choice(versions),
                agent_version="1.0.0",
                status="online",
                last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=random.randint(3, 60)),
                events_per_sec=random.randint(2, 60),
                cpu_usage=round(random.uniform(3, 65), 1),
                memory_usage=round(random.uniform(25, 88), 1),
                is_enabled=True,
            )
            db.add(agent)
            db.flush()
            agents.append(agent)
    db.commit()
    return agents


def seed_demo_users(db: Session, units: dict[str, Unit], roles) -> list[User]:
    users = []
    if not db.query(User).filter(User.username == "analyst").first():
        analyst = User(
            id=uuid.uuid4().hex[:16],
            username="analyst",
            email="analyst@cyberrakshak.demo",
            full_name="Security Analyst",
            password_hash=hash_password("Analyst@123"),
            role_id=roles["security_expert"].id,
            is_active=True,
        )
        db.add(analyst)
        users.append(analyst)
    if not db.query(User).filter(User.username == "unitadmin").first():
        unit_admin = User(
            id=uuid.uuid4().hex[:16],
            username="unitadmin",
            email="unitadmin@cyberrakshak.demo",
            full_name="Delhi Unit Administrator",
            password_hash=hash_password("UnitAdmin@123"),
            role_id=roles["unit_admin"].id,
            unit_id=units["UNIT-01"].id,
            is_active=True,
        )
        db.add(unit_admin)
        users.append(unit_admin)
    db.commit()
    return users


def _bulk_normal_event(
    db: Session,
    unit: Unit,
    agent: Agent,
    event_id: int,
    when: datetime,
    username: str | None,
    source_ip: str | None,
    command_line: str | None = None,
):
    now = datetime.now(timezone.utc)
    when = min(when, now)
    category, action, severity = EVENT_CLASSIFICATION.get(event_id, ("unknown", "observed", "informational"))
    payload = _structured_payload(
        event_id, agent.hostname, when,
        data={
            "SubjectUserName": username,
            "TargetUserName": username,
            "IpAddress": source_ip,
            "LogonType": "3",
            "NewProcessName": f"C:\\Windows\\System32\\{command_line or 'svchost.exe'}",
            "CommandLine": command_line or "C:\\Windows\\System32\\svchost.exe -k netsvcs",
        },
    )
    log_row = Log(
        unit_id=unit.id,
        agent_id=agent.id,
        source="windows",
        format="json",
        raw_log=json.dumps(payload)[:8000],
        parsed=True,
        received_at=when,
    )
    db.add(log_row)
    db.flush()
    event_row = NormalizedEvent(
        log_id=log_row.id,
        timestamp=when,
        unit_id=unit.id,
        agent_id=agent.id,
        hostname=agent.hostname,
        event_id=event_id,
        provider=payload["System"]["Provider"]["Name"],
        category=category,
        action=action,
        username=username,
        source_ip=source_ip,
        severity=severity,
        parser_version="1.0",
        is_suspicious=False,
    )
    db.add(event_row)
    log_row.normalized_event_id = event_row.id
    return event_row


def _run_attack_through_pipeline(
    db: Session,
    agent: Agent,
    unit: Unit,
    events: list[dict],
):
    """Push raw event dicts through the real parse→normalize→detect pipeline."""
    now = datetime.now(timezone.utc)
    for ev in events:
        payload = _structured_payload(ev["event_id"], agent.hostname, min(ev["when"], now), ev.get("data") or {})
        ingest_payload(db, payload, agent=agent, unit=unit)


def seed_demo_data(
    db: Session,
    units: dict[str, Unit],
    agents: list[Agent],
    days: int = 30,
) -> dict:
    agents_by_unit: dict[str, list[Agent]] = {}
    for agent in agents:
        agents_by_unit.setdefault(agent.unit_id, []).append(agent)

    now = datetime.now(timezone.utc)
    rng = random.Random(20260810)
    events_created = 0
    bursts_created = 0

    for day_offset in range(days):
        day = now - timedelta(days=day_offset)
        for unit in units.values():
            unit_agents = agents_by_unit[unit.id]
            if not unit_agents:
                continue
            hour = rng.randint(7, 22)

            # Normal successful logons
            for _ in range(rng.randint(8, 20)):
                agent = rng.choice(unit_agents)
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _bulk_normal_event(
                    db, unit, agent, 4624, when,
                    username=rng.choice(USERS_POOL), source_ip="10.0.0.0/8" if rng.random() > 0.5 else None,
                )
                events_created += 1

            # Normal process creation
            for _ in range(rng.randint(15, 40)):
                agent = rng.choice(unit_agents)
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _bulk_normal_event(
                    db, unit, agent, 4688, when,
                    username=rng.choice(USERS_POOL), source_ip=None,
                    command_line=rng.choice([
                        "explorer.exe", "chrome.exe", "winword.exe", "outlook.exe", "notepad.exe",
                    ]),
                )
                events_created += 1

            # Scattered failed logons (no burst, below threshold)
            for _ in range(rng.randint(0, 4)):
                agent = rng.choice(unit_agents)
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _bulk_normal_event(
                    db, unit, agent, 4625, when,
                    username=rng.choice(USERS_POOL), source_ip=rng.choice(SOURCE_POOL),
                )
                events_created += 1

            # Occasional service installs
            if rng.random() < 0.06:
                agent = rng.choice(unit_agents)
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _run_attack_through_pipeline(db, agent, unit, [
                    {
                        "event_id": 7045, "when": when,
                        "data": {
                            "ServiceName": "CRPFUpdateSvc",
                            "ImagePath": "C:\\Windows\\System32\\svchost.exe -k netsvcs",
                        },
                    }
                ])
                bursts_created += 1

            # Occasional user creation
            if rng.random() < 0.03:
                agent = rng.choice(unit_agents)
                when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                _run_attack_through_pipeline(db, agent, unit, [
                    {"event_id": 4720, "when": when, "data": {"NewAccountName": "temp_user", "SubjectUserName": "administrator"}}
                ])
                bursts_created += 1

        # A few brute force bursts per 30 days
        if rng.random() < 0.18:
            unit = rng.choice(list(units.values()))
            agent = rng.choice(agents_by_unit[unit.id])
            when = day.replace(hour=hour, minute=rng.randint(0, 55))
            target_user = rng.choice(USERS_POOL)
            source_ip = rng.choice(SOURCE_POOL[:3])
            attempts = rng.randint(8, 16)
            events = [
                {
                    "event_id": 4625,
                    "when": when + timedelta(seconds=10 * i),
                    "data": {"SubjectUserName": target_user, "IpAddress": source_ip, "Status": "0xC000006A", "SubStatus": "0xC0000064"},
                }
                for i in range(attempts)
            ]
            if rng.random() < 0.4:
                events.append({
                    "event_id": 4624, "when": when + timedelta(seconds=10 * (attempts + 2)),
                    "data": {"SubjectUserName": target_user, "IpAddress": source_ip, "LogonType": "3"},
                })
            _run_attack_through_pipeline(db, agent, unit, events)
            bursts_created += 1

        # A couple of audit log clears over 30 days
        if rng.random() < 0.035:
            unit = rng.choice(list(units.values()))
            agent = rng.choice(agents_by_unit[unit.id])
            when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
            _run_attack_through_pipeline(db, agent, unit, [
                {"event_id": 1102, "when": when, "data": {"SubjectUserName": "administrator", "LogName": "Security"}}
            ])
            bursts_created += 1

        # Suspicious PowerShell every few days
        if rng.random() < 0.05:
            unit = rng.choice(list(units.values()))
            agent = rng.choice(agents_by_unit[unit.id])
            when = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
            _run_attack_through_pipeline(db, agent, unit, [
                {
                    "event_id": 4688, "when": when,
                    "data": {
                        "SubjectUserName": "administrator",
                        "NewProcessName": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                        "CommandLine": "powershell.exe -nop -w hidden -enc SQBFAFgAKAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkA",
                    },
                }
            ])
            bursts_created += 1

    db.commit()
    return {
        "events_created": events_created,
        "attack_bursts": bursts_created,
    }


def mark_demo_risk(db: Session) -> None:
    """Set unit status/risk hints from generated alerts (informational only)."""
    db.commit()
