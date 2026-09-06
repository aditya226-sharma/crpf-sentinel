"""Transparent risk scoring engine.

Every point is explainable and returned to the UI as a list of factors.
"""

from app.normalization.engine import is_privileged_user, is_public_ip

SEVERITY_BASE = {
    "critical": 90,
    "high": 70,
    "medium": 40,
    "low": 15,
    "informational": 5,
}


def compute_risk_score(
    severity: str,
    event_count: int = 1,
    username: str | None = None,
    source_ip: str | None = None,
    event_id: int | None = None,
    correlated_success: bool = False,
    traffic_anomaly_score: int = 0,
    vpn_misconfig_score: int = 0,
) -> tuple[int, list[dict]]:
    reasons: list[dict] = []

    base = SEVERITY_BASE.get(severity.lower(), 20)
    reasons.append({"label": f"Base severity ({severity})", "points": base})
    score = base

    if event_id in (4625, 4624) or severity in ("critical", "high"):
        if event_count >= 15:
            points = 30
            label = "repeated authentication failures"
        elif event_count >= 5:
            points = 20
            label = "multiple authentication failures"
        elif event_count > 1:
            points = 10
            label = "repeated events"
        else:
            points = 0
            label = None
        if label:
            score += points
            reasons.append({"label": label, "points": points})

    if is_privileged_user(username):
        points = 25
        score += points
        reasons.append({"label": "privileged account", "points": points})

    if is_public_ip(source_ip):
        points = 20
        score += points
        reasons.append({"label": "suspicious source (public IP)", "points": points})

    if correlated_success:
        points = 12
        score += points
        reasons.append({"label": "correlated successful login", "points": points})

    if traffic_anomaly_score:
        score += traffic_anomaly_score
        reasons.append({"label": "traffic anomaly detected", "points": traffic_anomaly_score})
    if vpn_misconfig_score:
        score += vpn_misconfig_score
        reasons.append({"label": "VPN misconfiguration", "points": vpn_misconfig_score})

    score = max(0, min(100, score))
    return score, reasons
