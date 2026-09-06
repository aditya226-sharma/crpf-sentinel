from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import User


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RoleOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    permissions: list[str]
    default_dashboard: str | None = None

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: str | None = None
    role: RoleOut | None = None
    role_id: str
    unit_id: str | None = None
    is_active: bool
    last_login_at: datetime | None = None

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=RoleOut.model_validate(user.role) if user.role else None,
            role_id=user.role_id,
            unit_id=user.unit_id,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
        )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
