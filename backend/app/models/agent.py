from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from app.database.base import Base, IdMixin, TimestampMixin


class Agent(Base, IdMixin, TimestampMixin):
    __tablename__ = "agents"

    agent_id = Column(String(40), unique=True, nullable=False, index=True)
    unit_id = Column(String(32), ForeignKey("units.id"), nullable=False, index=True)
    hostname = Column(String(120), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True, index=True)
    os_version = Column(String(80), nullable=True)
    agent_version = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="offline", index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True, index=True)
    events_per_sec = Column(Integer, nullable=False, default=0)
    cpu_usage = Column(Float, nullable=False, default=0.0)
    memory_usage = Column(Float, nullable=False, default=0.0)
    buffer_size = Column(Integer, nullable=False, default=0)
    simulated = Column(Boolean, nullable=False, default=False, index=True)
    auth_token_hash = Column(String(64), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    registered_by = Column(String(32), ForeignKey("users.id"), nullable=True)
    last_sync_status = Column(String(40), nullable=True)
