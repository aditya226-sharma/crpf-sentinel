from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.database.base import Base, IdMixin, TimestampMixin


class Role(Base, IdMixin, TimestampMixin):
    __tablename__ = "roles"

    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    permissions = Column(JSON, nullable=False, default=list)
    default_dashboard = Column(String(32), nullable=True)


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(String(32), ForeignKey("roles.id"), nullable=False, index=True)
    unit_id = Column(String(32), ForeignKey("units.id"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    role = relationship("Role", lazy="joined")
    unit = relationship("Unit", lazy="joined")
