from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.database.base import Base, BigIntPK, TimestampMixin


class Flow(Base, TimestampMixin):
    __tablename__ = "flows"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    unit_id = Column(String(32), ForeignKey("units.id"), nullable=True, index=True)
    agent_id = Column(String(32), ForeignKey("agents.id"), nullable=True, index=True)
    hostname = Column(String(120), nullable=True)
    source_ip = Column(String(45), nullable=False, index=True)
    destination_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer, nullable=True)
    destination_port = Column(Integer, nullable=True)
    protocol = Column(String(10), nullable=True)
    packets = Column(Integer, nullable=False, default=0)
    bytes = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    simulated = Column(Boolean, nullable=False, default=False)