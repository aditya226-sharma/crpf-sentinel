from datetime import datetime

from pydantic import BaseModel


class KpiValue(BaseModel):
    label: str
    value: float | int | str
    change_pct: float | None = None
    compare_label: str | None = None
    detail: str | None = None
    status: str | None = None


class TimelinePoint(BaseModel):
    bucket: str
    events: int
    alerts: int
    critical_alerts: int


class SeverityBucket(BaseModel):
    severity: str
    count: int
    pct: float


class LiveEventItem(BaseModel):
    timestamp: datetime
    unit_id: str | None = None
    unit_name: str | None = None
    hostname: str | None = None
    event_id: int
    category: str | None = None
    action: str | None = None
    severity: str
    source_ip: str | None = None
    username: str | None = None
    matched_rule_id: str | None = None
    matched_rule_name: str | None = None
    simulated: bool = False
    id: int | None = None


class UnitOverviewItem(BaseModel):
    id: str
    unit_code: str
    name: str
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    agents: int
    events: int
    alerts: int
    risk: int
    status: str


class AgentHealthItem(BaseModel):
    id: str
    agent_id: str
    hostname: str
    unit_name: str | None = None
    ip_address: str | None = None
    os_version: str | None = None
    last_seen_at: datetime | None = None
    events_per_sec: int
    cpu_usage: float
    memory_usage: float
    simulated: bool = False
    status: str
    buffer_size: int = 0
    sync_status: str | None = None


class DashboardSummary(BaseModel):
    total_events: KpiValue
    critical_alerts: KpiValue
    high_alerts: KpiValue
    active_agents: KpiValue
    monitored_units: KpiValue
    risk_score: KpiValue
    timeline: list[TimelinePoint]
    severity: list[SeverityBucket]
    live_events: list[LiveEventItem]
    active_threats: list[dict]
    units: list[UnitOverviewItem]
    agent_health: list[AgentHealthItem]
    top_rules: list[dict]
    generated_at: datetime
