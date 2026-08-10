"""HTTPS transport to the CyberRakshak backend.

Batches spooled events into ``POST /api/ingest`` requests authenticated with
the agent bearer token, with exponential backoff and retries. Periodic
heartbeats keep the agent marked ``online`` on the server.
"""

from __future__ import annotations

import logging
import random
import time

import requests

log = logging.getLogger("cyberrakshak.transport")


class Transport:
    def __init__(self, settings, stop_event=None):
        self.settings = settings
        self.stop_event = stop_event
        self.session = requests.Session()
        self.session.headers.update(
            {"x-agent-token": settings.api_token, "Content-Type": "application/json"}
        )
        self.base = settings.server_url
        self._retry_backoff = 1.0

    def _headers(self) -> dict:
        return {"x-agent-token": self.settings.api_token}

    def _sleep_interruptible(self, seconds: float) -> bool:
        """Sleep in small slices; return False if a stop was requested."""
        if self.stop_event is None:
            time.sleep(seconds)
            return True
        remaining = seconds
        while remaining > 0:
            if self.stop_event.is_set():
                return False
            slice_s = min(0.2, remaining)
            time.sleep(slice_s)
            remaining -= slice_s
        return True

    def send(self, records: list[dict], heartbeat: dict | None = None) -> dict:
        """POST a batch of normalized events. Returns server response dict."""
        body = {
            "agent_id": self.settings.agent_id,
            "unit_id": self.settings.unit_id,
            "hostname": self.settings.effective_hostname,
            "events": records,
        }
        if heartbeat:
            body["heartbeat"] = heartbeat
        url = f"{self.base}/api/logs/ingest"
        resp = self.session.post(
            url,
            json=body,
            timeout=(self.settings.connect_timeout, self.settings.request_timeout),
            verify=self.settings.verify_ssl,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"ingest {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    def with_retry(self, fn, attempts: int = 4) -> object:
        """Run a callable with exponential backoff + jitter."""
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                result = fn()
                self._retry_backoff = 1.0
                return result
            except Exception as exc:  # network error / 5xx
                last_exc = exc
                delay = min(self.settings.max_retry_backoff, self._retry_backoff)
                delay *= 1 + random.uniform(-0.2, 0.2)
                log.warning("attempt %s failed (%s); retrying in %.1fs", attempt + 1, exc, delay)
                if not self._sleep_interruptible(delay):
                    raise RuntimeError(f"stopped during retry backoff: {exc}")
                self._retry_backoff = min(self.settings.max_retry_backoff, self._retry_backoff * 2)
        raise RuntimeError(f"transport retries exhausted: {last_exc}")

    def heartbeat(self, metrics: dict) -> dict:
        """Send a lightweight heartbeat (bearer-auth'd); {} on failure."""
        try:
            url = f"{self.base}/api/agents/heartbeat"
            resp = self.session.post(
                url,
                json=metrics,
                timeout=(self.settings.connect_timeout, self.settings.request_timeout),
                verify=self.settings.verify_ssl,
            )
            if resp.status_code >= 400:
                log.warning("heartbeat failed: %s %s", resp.status_code, resp.text[:200])
                return {}
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("heartbeat error: %s", exc)
            return {}

    def close(self) -> None:
        self.session.close()
