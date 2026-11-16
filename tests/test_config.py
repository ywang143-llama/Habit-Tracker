from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.path = Path(self._temp.name) / "config.json"

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_defaults_when_missing(self) -> None:
        config = ConfigStore(self.path)
        self.assertIsNone(config.config.x)
        self.assertIsNone(config.config.y)
        self.assertTrue(config.config.always_on_top)

    def test_round_trip(self) -> None:
        config = ConfigStore(self.path)
        config.set_position(1200, 80)
        config.set_always_on_top(False)

        reloaded = ConfigStore(self.path)
        self.assertEqual((reloaded.config.x, reloaded.config.y), (1200, 80))
        self.assertFalse(reloaded.config.always_on_top)

    def test_invalid_values_fall_back_to_defaults(self) -> None:
        self.path.write_text(
            json.dumps({"x": "10", "y": True, "always_on_top": "yes"}),
            encoding="utf-8",
        )
        config = ConfigStore(self.path)
        self.assertIsNone(config.config.x)
        self.assertIsNone(config.config.y)
        self.assertTrue(config.config.always_on_top)

    def test_partial_position_is_ignored(self) -> None:
        self.path.write_text(json.dumps({"x": 10}), encoding="utf-8")
        config = ConfigStore(self.path)
        self.assertIsNone(config.config.x)
        self.assertIsNone(config.config.y)

    def test_saved_shape(self) -> None:
        config = ConfigStore(self.path)
        config.set_position(30, 40)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            raw,
            {"x": 30, "y": 40, "always_on_top": True},
        )
        self.assertFalse((self.path.parent / "config.json.tmp").exists())

    def test_not_written_when_unchanged(self) -> None:
        config = ConfigStore(self.path)
        config.set_always_on_top(True)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
