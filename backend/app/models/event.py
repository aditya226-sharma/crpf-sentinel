from app.database.base import BigIntPK
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.database.base import Base, TimestampMixin


class NormalizedEvent(Base, TimestampMixin):
    __tablename__ = "normalized_events"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    log_id = Column(BigIntPK, ForeignKey("logs.id"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    unit_id = Column(String(32), ForeignKey("units.id"), nullable=True)
    agent_id = Column(String(32), ForeignKey("agents.id"), nullable=True)
    hostname = Column(String(120), nullable=True)
    event_id = Column(Integer, nullable=False)
    provider = Column(String(255), nullable=True)
    category = Column(String(60), nullable=True)
    action = Column(String(60), nullable=True)
    username = Column(String(120), nullable=True)
    source_ip = Column(String(45), nullable=True)
    destination_ip = Column(String(45), nullable=True)
    process_name = Column(String(255), nullable=True)
    command_line = Column(Text, nullable=True)
    logon_type = Column(String(20), nullable=True)
    status_code = Column(String(20), nullable=True)
    severity = Column(String(20), nullable=False, default="informational")
    parser_version = Column(String(10), nullable=True)
    is_suspicious = Column(Boolean, nullable=False, default=False)
    simulated = Column(Boolean, nullable=False, default=False, index=True)
    matched_rule_id = Column(String(32), nullable=True, index=True)
    extra = Column(JSON, nullable=True)
