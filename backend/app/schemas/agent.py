from datetime import datetime

from pydantic import BaseModel, Field


class AgentOut(BaseModel):
    id: str
    agent_id: str
    unit_id: str
    unit_name: str | None = None
    hostname: str
    ip_address: str | None = None
    os_version: str | None = None
    agent_version: str | None = None
    status: str
    last_seen_at: datetime | None = None
    events_per_sec: int
    cpu_usage: float
    memory_usage: float
    buffer_size: int
    simulated: bool = False
    last_sync_status: str | None = None
    is_enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentRegister(BaseModel):
    agent_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    unit_id: str
    hostname: str = Field(min_length=1, max_length=120)
    ip_address: str | None = None
    os_version: str | None = None
    agent_version: str | None = None
    simulated: bool = False


class AgentRegistered(BaseModel):
    agent: AgentOut
    api_token: str


class AgentUpdate(BaseModel):
    hostname: str | None = None
    ip_address: str | None = None
    os_version: str | None = None
    agent_version: str | None = None
    is_enabled: bool | None = None


class AgentHeartbeat(BaseModel):
    hostname: str | None = None
    ip_address: str | None = None
    os_version: str | None = None
    agent_version: str | None = None
    events_per_sec: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    buffer_size: int = 0
    sync_status: str | None = None
