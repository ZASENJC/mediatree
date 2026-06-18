import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

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
                        "javdb_cache_hours": 2,
                        "javdb_request_interval": 12,
                        "tmdb_cache_hours": 2,
                        "bangumi_cache_hours": 2,
                        "tmdb_api_key": "tmdb-key",
                    },
                    f,
                )

            settings.load_persisted_config()

            self.assertEqual(settings.tmdb_api_key, "")
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
            self.assertNotIn("javdb_enabled", saved)
            self.assertNotIn("tmdb_api_key", saved)


class JavdatabaseConfigPolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_javdatabase_scraper_ignores_deprecated_global_enabled_flag(self):
        from app import javdb

        cached_result = {"title": "Cached JAV metadata"}
        with (
            patch.object(javdb, "settings", SimpleNamespace()),
            patch.object(javdb, "_get_cached", AsyncMock(return_value=cached_result)),
        ):
            self.assertEqual(await javdb.search_javdb("ABP-123"), cached_result)


class ConfigApiPolicyTest(unittest.TestCase):
    def test_config_api_does_not_expose_or_apply_deprecated_javdb_enabled(self):
        from app import config, main

        original_auth_user = config.settings.auth_user
        original_auth_pass = config.settings.auth_pass
        original_auth_password_hash = config.settings.auth_password_hash
        try:
            config.settings.auth_user = "admin"
            config.settings.auth_pass = "secret"
            config.settings.auth_password_hash = ""
            client = TestClient(main.app)
            token = base64.b64encode(b"admin:secret").decode()
            headers = {"Authorization": f"Basic {token}"}

            self.assertNotIn("javdb_enabled", client.get("/api/config", headers=headers).json())

            response = client.post("/api/config", json={"javdb_enabled": False}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("javdb_enabled", response.json())
            self.assertFalse(hasattr(config.settings, "javdb_enabled"))
        finally:
            config.settings.auth_user = original_auth_user
            config.settings.auth_pass = original_auth_pass
            config.settings.auth_password_hash = original_auth_password_hash

    def test_config_api_does_not_expose_or_apply_tmdb_api_key(self):
        from app import config, main

        original_auth_user = config.settings.auth_user
        original_auth_pass = config.settings.auth_pass
        original_auth_password_hash = config.settings.auth_password_hash
        original_tmdb_api_key = config.settings.tmdb_api_key
        try:
            config.settings.auth_user = "admin"
            config.settings.auth_pass = "secret"
            config.settings.auth_password_hash = ""
            config.settings.tmdb_api_key = "legacy-key"
            client = TestClient(main.app)
            token = base64.b64encode(b"admin:secret").decode()
            headers = {"Authorization": f"Basic {token}"}

            self.assertNotIn("tmdb_api_key", client.get("/api/config", headers=headers).json())

            response = client.post("/api/config", json={"tmdb_api_key": "new-key"}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("tmdb_api_key", response.json())
            self.assertEqual(config.settings.tmdb_api_key, "legacy-key")
        finally:
            config.settings.auth_user = original_auth_user
            config.settings.auth_pass = original_auth_pass
            config.settings.auth_password_hash = original_auth_password_hash
            config.settings.tmdb_api_key = original_tmdb_api_key

    def test_config_api_allows_clearing_tmdb_access_token(self):
        from app import config, main

        original_auth_user = config.settings.auth_user
        original_auth_pass = config.settings.auth_pass
        original_auth_password_hash = config.settings.auth_password_hash
        original_tmdb_access_token = config.settings.tmdb_access_token
        try:
            config.settings.auth_user = "admin"
            config.settings.auth_pass = "secret"
            config.settings.auth_password_hash = ""
            config.settings.tmdb_access_token = "legacy-token"
            client = TestClient(main.app)
            token = base64.b64encode(b"admin:secret").decode()
            headers = {"Authorization": f"Basic {token}"}

            response = client.post("/api/config", json={"tmdb_access_token": ""}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(config.settings.tmdb_access_token, "")
        finally:
            config.settings.auth_user = original_auth_user
            config.settings.auth_pass = original_auth_pass
            config.settings.auth_password_hash = original_auth_password_hash
            config.settings.tmdb_access_token = original_tmdb_access_token


if __name__ == "__main__":
    unittest.main()
