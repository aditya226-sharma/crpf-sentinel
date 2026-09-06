"""Demo endpoints — scripted attack simulation + curated-state reset.

Both are restricted to the ``super_admin`` role so they are never reachable in
a real operational deployment. The simulate path replays events through the
exact same ingestion/detection pipeline that live agents use.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_user, require_roles
from app.database.session import get_db
from app.models.user import User
from app.services import demo
from app.services.audit import record_audit

router = APIRouter(prefix="/demo", tags=["demo"])


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


@router.post("/reset")
def reset(
    request: Request,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    result = demo.reset_demo(db)
    record_audit(
        db, "demo_reset", "demo",
        username=user.username, user_id=user.id, ip_address=client_ip(request),
        details=result,
    )
    db.commit()
    result["status"] = "ok"
    return result
