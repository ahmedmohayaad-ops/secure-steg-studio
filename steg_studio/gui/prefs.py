# steg_studio/gui/prefs.py
"""Tiny JSON preferences store at ~/.steg_studio/prefs.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PATH = Path.home() / ".steg_studio" / "prefs.json"
_DEFAULTS: dict[str, Any] = {"theme": "dark"}


def load() -> dict[str, Any]:
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**_DEFAULTS, **data}
    except (OSError, ValueError):
        pass
    return dict(_DEFAULTS)


def save(prefs: dict[str, Any]) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except OSError:
        pass


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set(key: str, value: Any) -> None:  # noqa: A001 — intentional API
    prefs = load()
    prefs[key] = value
    save(prefs)
