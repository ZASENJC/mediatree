import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings


class ConfigPolicyTest(unittest.TestCase):
    def test_internal_scraper_policy_ignores_env_and_persisted_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            with patch.dict(
                os.environ,
                {
                    "JAVDB_CACHE_HOURS": "1",
                    "JAVDB_REQUEST_INTERVAL": "30",
                    "TMDB_CACHE_HOURS": "1",
                    "BANGUMI_CACHE_HOURS": "1",
                },
            ):
                settings = Settings(data_dir=str(data_dir))

            self.assertEqual(settings.javdb_cache_hours, 24)
            self.assertEqual(settings.javdb_request_interval, 3.0)
            self.assertEqual(settings.tmdb_cache_hours, 168)
            self.assertEqual(settings.bangumi_cache_hours, 168)

            with open(settings.config_path, "w") as f:
                json.dump(
                    {
                        "javdb_enabled": False,
                        "javdb_cache_hours": 2,
                        "javdb_request_interval": 12,
                        "tmdb_cache_hours": 2,
                        "bangumi_cache_hours": 2,
                        "tmdb_api_key": "tmdb-key",
                    },
                    f,
                )

            settings.load_persisted_config()

            self.assertFalse(settings.javdb_enabled)
            self.assertEqual(settings.tmdb_api_key, "tmdb-key")
            self.assertEqual(settings.javdb_cache_hours, 24)
            self.assertEqual(settings.javdb_request_interval, 3.0)
            self.assertEqual(settings.tmdb_cache_hours, 168)
            self.assertEqual(settings.bangumi_cache_hours, 168)

            settings.save_config()
            with open(settings.config_path, "r") as f:
                saved = json.load(f)

            self.assertNotIn("javdb_cache_hours", saved)
            self.assertNotIn("javdb_request_interval", saved)
            self.assertNotIn("tmdb_cache_hours", saved)
            self.assertNotIn("bangumi_cache_hours", saved)


if __name__ == "__main__":
    unittest.main()
