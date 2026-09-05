"""SOC dashboard endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission, scope_unit_ids
from app.database.session import get_db
from app.models.agent import Agent
from app.models.alert import Alert
from app.models.event import NormalizedEvent
from app.models.rule import DetectionRule
from app.models.unit import Unit
from app.schemas.dashboard import DashboardSummary

router = APIRouter(tags=["dashboard"])

RANGE_SECONDS = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800, "30d": 2592000}
ONLINE_WINDOW = timedelta(seconds=120)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _recently_seen(agent: Agent, now: datetime) -> bool:
    last = agent.last_seen_at
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last <= ONLINE_WINDOW


def _bucket_expr(db: Session, period: str, model=None, time_col: str = "timestamp"):
    model = model or NormalizedEvent
    col = getattr(model, time_col)
    if db.bind.dialect.name == "postgresql":
        if period in ("1h", "6h"):
            return func.date_trunc("minute", col).label("bucket")
        if period in ("24h",):
            return func.date_trunc("hour", col).label("bucket")
        return func.date_trunc("day", col).label("bucket")
    if period in ("1h", "6h"):
        return func.strftime("%Y-%m-%d %H:%M", col).label("bucket")
    if period == "24h":
        return func.strftime("%Y-%m-%d %H", col).label("bucket")
    return func.strftime("%Y-%m-%d", col).label("bucket")


def _timeline(db: Session, period: str, unit_ids: list[str] | None) -> list[dict]:
    seconds = RANGE_SECONDS.get(period, 86400)
    since = _now() - timedelta(seconds=seconds)
    bucket = _bucket_expr(db, period)

    event_query = (
        db.query(bucket, func.count(NormalizedEvent.id))
        .filter(NormalizedEvent.timestamp >= since)
    )
    alert_query = (
        db.query(_bucket_expr(db, period, Alert, "created_at"), func.count(Alert.id))
        .filter(Alert.created_at >= since)
    )
    critical_query = (
        db.query(_bucket_expr(db, period, Alert, "created_at"), func.count(Alert.id))
        .filter(Alert.created_at >= since, Alert.severity == "critical")
    )
    if unit_ids:
        event_query = event_query.filter(NormalizedEvent.unit_id.in_(unit_ids))
        alert_query = alert_query.filter(Alert.unit_id.in_(unit_ids))
        critical_query = critical_query.filter(Alert.unit_id.in_(unit_ids))

    event_rows = dict(event_query.group_by("bucket").all())
    alert_rows = dict(alert_query.group_by("bucket").all())
    critical_rows = dict(critical_query.group_by("bucket").all())

    buckets = sorted(set(list(event_rows.keys()) + list(alert_rows.keys())))
    points = []
    for b in buckets:
        label = b.isoformat() if hasattr(b, "isoformat") else str(b)
        points.append(
            {
                "bucket": label,
                "events": event_rows.get(b, 0),
                "alerts": alert_rows.get(b, 0),
                "critical_alerts": critical_rows.get(b, 0),
            }
        )
    return points


def _severity_distribution(db: Session, unit_ids: list[str] | None) -> list[dict]:
    query = db.query(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
    if unit_ids:
        query = query.filter(Alert.unit_id.in_(unit_ids))
    counts = dict(query.all())
    total = sum(counts.values()) or 1
    return [
        {"severity": s, "count": counts.get(s, 0), "pct": round(counts.get(s, 0) / total * 100, 1)}
        for s in ["critical", "high", "medium", "low", "informational"]
    ]


def _kpi(label, value, change_pct, compare_label, detail=None, status=None):
    return {
        "label": label,
        "value": value,
        "change_pct": change_pct,
        "compare_label": compare_label,
        "detail": detail,
        "status": status,
    }


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    period: str = Query("24h"),
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unit_ids = scope_unit_ids(user)
    seconds = RANGE_SECONDS.get(period, 86400)
    since = _now() - timedelta(seconds=seconds)
    prev_since = since - timedelta(seconds=seconds)

    def scoped(q, column):
        if unit_ids:
            return q.filter(column.in_(unit_ids))
        return q

    total_events = scoped(db.query(func.count(NormalizedEvent.id)), NormalizedEvent.unit_id).scalar() or 0
    prev_events_query = db.query(func.count(NormalizedEvent.id)).filter(
        NormalizedEvent.timestamp >= prev_since, NormalizedEvent.timestamp < since
    )
    prev_events = scoped(prev_events_query, NormalizedEvent.unit_id).scalar() or 0
    event_change = _pct_change(total_events, prev_events)

    critical = db.query(func.count(Alert.id)).filter(Alert.severity == "critical")
    high = db.query(func.count(Alert.id)).filter(Alert.severity == "high")
    if unit_ids:
        critical = critical.filter(Alert.unit_id.in_(unit_ids))
        high = high.filter(Alert.unit_id.in_(unit_ids))
    critical_count = critical.scalar() or 0
    high_count = high.scalar() or 0

    agents_total = scoped(db.query(func.count(Agent.id)), Agent.unit_id).scalar() or 0
    agents_online = scoped(
        db.query(func.count(Agent.id)).filter(Agent.status == "online"), Agent.unit_id
    ).scalar() or 0
    active_pct = round(agents_online / agents_total * 100, 1) if agents_total else 0

    units_total = scoped(db.query(func.count(Unit.id)), Unit.id).scalar() or 0

    live_events = _live_events(db, unit_ids, limit=12)
    active_threats = _active_threats(db, unit_ids, limit=6)
    units_overview = _unit_overview(db, unit_ids)
    agent_health = _agent_health(db, unit_ids, limit=8)
    top_rules = _top_rules(db, unit_ids, since, limit=5)

    return DashboardSummary(
        total_events=_kpi("Total Events", total_events, event_change, f"vs previous {period}", detail="Normalized events ingested"),
        critical_alerts=_kpi("Critical Alerts", critical_count, None, "period total", detail="Severity: critical", status="critical" if critical_count else "ok"),
        high_alerts=_kpi("High Severity Alerts", high_count, None, "period total", detail="Severity: high", status="high" if high_count else "ok"),
        active_agents=_kpi("Active Agents", f"{agents_online} / {agents_total}", active_pct, "online / total", detail="Heartbeat received in the last 120s"),
        monitored_units=_kpi("Monitored Units", units_total, None, "all units", detail="Deployed CRPF units", status="ok"),
        risk_score=_kpi("Current Risk Score", _platform_risk(db, unit_ids), None, "computed", detail="Weighted from open alerts"),
        timeline=_timeline(db, period, unit_ids),
        severity=_severity_distribution(db, unit_ids),
        live_events=live_events,
        active_threats=active_threats,
        units=units_overview,
        agent_health=agent_health,
        top_rules=top_rules,
        generated_at=_now(),
    )


def _pct_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _live_events(db: Session, unit_ids: list[str] | None, limit: int = 12) -> list[dict]:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    q = db.query(NormalizedEvent)
    if unit_ids:
        q = q.filter(NormalizedEvent.unit_id.in_(unit_ids))
    q = q.filter(NormalizedEvent.timestamp <= now).order_by(NormalizedEvent.timestamp.desc()).limit(limit)
    events = q.all()
    units = {u.id: u for u in db.query(Unit).all()}
    rules = {r.rule_id: r.name for r in db.query(DetectionRule).all()}
    return [
        {
            "timestamp": e.timestamp,
            "unit_id": e.unit_id,
            "unit_name": units[e.unit_id].unit_code if e.unit_id in units else None,
            "hostname": e.hostname,
            "event_id": e.event_id,
            "category": e.category,
            "action": e.action,
            "severity": e.severity,
            "source_ip": e.source_ip,
            "username": e.username,
            "matched_rule_id": e.matched_rule_id,
            "matched_rule_name": rules.get(e.matched_rule_id) if e.matched_rule_id else None,
            "simulated": e.simulated,
            "id": e.id,
        }
        for e in events
    ]


def _active_threats(db: Session, unit_ids: list[str] | None, limit: int = 6) -> list[dict]:
    q = (
        db.query(Alert)
        .filter(Alert.status.in_(["open", "investigating"]))
        .order_by(Alert.severity, Alert.created_at.desc())
    )
    if unit_ids:
        q = q.filter(Alert.unit_id.in_(unit_ids))
    return [
        {
            "id": a.id,
            "alert_id": a.alert_id,
            "title": a.title,
            "severity": a.severity,
            "hostname": a.hostname,
            "event_count": a.event_count,
            "source_ip": a.source_ip,
            "username": a.username,
            "event_id": None,
            "detected_at": a.last_seen.isoformat(),
            "risk_score": a.risk_score,
            "status": a.status,
        }
        for a in q.limit(limit).all()
    ]


def _unit_overview(db: Session, unit_ids: list[str] | None) -> list[dict]:
    rows = []
    for unit in db.query(Unit).order_by(Unit.name).all():
        if unit_ids and unit.id not in unit_ids:
            continue
        agents = db.query(func.count(Agent.id)).filter(Agent.unit_id == unit.id).scalar() or 0
        events = db.query(func.count(NormalizedEvent.id)).filter(NormalizedEvent.unit_id == unit.id).scalar() or 0
        alerts = db.query(func.count(Alert.id)).filter(Alert.unit_id == unit.id).scalar() or 0
        risk = _unit_risk(db, unit.id)
        rows.append(
            {
                "id": unit.id,
                "unit_code": unit.unit_code,
                "name": unit.name,
                "city": unit.city,
                "latitude": unit.latitude,
                "longitude": unit.longitude,
                "agents": agents,
                "events": events,
                "alerts": alerts,
                "risk": risk,
                "status": unit.status,
            }
        )
    return rows


def _unit_risk(db: Session, unit_id: str) -> int:
    """Unit security score from open/investigating alerts.

    Calibrated so a realistic demo alert load maps to a spread across the
    map color bands (green < 35, warning 35-59, critical >= 60) instead of
    saturating at 100 after a handful of high-severity alerts. Weights are
    intentionally smaller than alert-level risk scores: a few medium alerts
    should read as "normal", while repeated criticals push toward red.
    """
    counts = dict(
        db.query(Alert.severity, func.count(Alert.id))
        .filter(Alert.unit_id == unit_id, Alert.status.in_(["open", "investigating"]))
        .group_by(Alert.severity)
        .all()
    )
    if not counts:
        return 0
    score = (
        counts.get("critical", 0) * 15
        + counts.get("high", 0) * 8
        + counts.get("medium", 0) * 4
        + counts.get("low", 0) * 2
    )
    return min(100, score)


def _platform_risk(db: Session, unit_ids: list[str] | None) -> int:
    q = db.query(Alert)
    if unit_ids:
        q = q.filter(Alert.unit_id.in_(unit_ids))
    open_alerts = q.filter(Alert.status.in_(["open", "investigating"])).all()
    if not open_alerts:
        return 0
    avg = sum(max(a.risk_score, 5) for a in open_alerts) / len(open_alerts)
    return min(100, int(avg))


def _agent_health(db: Session, unit_ids: list[str] | None, limit: int = 8) -> list[dict]:
    q = db.query(Agent, Unit).join(Unit, Agent.unit_id == Unit.id)
    if unit_ids:
        q = q.filter(Agent.unit_id.in_(unit_ids))
    q = q.order_by(Agent.last_seen_at.desc()).limit(limit)
    return [
        {
            "id": a.id,
            "agent_id": a.agent_id,
            "hostname": a.hostname,
            "unit_name": u.unit_code,
            "ip_address": a.ip_address,
            "os_version": a.os_version,
            "last_seen_at": a.last_seen_at,
            "events_per_sec": a.events_per_sec,
            "cpu_usage": a.cpu_usage,
            "memory_usage": a.memory_usage,
            "simulated": a.simulated,
            "status": a.status,
        }
        for a, u in q.all()
    ]


def _top_rules(
    db: Session, unit_ids: list[str] | None, since: datetime, limit: int = 5
) -> list[dict]:
    q = (
        db.query(NormalizedEvent.matched_rule_id, func.count(NormalizedEvent.id))
        .filter(
            NormalizedEvent.timestamp >= since,
            NormalizedEvent.matched_rule_id.isnot(None),
        )
        .group_by(NormalizedEvent.matched_rule_id)
        .order_by(func.count(NormalizedEvent.id).desc())
        .limit(limit)
    )
    if unit_ids:
        q = q.filter(NormalizedEvent.unit_id.in_(unit_ids))
    rules = {r.rule_id: r for r in db.query(DetectionRule).all()}
    return [
        {
            "rule_id": rule_id,
            "name": rules[rule_id].name if rule_id in rules else rule_id,
            "severity": rules[rule_id].severity if rule_id in rules else None,
            "times_matched": count,
            "mitre_technique": rules[rule_id].mitre_technique if rule_id in rules else None,
        }
        for rule_id, count in q.all()
    ]


@router.get("/dashboard/timeline")
def timeline(
    period: str = Query("24h"),
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _timeline(db, period, scope_unit_ids(user))


@router.get("/dashboard/severity")
def severity_distribution(
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _severity_distribution(db, scope_unit_ids(user))


@router.get("/dashboard/live-events")
def live_events(
    limit: int = Query(20, ge=1, le=100),
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _live_events(db, scope_unit_ids(user), limit)


@router.get("/dashboard/active-threats")
def active_threats(
    limit: int = Query(10, ge=1, le=50),
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _active_threats(db, scope_unit_ids(user), limit)


@router.get("/dashboard/unit-overview")
def unit_overview(
    _=Depends(require_permission("dashboard.view")),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _unit_overview(db, scope_unit_ids(user))
