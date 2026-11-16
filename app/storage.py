"""Small JSON helpers shared by the config and habit stores."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read and decode a JSON file, tolerating a Notepad-style BOM."""
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON to *path* without ever leaving a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")

    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def quarantine(path: Path) -> Path | None:
    """Move a damaged file aside so the app can recover without losing it."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.corrupt-{stamp}{path.suffix}")
    try:
        path.replace(backup)
    except OSError:
        return None
    return backup
