"""Cross-platform system metrics for heartbeats (psutil if available)."""

from __future__ import annotations

import platform
import socket

try:
    import psutil  # type: ignore

    HAS_PSUTIL = True
except ImportError:  # pragma: no cover
    psutil = None
    HAS_PSUTIL = False


def system_metrics() -> dict:
    if not HAS_PSUTIL:
        return {"cpu_usage": 0.0, "memory_usage": 0.0}
    return {
        "cpu_usage": round(psutil.cpu_percent(interval=None) or 0.0, 1),
        "memory_usage": round(psutil.virtual_memory().percent or 0.0, 1),
    }


def os_info() -> dict:
    return {"os_version": platform.platform()}


def local_ip() -> str:
    """Best-effort primary outbound IPv4 address.

    Opens a UDP socket (no packets sent) purely to discover the interface
    used to reach the network. Falls back to the loopback address.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        finally:
            sock.close()
    except Exception:
        return "127.0.0.1"
