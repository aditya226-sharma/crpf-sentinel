"""Crime case dossier endpoints — evidence upload + trilingual report/PDF."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_permission
from app.database.session import get_db
from app.models.case_intake import CaseDocument, CaseIntake
from app.models.user import User
from app.services import case_intake as cx

router = APIRouter(prefix="/case-intake", tags=["case-intake"])

_PREFIX = "CSI-"


def _case_out(case: CaseIntake, documents: list[CaseDocument] | None = None) -> dict:
    docs = documents if documents is not None else []
    return {
        "id": case.id,
        "case_id": case.case_id,
        "title": case.title,
        "fir_number": case.fir_number,
        "description": case.description,
        "status": case.status,
        "report_language": case.report_language,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "kind": d.kind,
                "mime": d.mime,
                "size": d.size,
                "available": bool(d.stored_path),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
    }


def _get_case_or_404(db: Session, case_id: str) -> CaseIntake:
    case = (
        db.query(CaseIntake)
        .filter(CaseIntake.case_id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("", status_code=201)
def create_case(
    title: str = Form(...),
    fir_number: str | None = Form(None),
    description: str | None = Form(None),
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    case_id = f"{_PREFIX}{uuid.uuid4().hex[:8].upper()}"
    while db.query(CaseIntake).filter(CaseIntake.case_id == case_id).first():
        case_id = f"{_PREFIX}{uuid.uuid4().hex[:8].upper()}"
    case = CaseIntake(
        id=uuid.uuid4().hex,
        case_id=case_id,
        title=title.strip()[:255] or "Untitled case",
        fir_number=(fir_number or "").strip()[:60] or None,
        description=(description or "").strip()[:4000] or None,
        status="draft",
        created_by=user.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _case_out(case)


@router.post("/{case_id}/documents", status_code=201)
async def upload_documents(
    case_id: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    case = _get_case_or_404(db, case_id)
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    accepted: list[dict] = []
    skipped = 0
    reasons: list[str] = []

    for file in files:
        filename = file.filename or "unnamed"
        raw = await file.read(max_bytes + 1)
        if len(raw) > max_bytes:
            skipped += 1
            reasons.append(f"{filename}: exceeds {settings.MAX_UPLOAD_MB} MB")
            continue
        mime = file.content_type or "application/octet-stream"
        kind = cx.classify_file(filename)
        stored_path, _safe_name, size = cx.store_upload(case.id, filename, raw, mime)
        doc = CaseDocument(
            id=uuid.uuid4().hex,
            case_id=case.id,
            filename=filename[:255],
            kind=kind,
            mime=mime,
            size=size,
            stored_path=stored_path,
            uploaded_by=user.id,
        )
        db.add(doc)
        accepted.append({"id": doc.id, "filename": filename, "kind": kind, "size": size})
    db.commit()
    return {"case_id": case.case_id, "accepted": len(accepted), "skipped": skipped,
            "documents": accepted, "reasons": reasons}


@router.get("")
def list_cases(
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    cases = db.query(CaseIntake).order_by(CaseIntake.created_at.desc()).limit(50).all()
    doc_counts = {}
    for case in cases:
        counts = (
            db.query(CaseDocument.kind, func.count(CaseDocument.id))
            .filter(CaseDocument.case_id == case.id)
            .group_by(CaseDocument.kind)
            .all()
        )
        doc_counts[case.id] = dict(counts)
    out = []
    for case in cases:
        base = _case_out(case)
        base["doc_counts"] = doc_counts.get(case.id, {})
        out.append(base)
    return {"items": out}


@router.get("/{case_id}")
def get_case(
    case_id: str,
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    case = _get_case_or_404(db, case_id)
    docs = db.query(CaseDocument).filter(CaseDocument.case_id == case.id).order_by(CaseDocument.created_at).all()
    return _case_out(case, docs)


@router.get("/{case_id}/report")
def get_report(
    case_id: str,
    lang: str = "en",
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    if lang not in cx.LANGUAGES:
        raise HTTPException(status_code=400, detail=f"lang must be one of {cx.LANGUAGES}")
    case = _get_case_or_404(db, case_id)
    docs = db.query(CaseDocument).filter(CaseDocument.case_id == case.id).order_by(CaseDocument.created_at).all()
    analysis = cx.analyze_case(case, docs, lang)
    case.report_language = lang
    db.commit()
    return {
        "case": _case_out(case, docs),
        "lang": lang,
        "language_label": cx.LANGUAGE_LABELS[lang],
        "narrative": analysis["narrative"],
        "stats": analysis["stats"],
        "intel": analysis["intel"],
        "cdr": analysis["cdr"],
        "photos": analysis["photos"],
        "html": analysis["html"],
    }


@router.get("/{case_id}/report.pdf")
def download_report_pdf(
    case_id: str,
    lang: str = "en",
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    if lang not in cx.LANGUAGES:
        raise HTTPException(status_code=400, detail=f"lang must be one of {cx.LANGUAGES}")
    case = _get_case_or_404(db, case_id)
    docs = db.query(CaseDocument).filter(CaseDocument.case_id == case.id).order_by(CaseDocument.created_at).all()
    analysis = cx.analyze_case(case, docs, lang)
    try:
        pdf = cx.render_pdf(case, docs, lang, analysis)
    except cx.ReportUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    from fastapi.responses import Response

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cyberrakshak-{case.case_id}-{lang}.pdf"'
        },
    )