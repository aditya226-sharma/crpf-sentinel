"""Phase F — crime case dossier: evidence upload + trilingual report + PDF.

Proves a case can be created, heterogeneous evidence (photo, FIR text, call
records CSV, forensic note, CCTV clip) uploaded and auto-classified, and a
report assembled in English / Hindi / Hinglish with extracted phones and CDR
statistics, plus a PDF download when the WeasyPrint engine is available.
"""

import base64
import io

import pytest
from fastapi.testclient import TestClient


def _png_bytes() -> bytes:
    try:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (80, 60), (120, 30, 90)).save(buf, "PNG")
        return buf.getvalue()
    except ImportError:
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )


_PNG = _png_bytes()

_FIR_TXT = (
    b"FIR No. 0123/2026 dated 05/08/2026. Complainant reported theft of "
    b"Rs. 250000. Suspect phone 9810123456 seen near the location on "
    b"15/08/2026.\n"
)

_CDR_CSV = (
    b"id,caller_number,called_number,date,time,duration_sec,type\n"
    b"1,919810123456,919810223456,05/08/2026,10:12,90,outgoing\n"
    b"2,919810123456,919810323456,05/08/2026,11:00,45,outgoing\n"
    b"3,919810223456,919810423456,05/08/2026,12:15,120,incoming\n"
)

_FORENSIC_TXT = b"Forensic analysis of the recovered device: no tampering detected.\n"


def _create_case(client: TestClient, admin_headers: dict[str, str]) -> dict:
    res = client.post(
        "/api/case-intake",
        headers=admin_headers,
        data={
            "title": "Marketplace theft probe",
            "fir_number": "0123/2026",
            "description": "Synthetic demo case for the report pipeline.",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _upload_all(client: TestClient, admin_headers: dict[str, str], case_id: str) -> dict:
    res = client.post(
        f"/api/case-intake/{case_id}/documents",
        headers=admin_headers,
        files=[
            ("files", ("crime-scene-1.png", _PNG, "image/png")),
            ("files", ("FIR_0123.txt", _FIR_TXT, "text/plain")),
            ("files", ("call_records_0123.csv", _CDR_CSV, "text/csv")),
            ("files", ("forensic_report.txt", _FORENSIC_TXT, "text/plain")),
            ("files", ("cctv_front_gate.mp4", b"00000000VIDEO", "video/mp4")),
        ],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["accepted"] == 5
    return body


def test_case_create_and_document_classification(client: TestClient, admin_headers: dict[str, str]):
    case = _create_case(client, admin_headers)
    assert case["case_id"].startswith("CSI-")
    up = _upload_all(client, admin_headers, case["case_id"])
    kinds = {d["kind"] for d in up["documents"]}
    assert kinds == {"photo", "fir", "call_records", "forensic", "cctv"}

    detail = client.get(f"/api/case-intake/{case['case_id']}", headers=admin_headers).json()
    assert detail["fir_number"] == "0123/2026"
    assert len(detail["documents"]) == 5


def test_report_english_grounded(client: TestClient, admin_headers: dict[str, str]):
    case = _create_case(client, admin_headers)
    _upload_all(client, admin_headers, case["case_id"])
    res = client.get(
        f"/api/case-intake/{case['case_id']}/report?lang=en", headers=admin_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body["lang"] == "en"
    assert "5" in body["narrative"]
    assert body["stats"]["photos"] == 1 and body["stats"]["call_records"] == 1
    assert "9810123456" in body["intel"]["phones"]
    assert body["cdr"]["rows"] >= 1
    assert body["cdr"]["unique_numbers"] >= 2
    assert isinstance(body["html"], str) and "Evidence" in body["html"]
    # the top caller by count is the FIR-tagged number's counterpart data
    assert body["cdr"]["top"][0]["calls"] >= 2


def test_report_hindi_and_hinglish(client: TestClient, admin_headers: dict[str, str]):
    case = _create_case(client, admin_headers)
    _upload_all(client, admin_headers, case["case_id"])
    hi = client.get(f"/api/case-intake/{case['case_id']}/report?lang=hi", headers=admin_headers)
    assert hi.status_code == 200
    assert "आपराधिक" in hi.json()["html"]
    hg = client.get(
        f"/api/case-intake/{case['case_id']}/report?lang=hinglish", headers=admin_headers
    )
    assert hg.status_code == 200
    assert hg.json()["html"].count("Evidence") >= 1

    bad = client.get(f"/api/case-intake/{case['case_id']}/report?lang=fr", headers=admin_headers)
    assert bad.status_code == 400


def test_report_pdf_download(client: TestClient, admin_headers: dict[str, str]):
    weasyprint = pytest.importorskip("weasyprint")
    assert weasyprint is not None  # keep linter happy
    case = _create_case(client, admin_headers)
    _upload_all(client, admin_headers, case["case_id"])
    res = client.get(
        f"/api/case-intake/{case['case_id']}/report.pdf", headers=admin_headers
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"