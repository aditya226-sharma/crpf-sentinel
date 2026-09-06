from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint

from app.database.base import Base, BigIntPK, TimestampMixin


class VpnTunnel(Base, TimestampMixin):
    __tablename__ = "vpn_tunnels"
    __table_args__ = (UniqueConstraint("tunnel_name", "peer_ip", name="uq_vpn_tunnel_identity"),)

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    unit_id = Column(String(32), ForeignKey("units.id"), nullable=True, index=True)
    agent_id = Column(String(32), ForeignKey("agents.id"), nullable=True, index=True)
    tunnel_name = Column(String(120), nullable=False, index=True)
    peer_ip = Column(String(45), nullable=False, index=True)
    local_ip = Column(String(45), nullable=True)
    dh_group = Column(String(20), nullable=True)
    pfs = Column(Boolean, nullable=True)
    cipher = Column(String(40), nullable=True)
    integrity = Column(String(40), nullable=True)
    ike_version = Column(String(10), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    last_seen = Column(DateTime(timezone=True), nullable=False, index=True)
    simulated = Column(Boolean, nullable=False, default=False)