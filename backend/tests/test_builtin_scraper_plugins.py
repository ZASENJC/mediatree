import asyncio
import base64
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import config, database, main
from app.scrapers.registry import get_scraper, list_scrapers, refresh_scraper_plugins


class BuiltinScraperPluginsTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.media_root = self.root / "media"
        self.data_dir = self.root / "data"
        self.media_root.mkdir()
        self.data_dir.mkdir()

        self.orig_media_root = config.settings.media_root
        self.orig_data_dir = config.settings.data_dir
        self.orig_auth_user = config.settings.auth_user
        self.orig_auth_pass = config.settings.auth_pass
        self.orig_auth_password_hash = config.settings.auth_password_hash
        self.orig_db_pool = database._db_pool

        config.settings.media_root = str(self.media_root)
        config.settings.data_dir = str(self.data_dir)
        config.settings.auth_user = "admin"
        config.settings.auth_pass = "secret"
        config.settings.auth_password_hash = ""
        database._db_pool = None
        refresh_scraper_plugins()

    def tearDown(self):
        refresh_scraper_plugins()
        if database._db_pool is not None:
            asyncio.run(database.close_db_pool())
        database._db_pool = self.orig_db_pool
        config.settings.media_root = self.orig_media_root
        config.settings.data_dir = self.orig_data_dir
        config.settings.auth_user = self.orig_auth_user
        config.settings.auth_pass = self.orig_auth_pass
        config.settings.auth_password_hash = self.orig_auth_password_hash
        self.tmpdir.cleanup()

    def auth_headers(self):
        token = base64.b64encode(b"admin:secret").decode()
        return {"Authorization": f"Basic {token}"}

    def test_registry_loads_builtin_scrapers_from_builtin_plugin_manifests(self):
        import app.scrapers.registry as registry

        expected = {
            "auto",
            "none",
            "tmdb_movie",
            "tmdb_tv",
            "tmdb_collection",
            "bangumi",
            "javdatabase",
        }
        builtin_names = {manifest.name for manifest in registry.list_builtin_scraper_manifests()}

        self.assertEqual(expected, builtin_names)
        self.assertEqual(set(registry._registry.keys()), expected)
        self.assertEqual(get_scraper("tmdb").name, "tmdb_movie")
        self.assertEqual(get_scraper("tmdb_movie").info().label, "TMDB Movie")
        self.assertEqual(get_scraper("auto").name, "auto")
        self.assertFalse(get_scraper("none").enabled)
        self.assertTrue(all(manifest.builtin for manifest in registry.list_builtin_scraper_manifests()))

        listed = {info.name for info in list_scrapers()}
        self.assertEqual(expected, listed)

    def test_builtin_scrapers_are_not_runtime_installed_plugins(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            scrapers = client.get("/api/scrapers", headers=self.auth_headers())
            plugins = client.get("/api/scraper-plugins", headers=self.auth_headers())

        self.assertEqual(scrapers.status_code, 200)
        self.assertEqual(plugins.status_code, 200)
        self.assertIn("tmdb_movie", {item["name"] for item in scrapers.json()["items"]})
        self.assertTrue(all(item["builtin"] for item in scrapers.json()["items"]))
        self.assertEqual([], plugins.json()["items"])


if __name__ == "__main__":
    unittest.main()
