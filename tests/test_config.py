import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from syspulse.config import Config, load_config, save_config


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = Config()
        self.assertEqual(cfg.refresh_interval_ms, 1000)
        self.assertEqual(cfg.history_points, 60)
        self.assertEqual(cfg.preferred_interface, "auto")
        self.assertEqual(cfg.theme, "dark")

    def test_validation_clamping(self):
        cfg = Config(
            refresh_interval_ms=100,  # below min (500)
            history_points=1000,      # above max (300)
            theme="invalid-theme",
            temperature_unit="X",
        )
        cfg.validate()
        self.assertEqual(cfg.refresh_interval_ms, 500)
        self.assertEqual(cfg.history_points, 300)
        self.assertEqual(cfg.theme, "dark")
        self.assertEqual(cfg.temperature_unit, "C")

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "config.json"
            with patch("syspulse.config.get_config_path", return_value=test_path):
                cfg = Config(refresh_interval_ms=2000, history_points=120)
                saved = save_config(cfg)
                self.assertTrue(saved)
                self.assertTrue(test_path.is_file())

                loaded = load_config()
                self.assertEqual(loaded.refresh_interval_ms, 2000)
                self.assertEqual(loaded.history_points, 120)


if __name__ == "__main__":
    unittest.main()
