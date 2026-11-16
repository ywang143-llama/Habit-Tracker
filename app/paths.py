"""Application data locations.

When running from source everything lives next to main.py, which keeps the
app portable. A frozen executable keeps its data in the executable's folder
when that folder is writable, and in %LOCALAPPDATA%\\HabitTracker otherwise.
HABIT_TRACKER_HOME overrides all of this.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
FROZEN = bool(getattr(sys, "frozen", False))


def app_base_dir() -> Path:
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return APP_DIR


@lru_cache(maxsize=1)
def data_dir() -> Path:
    override = os.environ.get("HABIT_TRACKER_HOME")
    if override:
        path = Path(override).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    base = app_base_dir()
    try:
        probe = base / f".write-test-{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return base
    except OSError:
        fallback = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        ) / "HabitTracker"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def asset_path(name: str) -> Path:
    """Resolve bundled assets both from source and from a frozen build."""
    base = Path(getattr(sys, "_MEIPASS", APP_DIR))
    return base / "assets" / name
