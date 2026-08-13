"""API router assembly."""

from fastapi import APIRouter

from app.api.routes import (
    agents,
    alerts,
    analytics,
    assets,
    audit,
    auth,
    dashboard,
    health,
    incidents,
    ioc,
    logs,
    mitre,
    reports,
    rules,
    search,
    stats,
    stream,
    units,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(stats.router)
api_router.include_router(dashboard.router)
api_router.include_router(logs.router)
api_router.include_router(alerts.router)
api_router.include_router(incidents.router)
api_router.include_router(rules.router)
api_router.include_router(ioc.router)
api_router.include_router(mitre.router)
api_router.include_router(analytics.router)
api_router.include_router(assets.router)
api_router.include_router(search.router)
api_router.include_router(agents.router)
api_router.include_router(units.router)
api_router.include_router(users.router)
api_router.include_router(audit.router)
api_router.include_router(reports.router)
api_router.include_router(stream.router)
