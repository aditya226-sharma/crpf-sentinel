"""Agent configuration: environment variables + optional YAML overlay.

Configuration precedence:
1. Environment variables (CYBERRAKSHAK_*)
2. YAML config file (config/agent.yaml)
3. Built-in defaults
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class Settings:
    # Identity
    agent_id: str = "WIN-AGT-0001"
    unit_id: str | None = None
    hostname: str | None = None

    # Server
    server_url: str = "http://localhost:8000"
    api_token: str = ""
    verify_ssl: bool = True
    connect_timeout: float = 10.0
    request_timeout: float = 30.0

    # Collection
    channels: list[str] = field(default_factory=lambda: ["Security", "System", "Application"])
    query: str | None = None  # optional XPath query
    max_batch: int = 200
    poll_interval_seconds: float = 5.0
    lookback_seconds: int = 300
    event_id_filter: list[int] = field(default_factory=list)
    include_raw_xml: bool = True
    metrics_interval_seconds: float = 15.0

    # Buffering
    spool_dir: str = "spool"
    spool_max_mb: int = 512
    max_retry_backoff: float = 60.0

    # Simulation (non-Windows dev)
    simulate: bool = False
    simulated_rate: float = 1.0
    simulated_seed: int = 42

    @property
    def effective_hostname(self) -> str:
        if self.hostname:
            return self.hostname
        import socket

        return socket.gethostname()

    @classmethod
    def from_env_and_file(cls, path: str | None = None) -> "Settings":
        defaults = cls()

        file_data: dict = {}
        candidates = [path, str(Path(__file__).resolve().parent.parent / "config" / "agent.yaml")]
        for cand in candidates:
            if not cand:
                continue
            p = Path(cand)
            if p.is_file() and yaml is not None:
                with p.open("r", encoding="utf-8") as fh:
                    raw = yaml.safe_load(fh) or {}
                file_data = {k: v for k, v in raw.items() if v is not None}
                break

        def get(name: str, default):
            env = os.environ.get(f"CYBERRAKSHAK_{name.upper()}")
            if env is not None:
                return env
            if name in file_data:
                return file_data[name]
            return default

        def get_bool(name: str, default):
            raw = get(name, "true" if default else "false")
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}

        def get_int(name: str, default):
            raw = get(name, default)
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        def get_float(name: str, default):
            raw = get(name, default)
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        return cls(
            agent_id=str(get("agent_id", defaults.agent_id)),
            unit_id=get("unit_id", defaults.unit_id),
            hostname=get("hostname", defaults.hostname),
            server_url=str(get("server_url", defaults.server_url)).rstrip("/"),
            api_token=str(get("api_token", defaults.api_token)),
            verify_ssl=get_bool("verify_ssl", defaults.verify_ssl),
            connect_timeout=get_float("connect_timeout", defaults.connect_timeout),
            request_timeout=get_float("request_timeout", defaults.request_timeout),
            channels=list(get("channels", defaults.channels)),
            query=get("query", defaults.query),
            max_batch=get_int("max_batch", defaults.max_batch),
            poll_interval_seconds=get_float("poll_interval_seconds", defaults.poll_interval_seconds),
            lookback_seconds=get_int("lookback_seconds", defaults.lookback_seconds),
            event_id_filter=list(get("event_id_filter", defaults.event_id_filter)),
            include_raw_xml=get_bool("include_raw_xml", defaults.include_raw_xml),
            metrics_interval_seconds=get_float("metrics_interval_seconds", defaults.metrics_interval_seconds),
            spool_dir=str(get("spool_dir", defaults.spool_dir)),
            spool_max_mb=get_int("spool_max_mb", defaults.spool_max_mb),
            max_retry_backoff=get_float("max_retry_backoff", defaults.max_retry_backoff),
            simulate=get_bool("simulate", defaults.simulate),
            simulated_rate=get_float("simulated_rate", defaults.simulated_rate),
            simulated_seed=get_int("simulated_seed", defaults.simulated_seed),
        )
