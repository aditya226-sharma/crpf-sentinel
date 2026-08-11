"""CyberRakshak — FastAPI application entrypoint."""

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.database.init_db import init_database
from app.seed.seed_all import seed_all

settings = get_settings()

_expose_docs = settings.APP_ENV != "production"

app = FastAPI(
    title="CyberRakshak API",
    description=(
        "Centralized IT System Log Analysis & Threat Detection Platform. "
        "Windows Event Log ingestion, normalization, signature detection, "
        "alert management and SOC monitoring. All data is DEMO / SYNTHETIC."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs" if _expose_docs else None,
    redoc_url="/redoc" if _expose_docs else None,
    openapi_url="/openapi.json" if _expose_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


app.state.debug = settings.DEBUG
register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.on_event("startup")
async def on_startup() -> None:
    if settings.SEED_DEMO_DATA:
        seed_all()
    else:
        init_database()
    if settings.SEED_DEMO_DATA:
        from app.simulation.live import start_live_demo

        app.state.live_demo_task = asyncio.create_task(start_live_demo())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    task = getattr(app.state, "live_demo_task", None)
    if task is not None:
        task.cancel()
