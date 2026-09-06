"""Demo endpoints — scripted attack simulation + curated-state reset.

Both are restricted to the ``super_admin`` role so they are never reachable in
a real operational deployment. The simulate path replays events through the
exact same ingestion/detection pipeline that live agents use.
"""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_roles
from app.database.session import SessionLocal, get_db
from app.models.user import User
from app.services import demo
from app.services.audit import record_audit

logger = logging.getLogger("cyberrakshak.demo")
router = APIRouter(prefix="/demo", tags=["demo"])
_reset_lock = threading.Lock()


@router.post("/simulate")
def run_simulation(
    request: Request,
    scenario: str = "espionage",
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    if scenario not in ("espionage",):
        raise HTTPException(status_code=400, detail="Unsupported scenario")
    try:
        result = demo.simulate_attack(db, scenario=scenario)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_audit(
        db, "demo_simulate", "demo",
        username=user.username, user_id=user.id, ip_address=client_ip(request),
        details={"scenario": scenario, "alerts": len(result["alerts_fired"])},
    )
    db.commit()
    return result


def _run_reset_worker(username: str, user_id: str, ip: str) -> None:
    """Detached worker: purge simulated artifacts and reseed the curated backdrop.

    Runs on its own DB session/thread so the HTTP request can return instantly
    instead of blocking on hosted-Postgres deletes that can outlast client timeouts.
    """
    if not _reset_lock.acquire(blocking=False):
        logger.warning("demo_reset skipped: another reset is already in progress")
        return
    try:
        db = SessionLocal()
        try:
            logger.info("demo_reset worker starting (%s)", username)
            result = demo.reset_demo(db)
            record_audit(
                db, "demo_reset", "demo",
                username=username, user_id=user_id, ip_address=ip,
                details={"status": "ok", **result},
            )
            db.commit()
            logger.info("demo_reset completed: %s", result)
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("demo_reset failed")
        finally:
            db.close()
    finally:
        _reset_lock.release()


@router.post("/reset")
def reset(
    request: Request,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.DEMO_BACKGROUND_RESET:
        # Synchronous path (tests / small DBs): do the work inline.
        result = demo.reset_demo(db)
        record_audit(
            db, "demo_reset", "demo",
            username=user.username, user_id=user.id, ip_address=ip,
            details={"status": "ok", **result},
        )
        db.commit()
        return {"status": "ok", **result}

    if not _reset_lock.acquire(blocking=False):
        record_audit(
            db, "demo_reset_skipped", "demo",
            username=user.username, user_id=user.id, ip_address=ip,
            details={"status": "busy"},
        )
        db.commit()
        return {"status": "busy", "message": "A reset is already in progress"}
    _reset_lock.release()
    record_audit(
        db, "demo_reset_started", "demo",
        username=user.username, user_id=user.id, ip_address=ip,
        details={"status": "queued"},
    )
    db.commit()
    threading.Thread(
        target=_run_reset_worker,
        args=(user.username, user.id, ip),
        daemon=True,
    ).start()
    return {"status": "started", "message": "Reset running in background — dashboard will refresh"}
