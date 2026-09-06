"""Authentication API: login, logout, current user, password change."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import client_ip, get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.rate_limit import RateLimiter
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import ChangePasswordRequest
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

login_limiter = RateLimiter(settings.RATE_LIMIT_LOGIN_PER_MINUTE, 60)


def _is_placeholder_account(user: User) -> bool:
    return (
        user.username == settings.SEED_ADMIN_USERNAME
        and user.email == settings.SEED_ADMIN_EMAIL
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = f"login:{client_ip(request)}:{body.username.lower()}"
    if not login_limiter.check(key):
        raise UnauthorizedError("RATE_LIMITED", "Too many login attempts. Try again later.")

    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        record_audit(
            db, "login_failed", "authentication",
            username=body.username, ip_address=client_ip(request),
            details={"reason": "invalid_credentials"},
        )
        db.commit()
        raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid username or password")

    if not user.is_active:
        raise UnauthorizedError("ACCOUNT_DISABLED", "Account is disabled")

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    record_audit(
        db, "login_success", "authentication",
        username=user.username, user_id=user.id, ip_address=client_ip(request),
        details={"role": user.role.name if user.role else None},
    )
    db.commit()

    token = create_access_token(
        user.id,
        claims={
            "username": user.username,
            "role": user.role.name if user.role else "unknown",
        },
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.from_user(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.from_user(user)


@router.post("/logout", status_code=204)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record_audit(
        db, "logout", "authentication",
        username=user.username, user_id=user.id, ip_address=client_ip(request),
    )
    db.commit()
    return None


@router.put("/password", status_code=204)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise UnauthorizedError("INVALID_PASSWORD", "Current password is incorrect")
    if len(body.new_password) < settings.PASSWORD_MIN_LENGTH:
        raise UnauthorizedError("WEAK_PASSWORD", "New password too short")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.add(user)
    record_audit(
        db, "password_change", "account", username=user.username, user_id=user.id
    )
    db.commit()
    return None
