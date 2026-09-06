"""Crime dossier → trilingual PDF report engine.

A ``CaseIntake`` aggregates raw investigative evidence (FIR text, photographs,
call records / CDR, forensic reports, CCTV clips, and any other files). This
module:

    * classifies an uploaded file into an evidence kind,
    * parses FIR text and CDR CSV into extractable facts (phones, dates,
      amounts, call volume, top counterparties),
    * assembles a single report rendered in English, Hindi or Hinglish from a
      template phrase library (no LLM required — every fact is grounded in the
      uploaded evidence or the case metadata),
    * renders the report to HTML and to PDF (WeasyPrint + fontconfig, so
      Devanagari shaping is correct).
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

LANGUAGES = ("en", "hi", "hinglish")
LANGUAGE_LABELS = {"en": "English", "hi": "Hindi (हिंदी)", "hinglish": "Hinglish"}

# Evidence kind classification: name tokens win, then extension.
_KIND_BY_NAME = (
    ("cctv", ("cctv", "camera", "video", "cam")),
    ("photo", ("photo", "photo evidence", "pic")),
    ("fir", ("fir", "first information", "prashasan", "complaint")),
    ("call_records", ("call record", "call detail", "cdr", "calls")),
    ("forensic", ("forensic", "forensics", "fss")),
)
_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"}
_VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "m4v", "3gp"}
_TEXT_EXTS = {"txt", "md", "csv", "json", "log"}
_SPREADSHEET_EXTS = {"csv", "xlsx", "xls", "tsv"}

_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
_AMOUNT_RE = re.compile(r"(?:\u20b9|Rs\.?|INR)\s*(\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
_DURATION_RE = re.compile(r"(\d+)\s*(?:sec|s|min|m)", re.IGNORECASE)

_CDR_HEADER_TOKENS = (
    "phone", "number", "caller", "party", "duration", "calltime",
    "time", "date", "type", "io", "dialed", "call_type",
)


class CaseNotFoundError(Exception):
    pass


class ReportUnavailableError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Language phrase library (template-driven, grounded in evidence counts)
# --------------------------------------------------------------------------- #

_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "report_title": "Criminal Intelligence — Crime Case Report",
        "case_id": "Case ID",
        "fir": "FIR No.",
        "description": "Notes",
        "status": "Status",
        "language": "Language",
        "narrative": "Executive summary",
        "evidence": "Evidence inventory",
        "kind": "Kind",
        "filename": "File",
        "size": "Size",
        "available": "available",
        "missing": "file unavailable",
        "photos": "Evidence photographs",
        "cdr": "Call detail analysis",
        "forensic": "Forensic / documents",
        "cctv": "CCTV footage",
        "entities": "Extracted intelligence",
        "phones": "Phone numbers",
        "dates": "Dates",
        "amounts": "Amounts",
        "total": "Total",
        "generated_at": "Report generated",
        "disclaimer": "Computer-generated report based solely on the uploaded case evidence.",
    },
    "hi": {
        "report_title": "आपराधिक खुफिया — अपराध केस रिपोर्ट",
        "case_id": "केस आईडी",
        "fir": "प्राथमिकी संख्या",
        "description": "विवरण",
        "status": "स्थिति",
        "language": "भाषा",
        "narrative": "कार्यकारी सारांश",
        "evidence": "साक्ष्य सूची",
        "kind": "श्रेणी",
        "filename": "फ़ाइल",
        "size": "आकार",
        "available": "उपलब्ध",
        "missing": "फ़ाइल उपलब्ध नहीं",
        "photos": "साक्ष्य तस्वीरें",
        "cdr": "कॉल विवरण विश्लेषण",
        "forensic": "फोरेंसिक / दस्तावेज़",
        "cctv": "सीसीटीवी फुटेज",
        "entities": "निकाले गए विवरण",
        "phones": "फ़ोन नंबर",
        "dates": "तिथियां",
        "amounts": "राशि",
        "total": "कुल",
        "generated_at": "रिपोर्ट तैयार",
        "disclaimer": "यह रिपोर्ट सिस्टम द्वारा केवल अपलोड किए गए साक्ष्य के आधार पर तैयार की गई है।",
    },
    "hinglish": {
        "report_title": "Criminal Intelligence — Crime Case Report",
        "case_id": "Case ID",
        "fir": "FIR No.",
        "description": "Notes",
        "status": "Status",
        "language": "Bhasha",
        "narrative": "Executive Summary",
        "evidence": "Evidence Inventory",
        "kind": "Kism",
        "filename": "File",
        "size": "Size",
        "available": "available",
        "missing": "file unavailable",
        "photos": "Evidence Photos",
        "cdr": "Call Detail Analysis",
        "forensic": "Forensic / Documents",
        "cctv": "CCTV Footage",
        "entities": "Extracted Intelligence",
        "phones": "Phone Numbers",
        "dates": "Dates",
        "amounts": "Amounts",
        "total": "Total",
        "generated_at": "Report Generated",
        "disclaimer": "Yeh report system ne sirf uploaded evidence ke aadhar par banai hai.",
    },
}


def _t(lang: str, key: str) -> str:
    return _PHRASES.get(lang, _PHRASES["en"]).get(key, _PHRASES["en"].get(key, key))


def _plural(n: int, single: str, plural: str | None = None) -> str:
    return f"{n} {single if n == 1 else (plural or single + 's')}"


def _narrative(lang: str, stats: dict, top_caller: str | None) -> str:
    p, fir, cdr, fc, vid, other, total = (
        stats["photos"], stats["fir"], stats["call_records"], stats["forensic"],
        stats["cctv"], stats["documents"], stats["total"],
    )
    phones = stats["phones"]
    if lang == "hi":
        base = (
            f"इस केस में कुल {total} साक्ष्य दर्ज किए गए हैं — {_plural(p, 'तस्वीर', 'तस्वीरें')}, "
            f"{_plural(fir, 'प्राथमिकी')}, {_plural(cdr, 'कॉल रिकॉर्ड')}, {_plural(fc, 'फोरेंसिक दस्तावेज़')}, "
            f"{_plural(vid, 'सीसीटीवी क्लिप')} और {_plural(other, 'अन्य फ़ाइल')}। "
            f"विश्लेषण से {phones} फ़ोन नंबर निकाले गए हैं।"
        )
    elif lang == "hinglish":
        base = (
            f"Is case me total {total} evidence dharje hain — {_plural(p, 'photo')}, {_plural(fir, 'FIR')}, "
            f"{_plural(cdr, 'call record')}, {_plural(fc, 'forensic document')}, "
            f"{_plural(vid, 'CCTV clip')} aur {_plural(other, 'other file')}. "
            f"Analysis se {phones} phone numbers nikale gaye hain."
        )
    else:
        base = (
            f"This case dossier aggregates {_plural(total, 'evidence item')} — "
            f"{_plural(p, 'photograph')}, {_plural(fir, 'FIR record')}, {_plural(cdr, 'call record')}, "
            f"{_plural(fc, 'forensic document')}, {_plural(vid, 'CCTV clip')}, "
            f"and {_plural(other, 'other file')}. The analysis extracted {phones} unique phone number(s)."
        )
    if top_caller and stats["call_records"]:
        if lang == "hi":
            base += f" सबसे अधिक संपर्क संख्या {top_caller} पाई गई है।"
        elif lang == "hinglish":
            base += f" Sabse zyada contact number {top_caller} paya gaya hai."
        else:
            base += f" The highest-contact number is {top_caller}."
    return base


# --------------------------------------------------------------------------- #
# Classification + parsing helpers
# --------------------------------------------------------------------------- #

def _ext_name(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()[:8]


def classify_file(filename: str) -> str:
    """Return the evidence kind for ``filename`` (name tokens, then extension)."""
    lower = filename.lower()
    for kind, tokens in _KIND_BY_NAME:
        if any(t in lower for t in tokens):
            return kind
    ext = _ext_name(filename)
    if ext in _IMAGE_EXTS:
        return "photo"
    if ext in _VIDEO_EXTS:
        return "cctv"
    if ext in _SPREADSHEET_EXTS and any(t in lower for t in ("call", "cdr", "voice", "detail")):
        return "call_records"
    return "document"


def _safe_ext(filename: str) -> str:
    ext = _ext_name(filename)
    return ext if re.fullmatch(r"[a-z0-9]{1,8}", ext) else "bin"


def _format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def _extract_intel(text: str) -> dict:
    return {
        "phones": sorted({_normalize_phone(p) for p in _PHONE_RE.findall(text) if _normalize_phone(p)}),
        "dates": sorted({d for d in _DATE_RE.findall(text)}),
        "amounts": sorted({a.strip() for a in _AMOUNT_RE.findall(text)}),
    }


def _merge_intel(target: dict, extra: dict) -> None:
    for key in ("phones", "dates", "amounts"):
        target[key] = sorted(set(target.get(key, [])) | set(extra.get(key, [])))


def _pick_col(header: list[str], primary: tuple[str, ...], secondary: tuple[str, ...]) -> int:
    for tokens in (primary, secondary):
        if not tokens:
            continue
        idx = next((i for i, h in enumerate(header) if any(t in h for t in tokens)), -1)
        if idx >= 0:
            return idx
    return -1


def _parse_duration(value: object) -> int:
    s = str(value or "").strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        m = _DURATION_RE.search(s)
        return int(m.group(1)) if m else 0


def _parse_cdr(raw: bytes, filename: str) -> dict:
    """Tolerant CSV parse: finds a header row, then aggregates per-number rows."""
    text = _decode_text(raw)
    duration_by_number: dict[str, int] = defaultdict(int)
    count_by_number: Counter[str] = Counter()
    rows_data: list[tuple[str, int]] = []

    if _ext_name(filename) in _SPREADSHEET_EXTS:
        reader = list(csv.reader(io.StringIO(text)))
        header_idx = -1
        for i, row in enumerate(reader[:6]):
            joined = " ".join(c.lower() for c in row)
            if any(t in joined for t in _CDR_HEADER_TOKENS):
                header_idx = i
                break
        if header_idx == -1 and reader:
            header_idx = 0
        if reader:
            header = [str(c).lower() for c in reader[header_idx]]
            num_col = _pick_col(
                header,
                ("caller", "called", "counterparty", "a_number", "b_number", "dialed"),
                ("number", "phone"),
            )
            dur_col = _pick_col(
                header,
                ("duration", "call duration", "talktime", "talk_time"),
                (),
            )
            for row in reader[header_idx + 1:]:
                num = ""
                if num_col >= 0 and num_col < len(row):
                    num = _normalize_phone(str(row[num_col] or "").strip())
                dur = 0
                if dur_col >= 0 and dur_col < len(row):
                    dur = _parse_duration(row[dur_col])
                elif len(row) >= 2 and num:
                    dur = _parse_duration(row[-1])
                if num:
                    count_by_number[num] += 1
                    duration_by_number[num] += dur
                rows_data.append((num or "", dur))

    text_phones = {_normalize_phone(p) for p in _PHONE_RE.findall(text) if _normalize_phone(p)}
    top = [
        {"number": n, "calls": cnt, "duration_s": duration_by_number.get(n, 0)}
        for n, cnt in count_by_number.most_common(6)
    ]
    return {
        "rows": max(len(rows_data), len(text_phones)),
        "unique_numbers": max(len(count_by_number), len(text_phones)),
        "total_duration_s": sum(d for _, d in rows_data),
        "top": top,
        "phones": sorted(text_phones),
    }


def _image_data_url(raw: bytes, mime: str) -> str:
    import base64

    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #

_KIND_LABELS = {
    "photo": "Photo", "fir": "FIR", "call_records": "Call records",
    "forensic": "Forensic", "cctv": "CCTV", "document": "Document",
}


def _bars(pairs: list[tuple[str, int]]) -> str:
    if not pairs:
        return ""
    greatest = max(v for _, v in pairs) or 1
    parts = []
    for label, value in pairs:
        pct = round(value / greatest * 100, 1)
        parts.append(
            '<div class="bar-row">'
            f'<div class="bar-label">{label} — {value}</div>'
            '<div class="bar-track"><div class="bar-fill" '
            f'style="width:{pct}%"></div></div></div>'
        )
    return "".join(parts)


_CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans', 'Noto Sans Devanagari', 'DejaVu Sans', sans-serif; color: #1e293b; font-size: 10.5pt; line-height: 1.5; }
h1 { font-size: 17pt; color: #0f172a; margin: 0 0 4pt; }
h2 { font-size: 12.5pt; color: #0f172a; border-bottom: 2px solid #7c3aed; padding-bottom: 3pt; margin: 14pt 0 6pt; }
.meta table { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
.meta td { padding: 3pt 6pt; border-bottom: 1px solid #e2e8f0; }
.meta td:first-child { color: #64748b; width: 35%; }
.narrative { background: #f8fafc; border-left: 4px solid #7c3aed; padding: 8pt 10pt; border-radius: 3pt; }
table.data { width: 100%; border-collapse: collapse; font-size: 9pt; }
table.data th { background: #f1f5f9; text-align: left; padding: 4pt 6pt; }
table.data td { border-bottom: 1px solid #e2e8f0; padding: 4pt 6pt; vertical-align: top; }
.badge { display: inline-block; background: #ede9fe; color: #5b21b6; border-radius: 8pt; padding: 1pt 7pt; font-size: 8pt; }
.chip { display: inline-block; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8pt; padding: 2pt 8pt; margin: 1.5pt; font-size: 8.5pt; font-family: monospace; }
.bar-row { margin: 3pt 0; }
.bar-label { font-size: 8.5pt; margin-bottom: 1pt; }
.bar-track { background: #eef2ff; border-radius: 2pt; height: 10pt; width: 100%; }
.bar-fill { background: #7c3aed; height: 10pt; border-radius: 2pt; }
.photos { margin-bottom: 6pt; }
.photo-box { display: inline-block; width: 31%; margin-right: 1.5%; margin-bottom: 6pt; vertical-align: top; border: 1px solid #e2e8f0; border-radius: 4pt; padding: 5pt; }
.photo-box img { width: 100%; border-radius: 2pt; }
.photo-cap { font-size: 7.5pt; color: #64748b; margin-top: 2pt; word-break: break-all; }
.footer { margin-top: 16pt; font-size: 8pt; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 6pt; }
"""


