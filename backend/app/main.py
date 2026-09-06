"""CyberRakshak — FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.seed.seed_all import seed_all

settings = get_settings()

_expose_docs = settings.APP_ENV != "production"

app = FastAPI(
    title="CyberRakshak API",
    description=(
        "Centralized IT System Log Analysis & Threat Detection Platform. "
        "Windows Event Log ingestion, normalization, signature detection, "
        "alert management and SOC monitoring."
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
    try:
        seed_all()
    except Exception as exc:  # noqa: BLE001 - a seed failure must not block startup
        import logging

        logging.getLogger("cyberrakshak.startup").exception("startup seeding failed: %s", exc)
    _start_osint_poller()


def _start_osint_poller() -> None:
    """Start the VAJRA OSINT bridge thread when configured (opt-in).

    Requires OSINT_API_URL + OSINT_API_KEY (+ an ingest URL and bridge-agent
    token for HTTP publishing). Records flow into the main pipeline through the
    exact same /api/logs/ingest path as every other format.
    """
    import logging

    logger = logging.getLogger("cyberrakshak.osint")

    try:
        from app.core.config import get_settings as _gs

        cfg = _gs()
    except Exception:  # pragma: no cover - config always available
        return

    if not cfg.OSINT_API_URL or not cfg.OSINT_API_KEY:
        return

    try:
        from app.integrations.osint_client import (
            OSINTClient,
            ensure_osint_bridge_agent,
            publish_in_process,
            publish_to_ingest,
            start_poller_thread,
        )
        from app.database.session import SessionLocal

        client = OSINTClient(cfg.OSINT_API_URL, cfg.OSINT_API_KEY)

        def _publish(record: dict) -> dict:
            if cfg.OSINT_BRIDGE_AGENT_TOKEN:
                return publish_to_ingest(
                    record,
                    ingest_url=cfg.OSINT_INGEST_URL,
                    agent_id=cfg.OSINT_BRIDGE_AGENT_ID,
                    agent_token=cfg.OSINT_BRIDGE_AGENT_TOKEN,
                )
            with SessionLocal() as db:
                agent, _ = ensure_osint_bridge_agent(db)
                return publish_in_process(db, record, agent=agent)

        start_poller_thread(client, publish_fn=_publish)
    except Exception as exc:  # pragma: no cover - poller must never block startup
        logger.warning("OSINT poller not started: %s", exc)
