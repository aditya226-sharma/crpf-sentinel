"""Background live telemetry generator for demo mode.

Periodically ingests small batches of SYNTHETIC events through the real
ingestion/detection pipeline so the Live Events stream and other real-time
views keep receiving data. All data is fictional — no real systems involved.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from app.database.session import SessionLocal
from app.models.agent import Agent
from app.models.unit import Unit
from app.services.ingest import ingest_payload
from app.simulation.scenarios import _payload

logger = logging.getLogger("cyberrakshak.live")

INTERVAL_SECONDS = 4
BURST_PROBABILITY = 0.3

USERS = ["administrator", "s.verma", "a.singh", "n.rao", "p.malhotra", "r.tiwari"]
SOURCES = ["203.0.113.77", "198.51.100.33", "192.0.2.101", "10.20.1.15", "10.40.3.88"]

_BENIGN_EVENTS = [
    lambda r: (4624, {"SubjectUserName": r.choice(USERS), "IpAddress": r.choice(SOURCES), "LogonType": r.choice([2, 3, 8])}),
    lambda r: (4634, {"SubjectUserName": r.choice(USERS), "LogonType": r.choice([2, 3])}),
    lambda r: (4672, {"SubjectUserName": r.choice(USERS)}),
    lambda r: (4688, {"SubjectUserName": r.choice(USERS), "NewProcessName": "C:\\Windows\\System32\\cmd.exe", "CommandLine": "cmd.exe /c net use \\\\server\\share"}),
    lambda r: (4663, {"SubjectUserName": r.choice(USERS), "ObjectName": "C:\\shared\\report.xlsx", "AccessMask": "0x1"}),
    lambda r: (4799, {"SubjectUserName": r.choice(USERS), "TargetUserName": "S-1-5-32-544"}),
    lambda r: (4732, {"SubjectUserName": r.choice(USERS), "TargetUserName": "S-1-5-32-544"}),
    lambda r: (4726, {"SubjectUserName": r.choice(USERS), "TargetUserName": "legacy.user"}),
]

_SUSPICIOUS_EVENTS = [
    lambda r: (4625, {"SubjectUserName": r.choice(USERS), "IpAddress": r.choice(SOURCES), "Status": "0xC000006A", "SubStatus": "0xC0000064"}),
    lambda r: (7045, {"ServiceName": "RemoteAdminSvc", "ImagePath": "C:\\Windows\\Temp\\remadmin.exe"}),
    lambda r: (4720, {"NewAccountName": "svc_temp", "SubjectUserName": "administrator"}),
    lambda r: (4688, {"SubjectUserName": r.choice(USERS), "NewProcessName": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "CommandLine": "powershell.exe -nop -w hidden -enc SQBFAFgAKAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkA"}),
    lambda r: (1102, {"SubjectUserName": r.choice(USERS), "LogName": "Security"}),
    lambda r: (4648, {"SubjectUserName": r.choice(USERS), "IpAddress": r.choice(SOURCES), "TargetServerName": "\\\\(10.0.0.9)"}),
]


def _generate_batch() -> None:
    db = SessionLocal()
    try:
        agents = db.query(Agent).all()
        if not agents:
            return
        rng = random.Random()
        burst = rng.random() < BURST_PROBABILITY
        count = rng.randint(4, 6) if burst else rng.randint(2, 4)
        pool = _SUSPICIOUS_EVENTS if burst else _BENIGN_EVENTS
        now = datetime.now(timezone.utc)
        for _ in range(count):
            agent = rng.choice(agents)
            unit = db.query(Unit).filter(Unit.id == agent.unit_id).first()
            event_id, data = rng.choice(pool)(rng)
            when = now - timedelta(seconds=rng.randint(0, 20))
            payload = _payload(event_id, agent.hostname, when, data)
            try:
                ingest_payload(db, payload, agent=agent, unit=unit)
            except Exception:
                db.rollback()
                break
    except Exception as exc:  # keep the generator alive across failures
        logger.warning("live demo batch failed: %s", exc)
    finally:
        db.close()


async def start_live_demo() -> None:
    while True:
        _generate_batch()
        await asyncio.sleep(INTERVAL_SECONDS)