def _esc(value: object) -> str:
    import html

    return html.escape(str(value or ""))


def render_report_html(case, documents, lang: str, analysis: dict) -> str:
    meta = analysis["meta"]
    narrative = analysis["narrative"]
    stats = analysis["stats"]
    cdr = analysis.get("cdr")
    intel = analysis["intel"]
    photos = analysis["photos"]

    rows = "\n".join(
        f'<tr><td><span class="badge">{_esc(_KIND_LABELS.get(d.kind, d.kind))}</span></td>'
        f"<td>{_esc(d.filename)}</td><td>{_format_size(d.size)}</td><td>"
        f"{_esc(_t(lang, 'available') if _file_ok(d) else _t(lang, 'missing'))}</td></tr>"
        for d in documents
    )
    kind_counts = stats["by_kind"]
    bars = _bars([
        (_KIND_LABELS.get(k, k), kind_counts.get(k, 0))
        for k in ("photo", "fir", "call_records", "forensic", "cctv", "document")
        if kind_counts.get(k, 0) > 0
    ])

    cdr_html = ""
    if cdr and cdr["rows"]:
        cdr_bars = _bars([(t["number"], t["calls"]) for t in cdr["top"][:6]])
        cdr_html = (
            f"<h2>{_esc(_t(lang, 'cdr'))}</h2>"
            "<p>"
            f"{_esc(_t(lang, 'total'))}: {cdr['rows']} rows · "
            f"{cdr['unique_numbers']} unique numbers · "
            f"{cdr['total_duration_s']}s talk time"
            "</p>" + cdr_bars
        )
    forensics = meta.get("forensic_excerpt")
    fir_excerpt = meta.get("fir_excerpt")
    forensic_html = ""
    if forensics:
        forensic_html = f"<h2>{_esc(_t(lang, 'forensic'))}</h2><p>{_esc(forensics)}</p>"
    also_fir = ""
    if fir_excerpt:
        also_fir = f"<h2>{_esc(_t(lang, 'fir'))}</h2><p>{_esc(fir_excerpt)}</p>"

    photo_boxes = []
    for ph in photos:
        if ph["embedded"]:
            photo_boxes.append(
                '<div class="photo-box"><img src="' + ph["data_url"] + '" alt="">'
                f'<div class="photo-cap">{_esc(ph["filename"])}</div></div>'
            )
        else:
            photo_boxes.append(
                f'<div class="photo-box"><div class="bar-fill" '
                f'style="height:80pt"></div><div class="photo-cap">{_esc(ph["filename"])} '
                f"({_esc(_t(lang, 'missing'))})</div></div>"
            )
    photos_html = ""
    if photo_boxes:
        photos_html = (
            f"<h2>{_esc(_t(lang, 'photos'))}</h2>"
            '<div class="photos">' + "".join(photo_boxes) + "</div>"
        )

    intel_chips = []
    if intel["phones"]:
        intel_chips.append(
            f'<p><b>{_esc(_t(lang, "phones"))}:</b> '
            + "".join(f'<span class="chip">{_esc(p)}</span>' for p in intel["phones"][:30])
            + "</p>"
        )
    if intel["dates"]:
        intel_chips.append(
            f'<p><b>{_esc(_t(lang, "dates"))}:</b> '
            + "".join(f'<span class="chip">{_esc(d)}</span>' for d in intel["dates"][:30])
            + "</p>"
        )
    if intel["amounts"]:
        intel_chips.append(
            f'<p><b>{_esc(_t(lang, "amounts"))}:</b> '
            + "".join(f'<span class="chip">₹{_esc(a)}</span>' for a in intel["amounts"][:30])
            + "</p>"
        )
    intel_html = ""
    if intel_chips:
        intel_html = (
            f"<h2>{_esc(_t(lang, 'entities'))}</h2>" + "".join(intel_chips)
        )

    created = meta["created_at"]
    body = f"""
<h1>{_esc(_t(lang, 'report_title'))}</h1>
<div class="meta"><table>
<tr><td>{_esc(_t(lang, 'case_id'))}</td><td>{_esc(case.case_id)}</td></tr>
<tr><td>Title</td><td>{_esc(case.title)}</td></tr>
<tr><td>{_esc(_t(lang, 'fir'))}</td><td>{_esc(case.fir_number or '—')}</td></tr>
<tr><td>{_esc(_t(lang, 'status'))}</td><td>{_esc(case.status)}</td></tr>
<tr><td>{_esc(_t(lang, 'language'))}</td><td>{_esc(LANGUAGE_LABELS[lang])}</td></tr>
<tr><td>{_esc(_t(lang, 'generated_at'))}</td><td>{_esc(created)}</td></tr>
</table></div>

<h2>{_esc(_t(lang, 'narrative'))}</h2>
<div class="narrative"><p>{_esc(narrative)}</p></div>

<h2>{_esc(_t(lang, 'evidence'))}</h2>
<table class="data">
<tr><th>{_esc(_t(lang, 'kind'))}</th><th>{_esc(_t(lang, 'filename'))}</th><th>{_esc(_t(lang, 'size'))}</th><th>{_esc(_t(lang, 'status'))}</th></tr>
{rows}
</table>

<h2>{_esc(_t(lang, 'evidence'))} — {_esc(stats['total'])} items</h2>
{bars}

{also_fir}
{cdr_html}
{forensic_html}
{photos_html}
{intel_html}

<div class="footer">{_esc(_t(lang, 'disclaimer'))}</div>
"""
    return (
        "<!doctype html><html lang='" + lang + "'><head><meta charset='utf-8'>"
        "<style>" + _CSS + "</style></head><body>" + body + "</body></html>"
    )


