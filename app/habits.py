"""Habit model, streak calculation, and habits.json persistence."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

from .storage import quarantine, read_json, write_json_atomic

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 60
SCHEMA_VERSION = 1


def date_key(day: date) -> str:
    return day.isoformat()


def _valid_date_key(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def calculate_streak(completed: Iterable[str], today: date) -> int:
    """Count consecutive completed days ending today or yesterday.

    A streak stays alive during the current day: if today has not been
    completed yet, consecutive days are counted back from yesterday.
    """
    days = completed if isinstance(completed, set) else set(completed)
    if not days:
        return 0

    cursor = today
    if date_key(cursor) not in days:
        cursor -= timedelta(days=1)

    streak = 0
    key = date_key(cursor)
    while key in days:
        streak += 1
        cursor -= timedelta(days=1)
        key = date_key(cursor)
    return streak


def normalise_name(name: str) -> str:
    return " ".join(name.split())


@dataclass
class Habit:
    id: str
    name: str
    created: str
    completed: set[str] = field(default_factory=set)

    def is_done(self, day: date) -> bool:
        return date_key(day) in self.completed

    def streak(self, today: date) -> int:
        return calculate_streak(self.completed, today)

    def toggle(self, day: date) -> bool:
        """Flip completion for *day* and return the new state."""
        key = date_key(day)
        if key in self.completed:
            self.completed.discard(key)
            return False
        self.completed.add(key)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "history": sorted(self.completed),
        }

    @classmethod
    def from_dict(cls, raw: Any, fallback_created: str) -> Optional["Habit"]:
        if not isinstance(raw, dict):
            return None

        name = raw.get("name")
        if not isinstance(name, str):
            return None
        name = normalise_name(name)[:MAX_NAME_LENGTH]
        if not name:
            return None

        habit_id = raw.get("id")
        if not isinstance(habit_id, str) or not habit_id.strip():
            habit_id = uuid.uuid4().hex

        created = _valid_date_key(raw.get("created")) or fallback_created

        history_raw = raw.get("history", [])
        history: set[str] = set()
        if isinstance(history_raw, list):
            for item in history_raw:
                key = _valid_date_key(item)
                if key is not None:
                    history.add(key)

        return cls(id=habit_id.strip(), name=name, created=created, completed=history)


class HabitStore:
    """Owns the habit list and knows how to read/write habits.json."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.habits: list[Habit] = []
        self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        self.habits = []
        if not self.path.exists():
            return

        try:
            raw = read_json(self.path)
        except (OSError, ValueError) as exc:
            logger.error("Could not read %s: %s", self.path, exc)
            if isinstance(exc, ValueError):
                backup = quarantine(self.path)
                logger.warning("Moved unreadable habit data to %s", backup)
            return

        entries = raw.get("habits") if isinstance(raw, dict) else None
        if not isinstance(entries, list):
            logger.error("Ignoring %s: expected an object with a habits list", self.path)
            backup = quarantine(self.path)
            logger.warning("Moved unexpected habit data to %s", backup)
            return

        seen_ids: set[str] = set()
        fallback_created = date_key(date.today())
        for entry in entries:
            habit = Habit.from_dict(entry, fallback_created)
            if habit is None:
                continue
            if habit.id in seen_ids:
                habit.id = uuid.uuid4().hex
            seen_ids.add(habit.id)
            self.habits.append(habit)

    # ------------------------------------------------------------------ save
    def save(self) -> None:
        write_json_atomic(
            self.path,
            {
                "version": SCHEMA_VERSION,
                "habits": [habit.to_dict() for habit in self.habits],
            },
        )

    # --------------------------------------------------------------- queries
    def get(self, habit_id: str) -> Optional[Habit]:
        return next((habit for habit in self.habits if habit.id == habit_id), None)

    def done_count(self, day: date) -> int:
        return sum(1 for habit in self.habits if habit.is_done(day))

    @property
    def total(self) -> int:
        return len(self.habits)

    # -------------------------------------------------------------- mutation
    def add(self, name: str, today: date) -> Habit:
        name = normalise_name(name)
        if not name:
            raise ValueError("Give your habit a name.")
        if len(name) > MAX_NAME_LENGTH:
            raise ValueError(f"Keep names under {MAX_NAME_LENGTH} characters.")
        if any(habit.name.casefold() == name.casefold() for habit in self.habits):
            raise ValueError("That habit is already on your list.")

        habit = Habit(
            id=uuid.uuid4().hex,
            name=name,
            created=date_key(today),
        )
        self.habits.append(habit)
        return habit

    def remove(self, habit_id: str) -> bool:
        for index, habit in enumerate(self.habits):
            if habit.id == habit_id:
                del self.habits[index]
                return True
        return False

    def move(self, habit_id: str, new_index: int) -> bool:
        """Move a habit to a new zero-based position.

        Returns True when the order changed. The caller is responsible for
        saving the store and refreshing the UI.
        """
        habit = self.get(habit_id)
        if habit is None:
            return False

        try:
            new_index = int(new_index)
        except (TypeError, ValueError):
            return False

        new_index = max(0, min(new_index, len(self.habits) - 1))
        current_index = self.habits.index(habit)
        if new_index == current_index:
            return False

        self.habits.pop(current_index)
        self.habits.insert(new_index, habit)
        return True

    def toggle(self, habit_id: str, day: date) -> bool:
        habit = self.get(habit_id)
        if habit is None:
            raise KeyError(habit_id)
        return habit.toggle(day)
