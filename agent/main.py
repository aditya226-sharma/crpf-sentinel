#!/usr/bin/env python3
"""CyberRakshak Windows Collector Agent — entrypoint.

Usage:
    python -m main [--config config/agent.yaml]

Environment variables (CYBERRAKSHAK_*) override the YAML config, which
overrides built-in defaults. See config/agent.yaml.example.
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from datetime import datetime, timezone

from collector import build_reader
from config.settings import Settings
from parser.windows import normalize
from spool.spool import Spool
from transport import Transport
from utils import local_ip, os_info, system_metrics

log = logging.getLogger("cyberrakshak")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


class CyberRakshakAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = threading.Event()
        self.reader = build_reader(settings)
        self.spool = Spool(settings.spool_dir, max_mb=settings.spool_max_mb)
        self.transport = Transport(settings, stop_event=self._stop)
        self._stats = {"collected": 0, "sent": 0, "failed": 0}
        self._os_info = os_info()

    # -- lifecycle ----------------------------------------------------------
    def run(self) -> None:
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        log.info(
            "CyberRakshak agent v%s starting | agent=%s server=%s mode=%s",
            "1.0.0",
            self.settings.agent_id,
            self.settings.server_url,
            "simulated" if self.settings.simulate else "windows-evtlog",
        )
        if not self.settings.api_token:
            log.warning("CYBERRAKSHAK_API_TOKEN is empty — server will reject requests")

        last_heartbeat = 0.0
        while not self._stop.is_set():
            try:
                self.collect_and_flush()
                if self._stop.is_set():
                    break
                now = time.monotonic()
                if now - last_heartbeat >= self.settings.metrics_interval_seconds:
                    self.send_heartbeat()
                    last_heartbeat = now
            except Exception as exc:  # noqa: BLE001 — keep the loop alive
                log.error("loop error: %s", exc)
            self._stop.wait(self.settings.poll_interval_seconds)

        self.shutdown()
        log.info("agent stopped | sent=%s failed=%s", self._stats["sent"], self._stats["failed"])

    def shutdown(self) -> None:
        self.reader.close() if hasattr(self.reader, "close") else None
        self.transport.close()

    def _on_signal(self, *_args) -> None:
        log.info("signal received; shutting down")
        self._stop.set()

    # -- core loop ----------------------------------------------------------
    def collect_and_flush(self) -> None:
        raw = self.reader.read_batch(self.settings.max_batch)
        if raw:
            normalized = [normalize(r) for r in raw]
            kept = self.spool.append(normalized)
            self._stats["collected"] += kept
            log.debug("collected %s events (%s spooled)", len(raw), kept)

        pending = self.spool.drain()
        if not pending:
            return
        self._flush_all(pending)

    def _flush_all(self, pending: list[dict]) -> None:
        chunk_size = min(self.settings.max_batch, 2000)
        sent = 0
        for i in range(0, len(pending), chunk_size):
            chunk = pending[i:i + chunk_size]
            if self._flush(chunk):
                sent += len(chunk)
            else:
                # server unreachable → put everything (incl. later chunks) back
                self.spool.append(pending[i:])
                self._stats["failed"] += len(pending) - sent
                return
        self._stats["sent"] += sent
        if sent:
            log.info("flushed %s events to %s", sent, self.settings.server_url)

    def _flush(self, pending: list[dict]) -> bool:
        try:
            self.transport.with_retry(lambda: self.transport.send(pending))
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("could not deliver %s events: %s", len(pending), exc)
            return False

    def send_heartbeat(self) -> None:
        spool_mb = self.spool.size_mb
        metrics = {
            "hostname": self.settings.effective_hostname,
            "ip_address": local_ip(),
            "os_version": self._os_info["os_version"],
            "agent_version": "1.0.0",
            "events_per_sec": int(self._stats["collected"] / max(1, self.settings.metrics_interval_seconds)),
            "buffer_size": int(spool_mb * 1024 * 1024),
            "sync_status": "healthy" if spool_mb < 1 else f"buffering {spool_mb:.1f} MB",
            **system_metrics(),
        }
        resp = self.transport.heartbeat(metrics)
        log.debug("heartbeat -> %s", resp or "no response")
        self._stats["collected"] = 0


def main() -> None:
    parser = argparse.ArgumentParser(description="CyberRakshak Windows Collector Agent")
    parser.add_argument("--config", default=None, help="path to agent YAML config")
    parser.add_argument("--simulate", action="store_true", help="force simulated events")
    args = parser.parse_args()

    settings = Settings.from_env_and_file(args.config)
    if args.simulate:
        settings.simulate = True

    if not settings.agent_id:
        raise SystemExit("agent_id is required (CYBERRAKSHAK_AGENT_ID)")

    CyberRakshakAgent(settings).run()


if __name__ == "__main__":
    main()
