import asyncio
import base64
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app import config, database, main
from app.scrapers.registry import get_scraper, list_scrapers, refresh_scraper_plugins


PLUGIN_SOURCE = """
from app.scrapers.base import BaseScraper, ScrapeCandidate, ScrapeResult


class DemoPluginScraper(BaseScraper):
    async def search(self, query, *, media_type=None, limit=10):
        return [ScrapeCandidate(
            source=self.name,
            source_id="demo-1",
            title=f"Demo {query}",
            media_type=media_type or "movie",
        )][:limit]

    async def get_detail(self, source_id, *, media_type=None):
        return ScrapeResult(
            source=self.name,
            source_id=str(source_id),
            title="Demo Detail",
            media_type=media_type or "movie",
        )

    def normalize_result(self, raw):
        return ScrapeResult(
            source=self.name,
            source_id=str(raw["id"]),
            title=raw["title"],
        )
"""

BROKEN_PLUGIN_SOURCE = """
class DemoPluginScraper:
    pass
"""


class ScraperPluginTest(unittest.TestCase):
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

    def plugin_zip(
        self,
        manifest: dict | None = None,
        extra_files: dict[str, bytes | str] | None = None,
        source: str = PLUGIN_SOURCE,
    ) -> bytes:
        manifest = manifest or {
            "name": "demo_plugin",
            "version": "1.0.0",
            "label": "Demo Plugin",
            "description": "Test plugin",
            "entrypoint": "scraper.py",
            "class_name": "DemoPluginScraper",
            "supported_media_types": ["movie"],
        }
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as zf:
            zf.writestr("plugin.json", json.dumps(manifest))
            zf.writestr("scraper.py", source)
            for name, content in (extra_files or {}).items():
                zf.writestr(name, content)
        return payload.getvalue()

    def test_install_requires_auth(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("demo.zip", self.plugin_zip(), "application/zip")},
            )

        self.assertEqual(response.status_code, 401)

    def test_install_rejects_zip_path_traversal(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("demo.zip", self.plugin_zip(extra_files={"../escape.py": "bad"}), "application/zip")},
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / "escape.py").exists())

    def test_install_rejects_duplicate_archive_paths(self):
        payload = io.BytesIO()
        manifest = {
            "name": "demo_plugin",
            "version": "1.0.0",
            "label": "Demo Plugin",
            "description": "Test plugin",
            "entrypoint": "scraper.py",
            "class_name": "DemoPluginScraper",
            "supported_media_types": ["movie"],
        }
        with zipfile.ZipFile(payload, "w") as zf:
            zf.writestr("plugin.json", json.dumps(manifest))
            zf.writestr("scraper.py", PLUGIN_SOURCE)
            zf.writestr("scraper.py", BROKEN_PLUGIN_SOURCE)

        with TestClient(main.app) as client:
            response = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("demo.zip", payload.getvalue(), "application/zip")},
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicate", response.json()["detail"].lower())

    def test_install_rejects_builtin_scraper_name(self):
        payload = self.plugin_zip(manifest={
            "name": "auto",
            "version": "1.0.0",
            "label": "Bad",
            "description": "Bad",
            "entrypoint": "scraper.py",
            "class_name": "DemoPluginScraper",
            "supported_media_types": ["movie"],
        })
        with TestClient(main.app) as client:
            response = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("bad.zip", payload, "application/zip")},
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reserved", response.json()["detail"].lower())

    def test_install_allows_builtin_named_plugin_when_builtin_scrapers_disabled(self):
        config.settings.enable_builtin_scraper_plugins = False
        refresh_scraper_plugins()

        with TestClient(main.app) as client:
            response = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("tmdb.zip", self.plugin_zip(manifest={
                    "name": "tmdb_movie",
                    "version": "1.0.0",
                    "label": "TMDB Movie Override",
                    "description": "Test plugin",
                    "entrypoint": "scraper.py",
                    "class_name": "DemoPluginScraper",
                    "supported_media_types": ["movie"],
                }), "application/zip")},
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plugin"]["name"], "tmdb_movie")
        self.assertFalse(response.json()["plugin"]["builtin"])

    def test_install_is_disabled_until_enabled_then_registry_loads_plugin(self):
        with TestClient(main.app) as client:
            installed = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("demo.zip", self.plugin_zip(), "application/zip")},
                headers=self.auth_headers(),
            )
            self.assertEqual(installed.status_code, 200)
            self.assertFalse(installed.json()["plugin"]["enabled"])
            self.assertNotIn("installed_path", installed.json()["plugin"])

            scrapers_before = client.get("/api/scrapers", headers=self.auth_headers())
            self.assertEqual(scrapers_before.status_code, 200)
            self.assertTrue(all("installed_path" not in item for item in scrapers_before.json()["items"]))
            self.assertNotIn("demo_plugin", {item["name"] for item in scrapers_before.json()["items"]})

            enabled = client.post("/api/scraper-plugins/demo_plugin/enable", headers=self.auth_headers())
            self.assertEqual(enabled.status_code, 200)
            self.assertTrue(enabled.json()["plugin"]["enabled"])

            scrapers_after = client.get("/api/scrapers", headers=self.auth_headers())
            self.assertIn("demo_plugin", {item["name"] for item in scrapers_after.json()["items"]})

        names = {info.name for info in list_scrapers()}
        self.assertIn("demo_plugin", names)
        scraper = get_scraper("demo_plugin")
        candidates = asyncio.run(scraper.search("Movie"))
        self.assertEqual(candidates[0].title, "Demo Movie")

    def test_enable_failure_keeps_plugin_disabled_and_records_error(self):
        with TestClient(main.app) as client:
            installed = client.post(
                "/api/scraper-plugins/install",
                files={"file": ("demo.zip", self.plugin_zip(source=BROKEN_PLUGIN_SOURCE), "application/zip")},
                headers=self.auth_headers(),
            )
            self.assertEqual(installed.status_code, 200)

            enabled = client.post("/api/scraper-plugins/demo_plugin/enable", headers=self.auth_headers())
            self.assertEqual(enabled.status_code, 400)
            self.assertEqual(enabled.json()["detail"], "Plugin load failed")

            plugins = client.get("/api/scraper-plugins", headers=self.auth_headers())
            self.assertEqual(plugins.status_code, 200)

        plugin = next(item for item in plugins.json()["items"] if item["name"] == "demo_plugin")
        self.assertFalse(plugin["enabled"])
        self.assertIn("subclass BaseScraper", plugin["error"])
        self.assertNotIn("installed_path", plugin)

    def test_enabled_plugin_can_be_saved_as_library_scraper(self):
        async def seed_schema():
            await database.init_db()

        asyncio.run(seed_schema())

        with TestClient(main.app) as client:
            self.assertEqual(
                client.post(
                    "/api/scraper-plugins/install",
                    files={"file": ("demo.zip", self.plugin_zip(), "application/zip")},
                    headers=self.auth_headers(),
                ).status_code,
                200,
            )
            self.assertEqual(
                client.post("/api/scraper-plugins/demo_plugin/enable", headers=self.auth_headers()).status_code,
                200,
            )
            saved = client.post(
                "/api/library-settings",
                json={"media_root": str(self.media_root), "scraper": "demo_plugin"},
                headers=self.auth_headers(),
            )

        self.assertEqual(saved.status_code, 200)
        canonical = config.settings.canonical_media_root(str(self.media_root)) or str(self.media_root)
        setting = asyncio.run(database.get_library_settings(canonical))
        self.assertEqual(setting["scraper"], "demo_plugin")

    def test_delete_rejects_plugin_in_use(self):
        with TestClient(main.app) as client:
            client.post(
                "/api/scraper-plugins/install",
                files={"file": ("demo.zip", self.plugin_zip(), "application/zip")},
                headers=self.auth_headers(),
            )
            client.post("/api/scraper-plugins/demo_plugin/enable", headers=self.auth_headers())
            client.post(
                "/api/library-settings",
                json={"media_root": str(self.media_root), "scraper": "demo_plugin"},
                headers=self.auth_headers(),
            )
            deleted = client.delete("/api/scraper-plugins/demo_plugin", headers=self.auth_headers())

        self.assertEqual(deleted.status_code, 409)


if __name__ == "__main__":
    unittest.main()
