"""Seed demo incidents and IOC library entries.

ALL DATA IS SYNTHETIC. No real CRPF operational information is used.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.incident import Incident, IncidentAlert, IncidentNote
from app.models.ioc import IocEntry
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.models.user import User


def seed_iocs(db: Session) -> int:
    """Seed a small demonstration IOC library. Returns count of new entries."""
    admin = db.query(User).filter(User.username == "admin").first()
    creator = admin.id if admin else None

    demo_iocs = [
        {"ioc_type": "ip", "value": "203.0.113.14", "description": "Known scanning source observed in demo feed", "source": "demo-feed", "severity": "high", "threat_type": "scanner"},
        {"ioc_type": "ip", "value": "198.51.100.7", "description": "Historical brute-force source", "source": "demo-feed", "severity": "high", "threat_type": "brute_force"},
        {"ioc_type": "ip", "value": "192.0.2.55", "description": "Suspicious inbound source", "source": "demo-feed", "severity": "medium", "threat_type": "suspicious"},
        {"ioc_type": "domain", "value": "payload.delivery.example", "description": "C2 delivery domain (synthetic)", "source": "demo-feed", "severity": "high", "threat_type": "c2"},
        {"ioc_type": "command", "value": "powershell.exe -nop -w hidden -enc", "description": "Encoded PowerShell download cradle pattern", "source": "demo-feed", "severity": "high", "threat_type": "execution"},
        {"ioc_type": "hash", "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "description": "Synthetic file hash (empty payload)", "source": "manual", "severity": "low", "threat_type": "hash"},
        {"ioc_type": "url", "value": "http://malicious.download.example/bob.exe", "description": "Synthetic malware download URL", "source": "demo-feed", "severity": "high", "threat_type": "download"},
    ]

    created = 0
    for spec in demo_iocs:
        exists = (
            db.query(IocEntry)
            .filter(IocEntry.ioc_type == spec["ioc_type"], IocEntry.value == spec["value"])
            .first()
        )
        if exists:
            continue
        db.add(
            IocEntry(
                id=uuid.uuid4().hex[:16],
                ioc_id=f"IOC-DEMO-{created + 1:03d}",
                created_by=creator,
                **spec,
            )
        )
        created += 1
    db.commit()
    return created


def seed_demo_incidents(db: Session) -> int:
    """Create demo incidents grouping open alerts. Returns number created.

    Additive and idempotent: each group is keyed by a stable ``incident_id``
    and is only created if it does not already exist, so re-seeding on every
    startup fills in missing incidents as the simulator accumulates alerts.
    """
    units = {u.id: u for u in db.query(Unit).all()}
    admin = db.query(User).filter(User.username == "admin").first()
    created_by = admin.id if admin else None
    now = datetime.now(timezone.utc)

    rules_by_id = {r.id: r for r in db.query(DetectionRule).all()}

    groups = [
        {
            "incident_id": "INC-DEMO-001",
            "title": "Unexpected Service Installation on Monitored Host",
            "category": "service_installation",
            "rule_substring": "RULE-SVC-001",
            "severity": "high",
            "status": "investigating",
            "description": (
                "A new Windows service was registered on a monitored host "
                "outside of any scheduled maintenance window. The service "
                "binary hash does not match the approved software baseline, "
                "suggesting possible persistence by an unauthorized actor."
            ),
        },
        {
            "incident_id": "INC-DEMO-002",
            "title": "Credential Compromise — Brute Force Followed by Successful Logon",
            "category": "authentication",
            "rule_substring": "RULE-AUTH-002",
            "severity": "critical",
            "status": "investigating",
            "description": (
                "A host recorded multiple failed logon attempts followed by "
                "a successful logon from the same source. This sequence "
                "strongly suggests the account credentials were compromised "
                "during a brute force attack."
            ),
        },
        {
            "incident_id": "INC-DEMO-003",
            "title": "Security Audit Log Tampering",
            "category": "security_audit",
            "rule_substring": "RULE-AUDIT-001",
            "severity": "critical",
            "status": "escalated",
            "description": (
                "The Windows security audit log was cleared on a critical "
                "host. Clearing audit logs is a common anti-forensics "
                "technique used by attackers to remove evidence of their "
                "activity and hinder incident response."
            ),
        },
        {
            "incident_id": "INC-DEMO-004",
            "title": "Privilege Escalation Attempt",
            "category": "privilege",
            "rule_substring": "RULE-PRIV-001",
            "severity": "high",
            "status": "investigating",
            "description": (
                "Special privileges were assigned to an account that "
                "previously held none. Unusual privilege assignment is "
                "frequently used to escalate access within the domain."
            ),
        },
        {
            "incident_id": "INC-DEMO-005",
            "title": "Lateral Movement via Credential Reuse",
            "category": "credential",
            "rule_substring": "RULE-CRED-001",
            "severity": "critical",
            "status": "triaging",
            "description": (
                "Explicit credential usage was detected on multiple hosts in "
                "quick succession. Reusing credentials across endpoints is a "
                "classic sign of lateral movement after initial compromise."
            ),
        },
        {
            "incident_id": "INC-DEMO-006",
            "title": "Suspicious PowerShell Execution",
            "category": "execution",
            "rule_substring": "RULE-PROC-001",
            "severity": "medium",
            "status": "resolved",
            "description": (
                "A PowerShell process executed with obfuscated arguments on a "
                "workstation. Investigation confirmed the command matched the "
                "synthetic demo IOC pattern; no data exfiltration was "
                "observed. Closed after validation."
            ),
        },
        {
            "incident_id": "INC-DEMO-007",
            "title": "New Account Created in Sensitive Unit",
            "category": "account",
            "rule_substring": "RULE-ACCT-001",
            "severity": "medium",
            "status": "open",
            "description": (
                "A new user account was created on a host in a sensitive "
                "unit. Creation of accounts outside the approved HR workflow "
                "should be reviewed for possible rogue admin activity."
            ),
        },
        {
            "incident_id": "INC-DEMO-008",
            "title": "Account Added to Privileged Group",
            "category": "account",
            "rule_substring": "RULE-ACCT-002",
            "severity": "high",
            "status": "investigating",
            "description": (
                "A user account was added to a privileged local group. "
                "Unexpected group membership changes can indicate privilege "
                "escalation or a compromised account being leveraged for "
                "further access."
            ),
        },
        {
            "incident_id": "INC-DEMO-009",
            "title": "Repeated Failed Logons on Remote Unit — Password Spraying",
            "category": "authentication",
            "rule_substring": "RULE-AUTH-002",
            "severity": "high",
            "status": "investigating",
            "description": (
                "An elevated rate of failed logon events was observed on "
                "hosts in a remote unit. The volume and timing are "
                "consistent with a password spraying campaign rather than "
                "individual user error."
            ),
        },
        {
            "incident_id": "INC-DEMO-010",
            "title": "Persistence via New Service on Remote Unit",
            "category": "service_installation",
            "rule_substring": "RULE-SVC-001",
            "severity": "high",
            "status": "investigating",
            "description": (
                "A service was installed on a remote unit host outside of "
                "change control. Persistence mechanisms such as service "
                "installation allow attackers to survive reboots and "
                "maintain a foothold on the network."
            ),
        },
        {
            "incident_id": "INC-DEMO-011",
            "title": "Multiple New Accounts on Same Host",
            "category": "account",
            "rule_substring": "RULE-ACCT-001",
            "severity": "medium",
            "status": "closed",
            "description": (
                "Several new user accounts were created on the same host "
                "within a short window. Review confirmed these were "
                "provisioned as part of a legitimate batch onboarding task. "
                "Incident closed as informational."
            ),
        },
    ]

    created = 0
    for spec in groups:
        exists = db.query(Incident).filter(Incident.incident_id == spec["incident_id"]).first()
        if exists:
            continue

        rule_ids = [r.id for rid, r in rules_by_id.items() if spec["rule_substring"] in (r.rule_id or "")]
        alerts = (
            db.query(Alert)
            .filter(Alert.rule_id.in_(rule_ids) if rule_ids else False)
            .order_by(Alert.last_seen.desc())
            .limit(8)
            .all()
        )
        if not alerts:
            continue

        first = alerts[-1]
        last = alerts[0]
        status = spec["status"]

        incident = Incident(
            id=uuid.uuid4().hex[:16],
            incident_id=spec["incident_id"],
            title=spec["title"],
            description=spec["description"],
            severity=spec["severity"],
            status=status,
            category=spec["category"],
            source="correlation",
            unit_id=first.unit_id,
            hostname=first.hostname,
            source_ip=first.source_ip,
            username=first.username,
            mitre_technique=first.mitre_technique,
            mitre_name=first.mitre_name,
            alert_count=len(alerts),
            event_count=sum(a.event_count or 0 for a in alerts),
            risk_score=max(a.risk_score or 0 for a in alerts),
            assigned_to=created_by,
            created_by=created_by,
            first_seen=first.first_seen,
            last_seen=last.last_seen,
            resolved_at=last.last_seen if status == "resolved" else None,
            closed_at=last.last_seen if status == "closed" else None,
        )
        db.add(incident)
        db.flush()
        for a in alerts:
            db.add(IncidentAlert(incident_id=incident.id, alert_id=a.id, timestamp=now))
        note_content = (
            "Incident auto-created during demo seeding. Review linked alerts and timeline."
            if status in ("investigating", "triaging", "escalated", "open")
            else "Incident reviewed and closed during demo seeding. No action required."
        )
        db.add(
            IncidentNote(
                incident_id=incident.id,
                user_id=created_by,
                username=admin.username if admin else "system",
                content=note_content,
                timestamp=now,
            )
        )
        created += 1

    db.commit()
    return created
