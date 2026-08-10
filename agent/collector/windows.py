"""Windows Event Log readers.

``WindowsEventReader`` uses the Windows Event Log API (pywin32) and is only
available on Windows. ``SimulatedEventReader`` emits realistic synthetic
Security/System events so the agent can be demoed on any platform.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Iterator

try:
    import win32evtlog  # type: ignore
    HAS_WINEVT = True
except ImportError:  # pragma: no cover
    win32evtlog = None
    HAS_WINEVT = False


class WindowsEventReader:
    """Reads Windows Event Log channels using the native Event Log API."""

    def __init__(self, channels: list[str], lookback_seconds: int = 300, event_id_filter: list[int] | None = None):
        if not HAS_WINEVT:
            raise RuntimeError("pywin32 (win32evtlog) is required on Windows")
        self.channels = channels
        self.lookback = lookback_seconds
        self.filter = set(event_id_filter or [])
        self._handles: dict[str, object] = {}

    def _open(self, channel: str) -> object:
        return win32evtlog.OpenEventLog(None, channel)  # type: ignore[attr-defined]

    def read_batch(self, batch_size: int) -> list[dict]:
        records: list[dict] = []
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ  # type: ignore[attr-defined]
        for channel in self.channels:
            if len(records) >= batch_size:
                break
            try:
                handle = self._handles.setdefault(channel, self._open(channel))
                for _ in range(batch_size * 2):
                    if len(records) >= batch_size:
                        break
                    try:
                        event = win32evtlog.ReadEventLog(handle, flags, 0)  # type: ignore[attr-defined]
                    except Exception:
                        break
                    if not event:
                        break
                    for rec in event:
                        rec_id = getattr(rec, "EventID", None)
                        if self.filter and rec_id not in self.filter:
                            continue
                        records.append(self._to_dict(rec))
            except Exception:
                continue
        return records

    @staticmethod
    def _to_dict(rec) -> dict:
        time_created = getattr(rec, "TimeGenerated", None)
        if isinstance(time_created, time.struct_time):
            time_created = datetime(*time_created[:6]).replace(tzinfo=timezone.utc)
        raw_xml = None
        try:
            raw_xml = win32evtlogutil.SafeFormatMessage(rec, None)  # type: ignore[attr-defined]
        except Exception:
            pass
        return {
            "event_id": getattr(rec, "EventID", None),
            "provider": getattr(rec, "SourceName", None),
            "computer": getattr(rec, "ComputerName", None),
            "time_created": time_created,
            "user": None,
            "data": {},
            "raw_xml": raw_xml,
            "source": "windows",
        }

    def close(self) -> None:
        for handle in self._handles.values():
            try:
                win32evtlog.CloseEventLog(handle)  # type: ignore[attr-defined]
            except Exception:
                pass
        self._handles.clear()


# ---------------------------------------------------------------------------
# Simulated reader (cross-platform development / demos)
# ---------------------------------------------------------------------------

_EVENT_TEMPLATES = [
    (4624, "Microsoft-Windows-Security-Auditing", "Logon Success", {"LogonType": "3", "TargetUserName": "domain\\admin", "IpAddress": "10.0.4.18"}, "success"),
    (4625, "Microsoft-Windows-Security-Auditing", "Logon Failure", {"LogonType": "3", "TargetUserName": "domain\\svc_backup", "IpAddress": "10.0.4.18", "SubStatus": "0xC000006A"}, "failed"),
    (4688, "Microsoft-Windows-Security-Auditing", "Process Created", {"NewProcessName": "C:\\Windows\\System32\\cmd.exe", "CommandLine": "cmd.exe /c whoami"}, "process"),
    (4720, "Microsoft-Windows-Security-Auditing", "User Created", {"TargetUserName": "temp_analyst", "SubjectUserName": "DOMAIN\\admin"}, "user"),
    (4732, "Microsoft-Windows-Security-Auditing", "Member Added", {"TargetUserName": "temp_analyst", "GroupName": "Administrators"}, "group"),
    (1102, "Microsoft-Windows-Security-Auditing", "Audit Log Cleared", {"SubjectUserName": "DOMAIN\\admin"}, "audit"),
    (7045, "Service Control Manager", "Service Installed", {"ServiceName": "svchost_update", "ImagePath": "C:\\Temp\\svchost.exe"}, "service"),
    (4688, "Microsoft-Windows-Security-Auditing", "Process Created", {"NewProcessName": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "CommandLine": "powershell.exe -enc JABjAG8AbQBtAGEAbgBkAA=="}, "process"),
]


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class SimulatedEventReader:
    """Generates synthetic Windows-style events for demos and development."""

    def __init__(self, rate: float = 1.0, seed: int = 42):
        self.rate = rate
        self.rng = random.Random(seed)
        self._hosts = [f"PC-{self.rng.randint(1, 99):02d}-{self.rng.randint(1000, 9999)}" for _ in range(3)]
        self._started = time.monotonic()

    def read_batch(self, batch_size: int) -> list[dict]:
        n = max(1, int(batch_size * self.rate * (self._interval())))
        n = min(n, batch_size)
        records = [self._next() for _ in range(n)]
        return records

    def _interval(self) -> float:
        elapsed = max(0.05, time.monotonic() - self._started)
        self._started = time.monotonic()
        return elapsed

    def _next(self) -> dict:
        event_id, provider, _, data, outcome = self.rng.choice(_EVENT_TEMPLATES)
        ts = datetime.now(timezone.utc) - timedelta(seconds=self.rng.random() * 8)
        host = self.rng.choice(self._hosts)
        event_data = "".join(
            f"<Data Name=\"{name}\">{_escape_xml(str(value))}</Data>"
            for name, value in data.items()
            if value is not None
        )
        raw_xml = (
            f'<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event" '
            f'xmlns:q="http://schemas.microsoft.com/win/2004/08/events/event">'
            f"<System><Provider Name=\"{provider}\"/><EventID>{event_id}</EventID>"
            f"<Computer>{host}</Computer><TimeCreated SystemTime=\"{ts.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z\"/>"
            f"<Security UserID=\"S-1-5-18\"/></System>"
            f"<EventData>{event_data}</EventData></Event>"
        )
        return {
            "event_id": event_id,
            "provider": provider,
            "computer": host,
            "time_created": ts,
            "user": data.get("TargetUserName"),
            "data": data,
            "raw_xml": raw_xml,
            "source": "windows",
            "outcome": outcome,
        }


def build_reader(settings) -> WindowsEventReader | SimulatedEventReader:
    """Construct the appropriate reader from agent settings."""
    if settings.simulate or not HAS_WINEVT:
        return SimulatedEventReader(rate=settings.simulated_rate, seed=settings.simulated_seed)
    return WindowsEventReader(
        channels=settings.channels,
        lookback_seconds=settings.lookback_seconds,
        event_id_filter=settings.event_id_filter,
    )
