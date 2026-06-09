import tempfile
import unittest
from pathlib import Path

from app import database
from app.config import settings
from app.scraper_cache_policy import bypass_scraper_cache


class ScraperCachePolicyTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data_dir = settings.data_dir
        settings.data_dir = str(Path(self.tmp.name) / "data")
        await database.close_db_pool()
        await database.init_db()

    async def asyncTearDown(self):
        await database.close_db_pool()
        settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    async def test_bypass_context_skips_existing_scraper_cache(self):
        await database.set_scraper_cache("tmdb", "tmdb_search:movie:Alien", {"title": "Cached Alien"})

        cached = await database.get_scraper_cache("tmdb", "tmdb_search:movie:Alien", 168)
        self.assertEqual(cached, {"title": "Cached Alien"})

        with bypass_scraper_cache():
            bypassed = await database.get_scraper_cache("tmdb", "tmdb_search:movie:Alien", 168)

        self.assertIsNone(bypassed)
        cached_after = await database.get_scraper_cache("tmdb", "tmdb_search:movie:Alien", 168)
        self.assertEqual(cached_after, {"title": "Cached Alien"})

    async def test_empty_scraper_cache_payload_is_not_persisted(self):
        await database.set_scraper_cache("bangumi", "bangumi_search:typeall:missing", {"title": "old"})
        await database.set_scraper_cache("bangumi", "bangumi_search:typeall:missing", [])

        cached = await database.get_scraper_cache("bangumi", "bangumi_search:typeall:missing", 168)
        self.assertIsNone(cached)

        db = await database.get_db()
        cur = await db.execute(
            "SELECT COUNT(*) AS cnt FROM scraper_cache WHERE source=? AND query=?",
            ("bangumi", "bangumi_search:typeall:missing"),
        )
        row = await cur.fetchone()
        self.assertEqual(row["cnt"], 0)

    async def test_legacy_empty_scraper_cache_row_is_ignored_and_removed(self):
        db = await database.get_db()
        await db.execute(
            "INSERT OR REPLACE INTO scraper_cache (source, query, data, fetched_at) "
            "VALUES (?,?,?,datetime('now'))",
            ("tmdb", "tmdb_search:movie:missing", "[]"),
        )
        await db.commit()

        cached = await database.get_scraper_cache("tmdb", "tmdb_search:movie:missing", 168)
        self.assertIsNone(cached)

        cur = await db.execute(
            "SELECT COUNT(*) AS cnt FROM scraper_cache WHERE source=? AND query=?",
            ("tmdb", "tmdb_search:movie:missing"),
        )
        row = await cur.fetchone()
        self.assertEqual(row["cnt"], 0)


if __name__ == "__main__":
    unittest.main()
