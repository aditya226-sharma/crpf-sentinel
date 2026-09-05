from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestItem(BaseModel):
    event_id: int | None = None
    provider: str | None = None
    computer: str | None = None
    time_created: datetime | None = None
    user: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    raw_xml: str | None = None
    raw_json: str | None = None
    source: str = "windows"


class IngestRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=40)
    unit_id: str | None = None
    hostname: str | None = None
    events: list[IngestItem] = Field(default_factory=list, max_length=2000)
    heartbeat: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    accepted: int
    parsed: int
    alerts_triggered: int
    matched_rules: list[str]
    new_alert_ids: list[str]


class EventOut(BaseModel):
    id: int
    timestamp: datetime
    unit_id: str | None = None
    unit_name: str | None = None
    agent_id: str | None = None
    hostname: str | None = None
    event_id: int
    provider: str | None = None
    category: str | None = None
    action: str | None = None
    username: str | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    process_name: str | None = None
    command_line: str | None = None
    logon_type: str | None = None
    status_code: str | None = None
    severity: str
    is_suspicious: bool
    simulated: bool = False
    matched_rule_id: str | None = None
    extra: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class EventDetail(EventOut):
    parser_version: str | None = None
    raw_log: str | None = None
    log_id: int | None = None
