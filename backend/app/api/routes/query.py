"""Template-based natural-language query endpoint.

Explainable, template-first: the query string is matched against a small set
of explicit templates (open alerts, failed logons, graph paths, network
bursts). A template either matches with a confidence score or the request
falls back to guidance — there is NO generative/AI inference here by default.
When ``QUERY_LLM_ENABLED`` is on, a strictly-grounded ``narrative`` is layered
over the template results (see ``app/services/query_llm.py``); it cannot
fabricate rows and degrades to template-only on any failure.

Synthetic-data caveat: when SEED_DEMO_DATA is off, results may be empty;
that is expected, the endpoint does not fabricate answers.
"""

import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.database.session import get_db
from app.models.alert import Alert
from app.models.event import NormalizedEvent
from app.models.unit import Unit
from app.models.user import User
from app.services.query_llm import summarize as maybe_narrate

router = APIRouter(prefix="/query", tags=["query"])

_UNIT_RE = re.compile(r"(?i)unit[\s-]*(?:of\s*)?([a-z0-9]{2,6})")
_USERNAME_RE = re.compile(r"(?i)(?:by|from|for|as)\s+([a-z][a-z0-9_.$-]{1,40})\b")
_SEVERITY_RE = re.compile(r"(?i)\b(critical|high|medium|low|info(?:rmational)?)\b")


@router.post("")
def run_query(
    body: dict,
    user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
):
    query = (body.get("query") or "").strip()
    answer = _answer(db, query)
    narrative = maybe_narrate(query, answer)
    if narrative:
        answer["narrative"] = narrative
    return answer


def _answer(db: Session, query: str) -> dict:
    lowered = query.lower()
    if not query:
        return {
            "template": "help",
            "confidence": "high",
            "query": query,
            "explanation": "Provide a question; no input was given.",
            "results": [],
        }

    unit_code = _UNIT_RE.search(lowered)
    unit_name = unit_code.group(1) if unit_code else None
    unit_ids = _matched_unit_ids(db, unit_name) if unit_name else None

    if "alert" in lowered and any(k in lowered for k in ("open", "current", "today", "active", "acknowledge")):
        return _open_alerts(db, query, severity=_SEVERITY_RE.search(lowered), unit_ids=unit_ids)

    if any(k in lowered for k in ("failed log", "failed login", "failed logon", "brute force", "4625")):
        return _failed_logons(db, query, username=_USERNAME_RE.search(lowered), unit_ids=unit_ids)

    if any(k in lowered for k in ("path between", "link between", "connect", "who connects")):
        return _graph_path(db, query)

    if any(k in lowered for k in ("network", "netflow", "traffic burst", "scan", "ddos")):
        return _network_bursts(db, query, unit_ids=unit_ids)

    return _fallback(query)


def _matched_unit_ids(db: Session, code: str) -> list[str] | None:
    if not code:
        return None
    rows = db.query(Unit.id).filter(Unit.code.ilike(f"%{code}%") | Unit.name.ilike(f"%{code}%")).all()
    return [r[0] for r in rows] or None


def _seal(template: str, query: str, explanation: str, results: list[dict], confidence: str = "high") -> dict:
    return {
        "template": template,
        "query": query,
        "confidence": confidence,
        "explanation": explanation,
        "results": results,
    }


def _open_alerts(db, query, severity, unit_ids):
    q = db.query(Alert).filter(Alert.status.in_(["open", "investigating"]))
    if unit_ids:
        q = q.filter(Alert.unit_id.in_(unit_ids))
    if severity:
        q = q.filter(Alert.severity == severity.group(1))
    rows = q.order_by(Alert.risk_score.desc()).limit(10).all()
    results = [
        {
            "label": f"{a.title} · {a.severity} · risk {a.risk_score}",
            "detail": f"{a.alert_id} — {a.event_count} events, last seen {a.last_seen:%Y-%m-%d %H:%M}",
        }
        for a in rows
    ]
    return _seal(
        "open_alerts",
        query,
        f"Matched the 'open alerts' template{', constrained to a unit' if unit_ids else ''}"
        f"{', severity ' + severity.group(1) if severity else ''}.",
        results,
    )


def _failed_logons(db, query, username, unit_ids):
    q = db.query(NormalizedEvent).filter(NormalizedEvent.event_id.in_([4625, 4624]))
    if unit_ids:
        q = q.filter(NormalizedEvent.unit_id.in_(unit_ids))
    if username:
        q = q.filter(NormalizedEvent.username.ilike(f"%{username.group(1)}%"))
    rows = q.order_by(NormalizedEvent.timestamp.desc()).limit(10).all()
    results = [
        {
            "label": f"{e.username or '-'} on {e.hostname or '-'} via {e.source_ip or '-'}",
            "detail": f"{e.event_id} · {e.timestamp:%Y-%m-%d %H:%M} · {e.action}",
        }
        for e in rows
    ]
    return _seal(
        "failed_logons",
        query,
        "Authentication-related events (4625/4624), most recent first"
        f"{', filtered by unit' if unit_ids else ''}{', filtered by user' if username else ''}.",
        results,
    )


def _graph_path(db, query):
    import re as _re

    entities = re.findall(r"['\"”]([^'\"”]+)['\"”]", query)
    return _seal(
        "graph_path",
        query,
        "Use the Criminal Intelligence Network Map for interactive path finding.",
        [
            {"label": "Entity selector", "detail": "Open /criminal and pick two entities; the path is highlighted."}
        ]
        + ([{"label": f"Cited entity: {e}", "detail": "Searchable in the graph"} for e in entities[:4]] if entities else []),
        "medium",
    )


def _network_bursts(db, query, unit_ids):
    q = db.query(Alert).filter(Alert.rule_id == "RULE-NET-001")
    if unit_ids:
        q = q.filter(Alert.unit_id.in_(unit_ids))
    rows = q.order_by(Alert.risk_score.desc()).limit(10).all()
    results = [
        {
            "label": f"{a.source_ip or '(no source)'} — {a.event_count} flows",
            "detail": f"{a.alert_id} · {a.risk_score} risk · last seen {a.last_seen:%Y-%m-%d %H:%M}",
        }
        for a in rows
    ]
    return _seal(
        "network_bursts",
        query,
        "Matched the traffic-anomaly template. Results come from the NetFlow analyzer "
        "(RULE-NET-001) alerts written to the shared Alert model.",
        results,
    )


def _fallback(query: str) -> dict:
    return _seal(
        "fallback",
        query,
        "No template matched this phrasing. Try: 'open high alerts', 'failed logons by rpatil', "
        "'network scan in last hour', or 'path between two entities'.",
        [],
        "low",
    )