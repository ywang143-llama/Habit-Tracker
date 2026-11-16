"""Persistent window settings."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .storage import read_json, write_json_atomic

logger = logging.getLogger(__name__)


@dataclass
class Config:
    x: Optional[int] = None
    y: Optional[int] = None
    always_on_top: bool = True


def _optional_int(value: Any) -> Optional[int]:
    # bool is an int subclass, but never a valid coordinate.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class ConfigStore:
    """Loads config.json and saves small updates immediately."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.config = Config()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return

        try:
            raw = read_json(self.path)
        except (OSError, ValueError) as exc:
            logger.warning("Could not read %s: %s", self.path, exc)
            return

        if not isinstance(raw, dict):
            logger.warning("Ignoring %s: expected a JSON object", self.path)
            return

        x = _optional_int(raw.get("x"))
        y = _optional_int(raw.get("y"))
        if x is not None and y is not None:
            self.config.x, self.config.y = x, y

        always_on_top = raw.get("always_on_top")
        if isinstance(always_on_top, bool):
            self.config.always_on_top = always_on_top

    def save(self) -> None:
        write_json_atomic(
            self.path,
            {
                "x": self.config.x,
                "y": self.config.y,
                "always_on_top": self.config.always_on_top,
            },
        )

    def set_position(self, x: int, y: int) -> None:
        x, y = int(x), int(y)
        if (x, y) == (self.config.x, self.config.y):
            return
        self.config.x, self.config.y = x, y
        try:
            self.save()
        except OSError as exc:
            logger.error("Could not save window position: %s", exc)

    def set_always_on_top(self, value: bool) -> None:
        value = bool(value)
        if value == self.config.always_on_top:
            return
        self.config.always_on_top = value
        try:
            self.save()
        except OSError as exc:
            logger.error("Could not save always-on-top setting: %s", exc)
