from pydantic import BaseModel


class ReportRequest(BaseModel):
    report_type: str = "daily"
    unit_id: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    format: str = "csv"


class ReportMeta(BaseModel):
    report_type: str
    title: str
    generated_at: str
    rows: int


class StatsOut(BaseModel):
    total_events: int
    total_alerts: int
    open_alerts: int
    total_agents: int
    agents_online: int
    total_units: int
    total_rules: int
    events_per_second: int
    storage_estimate_mb: float
