from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.habits import Habit, HabitStore, calculate_streak, normalise_name

TODAY = date(2026, 11, 15)


def keys(*offsets: int) -> set[str]:
    return {(TODAY + timedelta(days=offset)).isoformat() for offset in offsets}


class StreakTests(unittest.TestCase):
    def test_empty_history(self) -> None:
        self.assertEqual(calculate_streak(set(), TODAY), 0)

    def test_counts_back_from_today(self) -> None:
        self.assertEqual(calculate_streak(keys(0, -1, -2), TODAY), 3)

    def test_counts_back_from_yesterday_until_today_is_done(self) -> None:
        self.assertEqual(calculate_streak(keys(-1, -2, -3), TODAY), 3)

    def test_misses_break_the_streak(self) -> None:
        self.assertEqual(calculate_streak(keys(0, -1, -3), TODAY), 2)

    def test_streak_can_expire(self) -> None:
        self.assertEqual(calculate_streak(keys(-2, -3), TODAY), 0)

    def test_single_day(self) -> None:
        self.assertEqual(calculate_streak(keys(0), TODAY), 1)

    def test_future_days_do_not_count(self) -> None:
        self.assertEqual(calculate_streak(keys(1, 2), TODAY), 0)

    def test_long_streak(self) -> None:
        self.assertEqual(calculate_streak(keys(*range(0, -30, -1)), TODAY), 30)


class HabitModelTests(unittest.TestCase):
    def test_toggle_round_trip(self) -> None:
        habit = Habit(id="a", name="Read", created=TODAY.isoformat())
        self.assertFalse(habit.is_done(TODAY))
        self.assertTrue(habit.toggle(TODAY))
        self.assertTrue(habit.is_done(TODAY))
        self.assertEqual(habit.streak(TODAY), 1)
        self.assertEqual(habit.streak(TODAY + timedelta(days=1)), 1)
        self.assertFalse(habit.toggle(TODAY))
        self.assertFalse(habit.is_done(TODAY))

    def test_history_is_deduplicated_when_loaded(self) -> None:
        habit = Habit.from_dict(
            {
                "id": "b",
                "name": "  Read   daily  ",
                "created": "not-a-date",
                "history": ["2026-11-14", "2026-11-14", "nope", 7],
            },
            fallback_created="2026-11-15",
        )
        assert habit is not None
        self.assertEqual(habit.name, "Read daily")
        self.assertEqual(habit.created, "2026-11-15")
        self.assertEqual(habit.completed, {"2026-11-14"})

    def test_invalid_entries_are_ignored(self) -> None:
        self.assertIsNone(Habit.from_dict({"name": ""}, "2026-11-15"))
        self.assertIsNone(Habit.from_dict({"name": 5}, "2026-11-15"))
        self.assertIsNone(Habit.from_dict("not a dict", "2026-11-15"))

    def test_normalise_name(self) -> None:
        self.assertEqual(normalise_name("  Drink \t water "), "Drink water")


class HabitStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.path = Path(self._temp.name) / "habits.json"
        self.store = HabitStore(self.path)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_starts_empty(self) -> None:
        self.assertEqual(self.store.habits, [])
        self.assertEqual(self.store.total, 0)

    def test_utf8_bom_is_tolerated(self) -> None:
        self.path.write_text(
            "\ufeff"
            + json.dumps(
                {
                    "version": 1,
                    "habits": [{"id": "bom", "name": "Read", "history": []}],
                }
            ),
            encoding="utf-8",
        )
        store = HabitStore(self.path)
        self.assertEqual([habit.name for habit in store.habits], ["Read"])
        self.assertTrue(self.path.exists())

    def test_add_save_and_reload(self) -> None:
        habit = self.store.add("  Drink   water ", TODAY)
        self.store.save()

        reloaded = HabitStore(self.path)
        self.assertEqual(len(reloaded.habits), 1)
        self.assertEqual(reloaded.habits[0].name, "Drink water")
        self.assertEqual(reloaded.habits[0].id, habit.id)

    def test_completion_persists(self) -> None:
        habit = self.store.add("Read", TODAY)
        self.assertTrue(self.store.toggle(habit.id, TODAY))
        self.store.save()

        reloaded = HabitStore(self.path)
        self.assertTrue(reloaded.get(habit.id).is_done(TODAY))
        self.assertEqual(reloaded.done_count(TODAY), 1)

    def test_name_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.store.add("   ", TODAY)
        with self.assertRaises(ValueError):
            self.store.add("x" * 61, TODAY)

        self.store.add("Read", TODAY)
        with self.assertRaises(ValueError):
            self.store.add("  read ", TODAY)

    def test_remove(self) -> None:
        habit = self.store.add("Read", TODAY)
        self.assertTrue(self.store.remove(habit.id))
        self.assertFalse(self.store.remove(habit.id))
        self.assertEqual(self.store.habits, [])

    def test_move_reorders_and_persists(self) -> None:
        first = self.store.add("First", TODAY)
        self.store.add("Second", TODAY)
        third = self.store.add("Third", TODAY)

        self.assertTrue(self.store.move(third.id, 0))
        self.assertEqual(
            [habit.name for habit in self.store.habits],
            ["Third", "First", "Second"],
        )
        self.assertFalse(self.store.move(third.id, 0))

        self.store.save()
        reloaded = HabitStore(self.path)
        self.assertEqual(
            [habit.name for habit in reloaded.habits],
            ["Third", "First", "Second"],
        )

        self.assertTrue(self.store.move(third.id, 99))
        self.assertEqual(
            [habit.name for habit in self.store.habits],
            ["First", "Second", "Third"],
        )
        self.assertTrue(self.store.move(third.id, -5))
        self.assertEqual(
            [habit.name for habit in self.store.habits],
            ["Third", "First", "Second"],
        )
        self.assertFalse(self.store.move("missing", 1))
        self.assertFalse(self.store.move(first.id, "nope"))  # type: ignore[arg-type]

    def test_corrupt_file_is_quarantined(self) -> None:
        self.path.write_text("{ this is not json", encoding="utf-8")
        store = HabitStore(self.path)
        self.assertEqual(store.habits, [])
        self.assertFalse(self.path.exists())
        self.assertTrue(list(self.path.parent.glob("habits.corrupt-*.json")))

    def test_wrong_shape_is_quarantined(self) -> None:
        self.path.write_text(json.dumps({"habits": "nope"}), encoding="utf-8")
        store = HabitStore(self.path)
        self.assertEqual(store.habits, [])
        self.assertTrue(list(self.path.parent.glob("habits.corrupt-*.json")))

    def test_bad_entries_are_skipped(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "habits": [
                        {"name": 5},
                        {"name": "Read", "history": ["2026-11-14"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        store = HabitStore(self.path)
        self.assertEqual([habit.name for habit in store.habits], ["Read"])

    def test_duplicate_ids_are_replaced(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "habits": [
                        {"id": "same", "name": "One"},
                        {"id": "same", "name": "Two"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        store = HabitStore(self.path)
        self.assertEqual(len(store.habits), 2)
        self.assertNotEqual(store.habits[0].id, store.habits[1].id)

    def test_saved_document_shape(self) -> None:
        habit = self.store.add("Read", TODAY)
        self.store.toggle(habit.id, TODAY)
        self.store.save()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["version"], 1)
        self.assertEqual(raw["habits"][0]["name"], "Read")
        self.assertEqual(raw["habits"][0]["history"], [TODAY.isoformat()])
        self.assertFalse((self.path.parent / "habits.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