def _file_ok(doc) -> bool:
    return bool(doc.stored_path) and os.path.isfile(doc.stored_path)


def analyze_case(case, documents: list, lang: str) -> dict:
    """Assemble the structured report data for a case."""
    settings = get_settings()
    by_kind: dict[str, list] = defaultdict(list)
    for d in documents:
        by_kind[d.kind].append(d)
    counts = {kind: len(docs) for kind, docs in by_kind.items()}

    intel = {"phones": [], "dates": [], "amounts": []}
    forensic_excerpt = ""
    fir_excerpt = ""
    cdr = None
    photos: list[dict] = []

    for d in documents:
        path = d.stored_path
        kind = d.kind
        if path and os.path.isfile(path):
            raw = open(path, "rb").read()
            ext = _ext_name(d.filename)
            if kind == "fir":
                tx = _decode_text(raw)
                fir_excerpt = " ".join(tx.split())[:400]
                _merge_intel(intel, _extract_intel(tx))
            elif kind == "call_records":
                if cdr is None:
                    cdr = _parse_cdr(raw, d.filename)
                _merge_intel(intel, {"phones": cdr.get("phones", [])})
            elif kind == "forensic":
                if ext in _TEXT_EXTS:
                    tx = _decode_text(raw)
                    forensic_excerpt = " ".join(tx.split())[:200]
                    _merge_intel(intel, _extract_intel(tx))
            elif kind == "document" and ext in _TEXT_EXTS:
                _merge_intel(intel, _extract_intel(_decode_text(raw)))
            elif kind == "photo" and ext in _IMAGE_EXTS - {"webp", "heic"}:
                data_url = _image_data_url(raw, d.mime) if len(raw) <= 8 * 1024 * 1024 else None
                photos.append({"filename": d.filename, "data_url": data_url, "embedded": bool(data_url)})

    total = len(documents)
    stats = {
        "photos": counts.get("photo", 0),
        "fir": counts.get("fir", 0),
        "call_records": counts.get("call_records", 0),
        "forensic": counts.get("forensic", 0),
        "cctv": counts.get("cctv", 0),
        "documents": counts.get("document", 0),
        "phones": len(intel["phones"]),
        "total": total,
        "by_kind": counts,
    }
    top_caller = cdr["top"][0]["number"] if cdr and cdr["top"] else None
    narrative = _narrative(lang, stats, top_caller)
    meta = {
        "created_at": case.created_at.isoformat() if case.created_at else "",
        "fir_excerpt": fir_excerpt,
        "forensic_excerpt": forensic_excerpt,
    }
    analysis = {
        "meta": meta,
        "stats": stats,
        "intel": intel,
        "cdr": cdr,
        "photos": photos,
        "narrative": narrative,
        "lang": lang,
    }
    analysis["html"] = render_report_html(case, documents, lang, analysis)
    return analysis


def render_pdf(case, documents: list, lang: str, analysis: dict) -> bytes:
    """Render the report HTML to PDF bytes (WeasyPrint; Devanagari-safe)."""
    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ReportUnavailableError("PDF engine not available") from exc
    html = analysis.get("html") or render_report_html(case, documents, lang, analysis)
    try:
        return HTML(string=html).write_pdf()
    except ReportUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 - layout dependent
        logger.warning("weasyprint render failed: %s", exc)
        raise ReportUnavailableError("PDF rendering failed") from exc


# --------------------------------------------------------------------------- #
# File persistence helpers for the route layer
# --------------------------------------------------------------------------- #

def store_upload(case_id: str, filename: str, raw: bytes, mime: str) -> tuple[str, str, int]:
    """Persist an uploaded file under ``UPLOAD_DIR/<case_id>/``.

    Returns ``(stored_path, safe_kind_agnostic_filename, size)``.
    """
    settings = get_settings()
    case_dir = Path(settings.UPLOAD_DIR) / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    safe = f"{uuid.uuid4().hex}.{_safe_ext(filename)}"
    target = case_dir / safe
    target.write_bytes(raw)
    return str(target), safe, len(raw)