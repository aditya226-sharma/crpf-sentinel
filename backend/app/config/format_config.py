"""Per-format classification catalog, loaded from YAML config files.

Adding a new event code mapping (or an entirely new format) requires editing
YAML only — no Python change. This is the source used by the normalization
engine for every format that flows through the parser registry.
"""

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent

# (format_name, code) -> (category, action, severity), plus per-format defaults.
_catalog: dict[str, dict[str, Any]] = {}


def _load(name: str) -> dict[str, Any]:
    if name not in _catalog:
        path = CONFIG_DIR / "formats" / f"{name}.yaml"
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                _catalog[name] = yaml.safe_load(fh) or {}
    return _catalog.get(name, {})


def classify(format_name: str, code: int | str | None) -> tuple[str, str, str]:
    """Return (category, action, severity) for a code in the given format."""
    catalog = _load(format_name)
    defaults = catalog.get("defaults", {})
    category = defaults.get("category", "security")
    action = defaults.get("action", "observed")
    severity = defaults.get("severity", "informational")

    if code is not None:
        entry = catalog.get("codes", {}).get(str(code))
        if entry:
            return (
                entry.get("category", category),
                entry.get("action", action),
                entry.get("severity", severity),
            )
    return category, action, severity


def formats() -> list[str]:
    """Names of all config formats present on disk, for registry parity checks."""
    return sorted(p.stem for p in (CONFIG_DIR / "formats").glob("*.yaml"))