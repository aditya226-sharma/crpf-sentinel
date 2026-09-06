from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class AuditLogOut(BaseModel):
    id: int
    user_id: str | None = None
    username: str | None = None
    action: str
    category: str
    details: dict[str, Any] | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: str
    user_id: str
    type: str
    severity: str
    title: str
    message: str | None = None
    alert_id: str | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=9, max_length=128)
    role_id: str
    unit_id: str | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role_id: str | None = None
    unit_id: str | None = None
    is_active: bool | None = None
    password: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=9, max_length=128)
