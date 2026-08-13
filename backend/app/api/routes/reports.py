"""Report download endpoints (CSV / JSON)."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.deps import get_current_user, require_permission, scope_unit_ids
from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.services.reports import build_report

router = APIRouter(tags=["reports"])


@router.get("/reports/{report_type}")
def download_report(
    report_type: str,
    unit_id: str | None = Query(None),
    format: str = Query("csv", pattern=r"^(csv|json)$"),
    _=Depends(require_permission("reports.view")),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    unit_scope = scope_unit_ids(user)
    if unit_id and not (unit_scope is None or unit_id in unit_scope):
        raise NotFoundError("UNIT_NOT_FOUND", "Unit not found")

    try:
        payload, content_type, meta = build_report(
            db, report_type, unit_id, format, unit_scope=unit_scope
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": {"code": "INVALID_REPORT", "message": str(exc)}})
    headers = {
        "X-Report-Type": meta["report_type"],
        "X-Report-Rows": str(meta["rows"]),
        "Content-Disposition": f'attachment; filename="{report_type}_report.{format}"',
    }
    return PlainTextResponse(content=payload, media_type=content_type, headers=headers)
