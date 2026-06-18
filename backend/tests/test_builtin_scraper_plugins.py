import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.orig_enable_builtin_scraper_plugins = config.settings.enable_builtin_scraper_plugins
        self.orig_db_pool = database._db_pool

        config.settings.media_root = str(self.media_root)
        config.settings.data_dir = str(self.data_dir)
        config.settings.auth_user = "admin"
        config.settings.auth_pass = "secret"
        config.settings.auth_password_hash = ""
        config.settings.enable_builtin_scraper_plugins = True
        database._db_pool = None
        refresh_scraper_plugins()

    def tearDown(self):
        if database._db_pool is not None:
            asyncio.run(database.close_db_pool())
        database._db_pool = self.orig_db_pool
        config.settings.media_root = self.orig_media_root
        config.settings.data_dir = self.orig_data_dir
        config.settings.auth_user = self.orig_auth_user
        config.settings.auth_pass = self.orig_auth_pass
        config.settings.auth_password_hash = self.orig_auth_password_hash
        config.settings.enable_builtin_scraper_plugins = self.orig_enable_builtin_scraper_plugins
        refresh_scraper_plugins()
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

    def test_builtin_scrapers_are_listed_in_plugin_management(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            scrapers = client.get("/api/scrapers", headers=self.auth_headers())
            plugins = client.get("/api/scraper-plugins", headers=self.auth_headers())

        self.assertEqual(scrapers.status_code, 200)
        self.assertEqual(plugins.status_code, 200)
        self.assertIn("tmdb_movie", {item["name"] for item in scrapers.json()["items"]})
        self.assertTrue(all(item["builtin"] for item in scrapers.json()["items"]))
        plugin_items = plugins.json()["items"]
        self.assertEqual(
            {"auto", "none", "tmdb_movie", "tmdb_tv", "tmdb_collection", "bangumi", "javdatabase"},
            {item["name"] for item in plugin_items},
        )
        tmdb_movie = next(item for item in plugin_items if item["name"] == "tmdb_movie")
        self.assertTrue(tmdb_movie["builtin"])
        self.assertTrue(tmdb_movie["enabled"])

    def test_builtin_plugin_sync_does_not_touch_unchanged_rows(self):
        from app.scraper_plugins import list_plugins

        async def prepare():
            await database.init_db()
            await list_plugins()
            db = await database.get_db()
            await db.execute("UPDATE scraper_plugins SET updated_at='2000-01-01 00:00:00' WHERE builtin=1")
            await db.commit()
            await list_plugins()
            cur = await db.execute("SELECT updated_at FROM scraper_plugins WHERE builtin=1")
            return [row["updated_at"] for row in await cur.fetchall()]

        updated_at_values = asyncio.run(prepare())

        self.assertTrue(updated_at_values)
        self.assertTrue(all(value == "2000-01-01 00:00:00" for value in updated_at_values))

    def test_builtin_scraper_can_be_disabled_and_hidden(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            disabled = client.post("/api/scraper-plugins/tmdb_movie/disable", headers=self.auth_headers())
            scrapers_after_disable = client.get("/api/scrapers", headers=self.auth_headers())
            plugins_after_disable = client.get("/api/scraper-plugins", headers=self.auth_headers())
            deleted = client.delete("/api/scraper-plugins/tmdb_movie", headers=self.auth_headers())
            scrapers_after_delete = client.get("/api/scrapers", headers=self.auth_headers())
            plugins_after_delete = client.get("/api/scraper-plugins", headers=self.auth_headers())

        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["plugin"]["enabled"])
        self.assertNotIn("tmdb_movie", {item["name"] for item in scrapers_after_disable.json()["items"]})
        disabled_item = next(item for item in plugins_after_disable.json()["items"] if item["name"] == "tmdb_movie")
        self.assertTrue(disabled_item["builtin"])
        self.assertFalse(disabled_item["enabled"])
        with self.assertRaises(KeyError):
            get_scraper("tmdb_movie")

        self.assertEqual(deleted.status_code, 200)
        self.assertNotIn("tmdb_movie", {item["name"] for item in scrapers_after_delete.json()["items"]})
        self.assertNotIn("tmdb_movie", {item["name"] for item in plugins_after_delete.json()["items"]})

    def test_default_scraper_falls_back_to_available_scraper_when_auto_is_disabled(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            disabled = client.post("/api/scraper-plugins/auto/disable", headers=self.auth_headers())

        self.assertEqual(disabled.status_code, 200)
        self.assertNotEqual(database._valid_scraper("missing_plugin"), "auto")

    def test_disabled_builtin_name_is_not_treated_as_enabled_uploaded_plugin(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            disabled = client.post("/api/scraper-plugins/tmdb_movie/disable", headers=self.auth_headers())

        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(database._enabled_scraper_plugin_exists_sync("tmdb_movie"))
        self.assertNotEqual(database._valid_scraper("tmdb_movie"), "tmdb_movie")

    def test_auto_scraper_skips_disabled_bangumi_fallback(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            disabled = client.post("/api/scraper-plugins/bangumi/disable", headers=self.auth_headers())

        self.assertEqual(disabled.status_code, 200)
        auto = get_scraper("auto")
        with patch("app.scrapers.registry.tmdb_title_search", new_callable=unittest.mock.AsyncMock) as tmdb_search:
            tmdb_search.return_value = None
            result = asyncio.run(auto.full_scrape("Missing Title", code=""))

        self.assertIsNone(result)

    def test_auto_scraper_skips_tmdb_title_search_when_tmdb_scrapers_are_disabled(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            movie_disabled = client.post("/api/scraper-plugins/tmdb_movie/disable", headers=self.auth_headers())
            tv_disabled = client.post("/api/scraper-plugins/tmdb_tv/disable", headers=self.auth_headers())
            bangumi_disabled = client.post("/api/scraper-plugins/bangumi/disable", headers=self.auth_headers())

        self.assertEqual(movie_disabled.status_code, 200)
        self.assertEqual(tv_disabled.status_code, 200)
        self.assertEqual(bangumi_disabled.status_code, 200)
        auto = get_scraper("auto")
        with patch("app.scrapers.registry.tmdb_title_search", new_callable=unittest.mock.AsyncMock) as tmdb_search:
            result = asyncio.run(auto.full_scrape("Missing Title", code=""))

        self.assertIsNone(result)
        tmdb_search.assert_not_called()

    def test_bangumi_fallback_chain_skips_disabled_tmdb_search_steps(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            movie_disabled = client.post("/api/scraper-plugins/tmdb_movie/disable", headers=self.auth_headers())
            tv_disabled = client.post("/api/scraper-plugins/tmdb_tv/disable", headers=self.auth_headers())

        self.assertEqual(movie_disabled.status_code, 200)
        self.assertEqual(tv_disabled.status_code, 200)
        from app import scanner
        self.assertEqual(scanner.build_fallback_chain("bangumi"), ["bangumi"])

    def test_tmdb_scraper_skips_disabled_bangumi_fallback(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            disabled = client.post("/api/scraper-plugins/bangumi/disable", headers=self.auth_headers())

        self.assertEqual(disabled.status_code, 200)
        scraper = get_scraper("tmdb_movie")
        with (
            patch("app.scrapers.tmdb_scraper.tmdb_title_search", new_callable=unittest.mock.AsyncMock) as tmdb_search,
            patch("app.scrapers.registry.get_scraper") as registry_get_scraper,
        ):
            tmdb_search.return_value = None
            result = asyncio.run(scraper.full_scrape("Missing Title", code=""))

        self.assertIsNone(result)
        registry_get_scraper.assert_not_called()

    def test_builtin_scraper_can_be_deleted_while_used_by_library(self):
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            saved = client.post(
                "/api/library-settings",
                headers=self.auth_headers(),
                json={"media_root": str(self.media_root), "scraper": "tmdb_movie"},
            )
            deleted = client.delete("/api/scraper-plugins/tmdb_movie", headers=self.auth_headers())
            plugins_after_delete = client.get("/api/scraper-plugins", headers=self.auth_headers())

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(deleted.status_code, 200)
        self.assertNotIn("tmdb_movie", {item["name"] for item in plugins_after_delete.json()["items"]})
        setting = asyncio.run(database.get_library_settings(config.settings.canonical_media_root(str(self.media_root))))
        self.assertNotEqual(setting["scraper"], "tmdb_movie")
        self.assertEqual(setting["scraper"], "auto")

    def test_builtin_scrapers_can_be_disabled_for_empty_test_containers(self):
        config.settings.enable_builtin_scraper_plugins = False
        refresh_scraper_plugins()
        asyncio.run(database.init_db())

        with TestClient(main.app) as client:
            scrapers = client.get("/api/scrapers", headers=self.auth_headers())
            plugins = client.get("/api/scraper-plugins", headers=self.auth_headers())

        self.assertEqual(scrapers.status_code, 200)
        self.assertEqual(plugins.status_code, 200)
        self.assertEqual([], scrapers.json()["items"])
        self.assertEqual([], plugins.json()["items"])
        with self.assertRaises(KeyError):
            get_scraper("tmdb_movie")


if __name__ == "__main__":
    unittest.main()
