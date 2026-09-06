"""Traffic anomaly detector for network flows.

Rule-based baseline over Flow rows in a sliding window (NO machine learning —
explainable thresholds only):
  - rate:  too many flows from one source in the window,
  - fan-out: one source talking to too many distinct destinations,
  - entropy proxy: too many distinct destination ports (port-scan signature).

Alerts are written through the shared ``alert_writer`` into the existing
``Alert`` model, so they surface on the Alerts page without frontend changes.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.detection.alert_writer import get_or_create_rule, write_analysis_alert
from app.models.flow import Flow

RULE_DEF = {
    "rule_id": "RULE-NET-001",
    "name": "Traffic Anomaly: Possible DDoS / Network Scan",
    "description": "A single source produced an abnormal burst of flows: high "
    "flow rate, high destination fan-out, or a port-scan-like distribution.",
    "category": "network",
    "severity": "high",
    "event_id": 3001,
    "mitre_technique": "T1498",
    "mitre_name": "Network Denial of Service",
}

WINDOW_SECONDS = 60
RATE_THRESHOLD = 100          # flows from one source within the window
FANOUT_THRESHOLD = 30         # distinct destinations from one source
PORT_SCAN_THRESHOLD = 40      # distinct destination ports from one source


def detect_flow_burst(
    db: Session,
    event: dict,
    event_row_id: int | None,
) -> list[object]:
    """Evaluate the current flow window for anomalous behavior."""
    source_ip = event.get("source_ip")
    if not source_ip:
        return []

    since = event.get("timestamp") or datetime.now(timezone.utc)
    if isinstance(since, datetime):
        window_start = since - timedelta(seconds=WINDOW_SECONDS)
    else:
        window_start = datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)

    base = db.query(Flow).filter(Flow.source_ip == source_ip, Flow.timestamp >= window_start)

    rate = base.count()
    fanout = base.with_entities(func.count(func.distinct(Flow.destination_ip))).scalar() or 0
    ports = base.with_entities(func.count(func.distinct(Flow.destination_port))).scalar() or 0

    reasons: list[dict] = []
    if rate >= RATE_THRESHOLD:
        reasons.append({"label": "traffic anomaly (flow rate)", "points": min(30, rate // 5)})
    if fanout >= FANOUT_THRESHOLD:
        reasons.append({"label": "traffic anomaly (destination fan-out)", "points": 25})
    if ports >= PORT_SCAN_THRESHOLD:
        reasons.append({"label": "traffic anomaly (port distribution)", "points": 20})
    if not reasons:
        return []

    rule = get_or_create_rule(db, RULE_DEF)
    detail = f"{rate} flows from {source_ip} to {fanout} destinations on {ports} ports in the last {WINDOW_SECONDS}s"
    alert = write_analysis_alert(
        db,
        rule=rule,
        event=event,
        event_row_id=event_row_id,
        explanation=f"Traffic anomaly detected: {detail}",
        severity=RULE_DEF["severity"],
        risk_factors=reasons,
        source_ip=source_ip,
        correlation_key=f"traffic:{source_ip}",
        mitre=(RULE_DEF.get("mitre_technique"), RULE_DEF.get("mitre_name")),
    )
    return [alert]