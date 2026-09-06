"""Auth + RBAC FastAPI dependencies. Enforcement happens here, server-side."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import constant_time_equals, decode_access_token, hash_agent_token
from app.database.session import get_db
from app.models.agent import Agent
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)

PERMISSIONS = {
    "dashboard.view",
    "logs.view",
    "logs.ingest",
    "alerts.view",
    "alerts.manage",
    "rules.view",
    "rules.manage",
    "agents.view",
    "agents.manage",
    "units.view",
    "units.manage",
    "users.manage",
    "audit.view",
    "reports.view",
    "settings.manage",
    "threat_intel.view",
    "threat_intel.manage",
    "correlations.view",
    "graph.view",
}

ROLE_PERMISSIONS = {
    "super_admin": PERMISSIONS,
    "security_expert": {
        "dashboard.view",
        "logs.view",
        "alerts.view",
        "alerts.manage",
        "rules.view",
        "rules.manage",
        "agents.view",
        "units.view",
        "audit.view",
        "reports.view",
        "threat_intel.view",
        "correlations.view",
    },
    "unit_admin": {
        "dashboard.view",
        "logs.view",
        "alerts.view",
        "agents.view",
        "units.view",
        "reports.view",
    },
    "crime_analyst": {
        "dashboard.view",
        "logs.view",
        "alerts.view",
        "units.view",
        "threat_intel.view",
        "graph.view",
    },
}


def client_ip(request: Request) -> str:
    """Return the client IP, honoring X-Forwarded-For only behind a trusted proxy.

    Unconditionally trusting X-Forwarded-For lets clients spoof arbitrary IPs and
    bypass IP-based rate limiting / auditing.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and get_settings().TRUST_PROXY:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("UNAUTHORIZED", "Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise UnauthorizedError("INVALID_TOKEN", "Token is invalid or expired")
    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError("INVALID_TOKEN", "Token subject missing")
    user = db.get(User, subject)
    if user is None or not user.is_active:
        raise UnauthorizedError("INVALID_TOKEN", "Account is disabled")
    return user


def _permissions_for(user: User) -> set[str]:
    return ROLE_PERMISSIONS.get(user.role.name, set()) if user.role else set()


def require_permission(permission: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if permission not in _permissions_for(user):
            raise ForbiddenError("FORBIDDEN", f"Permission required: {permission}")
        return user

    return dependency


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in roles:
            raise ForbiddenError("FORBIDDEN", "Insufficient role for this operation")
        return user

    return dependency


def get_current_agent(
    request: Request, db: Session = Depends(get_db)
) -> tuple[Agent, User | None]:
    """Authenticate an agent via its secret token. Returns agent and the registering user."""
    token = request.headers.get("x-agent-token")
    if not token:
        raise UnauthorizedError("UNAUTHORIZED", "Missing agent token")
    token_hash = hash_agent_token(token)
    agent = db.query(Agent).filter(Agent.auth_token_hash == token_hash).first()
    if agent is None:
        raise UnauthorizedError("INVALID_AGENT_TOKEN", "Agent token is invalid")
    if not agent.is_enabled:
        raise ForbiddenError("AGENT_DISABLED", "Agent is disabled")
    return agent


def scope_unit_ids(user: User) -> list[str] | None:
    """Return the unit ids the user may access, or None for all units."""
    if user.role.name == "unit_admin":
        return [user.unit_id] if user.unit_id else []
    return None


def unit_in_scope(unit_scope: list[str] | None, unit_id: str | None) -> bool:
    """True if the resource's unit is visible to the caller's scope.

    A unit scope of None means the caller (global role) may access all units.
    """
    return unit_scope is None or (unit_id is not None and unit_id in unit_scope)
