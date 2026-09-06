"""Optional grounded-narrative layer for the template query bar.

``/api/query`` is template-first and always returns explainable structured
results. When ``QUERY_LLM_ENABLED`` is set, this module adds a short
natural-language ``narrative`` produced ONLY from those structured results via
a single OpenAI-compatible chat-completions call. The system prompt forbids
inventing facts; when no rows matched, the narrative says so. Any failure
(network, auth, malformed response) degrades gracefully to ``None`` so the
query bar keeps answering from templates.

Enabled via ``QUERY_LLM_ENABLED`` + ``QUERY_LLM_API_KEY`` (+ optional
``QUERY_LLM_BASE_URL`` / ``QUERY_LLM_MODEL``). Default OFF — the demo never
leaves the template guarantee.
"""

import json
import logging
import urllib.request
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a SIEM analyst assistant. You receive a user question and a JSON "
    "summary produced by an explainable template engine. Answer in 1-3 concise "
    "sentences using ONLY the provided data. Never invent entities, counts, "
    "dates, or facts. If the results list is empty, state plainly that no "
    "matching data was found. Do not mention 'template', 'JSON', or any "
    "implementation detail."
)

_MAX_NARRATIVE_CHARS = 1200


def summarize(query: str, answer: dict[str, Any]) -> str | None:
    """Return a grounded narrative for a template answer, or None."""
    settings = get_settings()
    if not settings.QUERY_LLM_ENABLED or not settings.QUERY_LLM_API_KEY:
        return None
    payload = {
        "model": settings.QUERY_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(query, answer)},
        ],
        "temperature": 0.1,
        "max_tokens": 400,
    }
    try:
        text = _chat_completion(
            settings.QUERY_LLM_BASE_URL,
            settings.QUERY_LLM_API_KEY,
            payload,
        )
    except Exception as exc:  # noqa: BLE001 — degrade, never break the query bar
        logger.warning("query_llm degraded to template-only answer: %s", exc)
        return None
    if not text:
        return None
    return text.strip()[:_MAX_NARRATIVE_CHARS]


def _user_prompt(query: str, answer: dict[str, Any]) -> str:
    context = {
        "user_question": query,
        "template": answer.get("template"),
        "confidence": answer.get("confidence"),
        "explanation": answer.get("explanation"),
        "rows": [
            {"label": r.get("label"), "detail": r.get("detail")}
            for r in answer.get("results", [])[:15]
        ],
    }
    return json.dumps(context, ensure_ascii=False)


def _chat_completion(base_url: str, api_key: str, payload: dict) -> str | None:
    """POST an OpenAI-compatible chat completions request (stdlib only)."""
    url = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]