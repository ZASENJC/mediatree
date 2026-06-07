"""Tests for P1 features: IMDB ID fetch validation, pending_review DB ops,
media type inference edge cases, and complete scraped data checks."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite

from app.title_match import (
    extract_code,
    extract_imdb_id_from_name,
    has_complete_scraped_data,
    has_local_data,
    infer_tmdb_media_type,
    _local_metadata,
    _meaningful_local_metadata,
)
from app.database import (
    get_db,
    get_review_queue,
    approve_review_item,
    clear_review_queue,
    get_db_pool,
)


# ── IMDB ID Fetch Validation ──────────────────────────────────────────────


class ImdbIdFetchValidationTest(unittest.TestCase):
    """Test IMDB ID format validation (early return before network in fetch_tmdb_by_imdb_id)."""

    def test_valid_imdb_id_format(self):
        """IDs must start with 'tt' and have 7+ digits."""
        from app.tmdb import _has_tmdb_auth
        # Without auth, fetch_tmdb_by_imdb_id returns None immediately
        # But we can test the IMDB_ID_PATTERN extraction logic directly
        self.assertEqual(extract_imdb_id_from_name("tt1234567"), "tt1234567")
        self.assertEqual(extract_imdb_id_from_name("tt12345678"), "tt12345678")

    def test_invalid_imdb_id_too_short(self):
        self.assertIsNone(extract_imdb_id_from_name("tt123456"))
        self.assertIsNone(extract_imdb_id_from_name("tt123"))

    def test_invalid_imdb_id_wrong_prefix(self):
        self.assertIsNone(extract_imdb_id_from_name("mm1234567"))
        self.assertIsNone(extract_imdb_id_from_name("1234567"))

    def test_imdb_id_in_brackets(self):
        self.assertEqual(extract_imdb_id_from_name("[imdbid-tt1234567]"), "tt1234567")

    def test_no_false_positive_on_tmdb_token(self):
        self.assertIsNone(extract_imdb_id_from_name("[tmdbid=123456]"))


# ── Complete Scraped Data ──────────────────────────────────────────────────


class CompleteScrapedDataTest(unittest.TestCase):
    """Test has_complete_scraped_data() thoroughly."""

    def test_full_data(self):
        self.assertTrue(has_complete_scraped_data({
            "title": "Movie",
            "cover_remote": "https://img/c.jpg",
            "tmdb_id": 1,
        }))

    def test_full_data_javdb(self):
        self.assertTrue(has_complete_scraped_data({
            "title": "JAV-001",
            "cover_local": "/covers/abc.jpg",
            "javdb_id": "ABC123",
        }))

    def test_full_data_bangumi(self):
        self.assertTrue(has_complete_scraped_data({
            "title": "Anime",
            "cover_remote": "https://img/c.jpg",
            "bangumi_id": "12345",
        }))

    def test_full_data_source_id(self):
        self.assertTrue(has_complete_scraped_data({
            "title": "Show",
            "cover_local": "local.jpg",
            "source_id": "tmdb_1",
        }))

    def test_missing_title(self):
        self.assertFalse(has_complete_scraped_data({"title": "", "tmdb_id": 1}))

    def test_title_whitespace_only(self):
        self.assertFalse(has_complete_scraped_data({"title": "   ", "cover_remote": "x"}))

    def test_missing_cover(self):
        self.assertFalse(has_complete_scraped_data({
            "title": "Movie",
            "cover_local": None,
            "cover_remote": None,
            "tmdb_id": 1,
        }))
        self.assertFalse(has_complete_scraped_data({
            "title": "Movie",
            "cover_local": "",
            "cover_remote": "",
            "tmdb_id": 1,
        }))

    def test_missing_source_id(self):
        self.assertFalse(has_complete_scraped_data({
            "title": "Movie",
            "cover_remote": "https://img/c.jpg",
        }))

    def test_empty_row(self):
        self.assertFalse(has_complete_scraped_data({}))
        self.assertFalse(has_complete_scraped_data({"title": "", "cover_local": "", "cover_remote": ""}))


class JavdatabaseScraperCodePolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_scrape_skips_rows_without_explicit_jav_code(self):
        from app.scrapers.javdatabase_scraper import JavdatabaseScraper

        scraper = JavdatabaseScraper()
        scraper.get_detail = AsyncMock(return_value=None)

        result = await scraper.full_scrape(
            "Sperm Mania-298 Ria Kurumi",
            code="Sperm Mania 298 Ria Kurumi",
            movie={"local_metadata": json.dumps({"jav_code_explicit": False})},
        )

        self.assertIsNone(result)
        scraper.get_detail.assert_not_called()


# ── Media Type Inference Edge Cases ───────────────────────────────────────


class MediaTypeInferenceEdgeTest(unittest.TestCase):
    """Additional infer_tmdb_media_type() edge cases beyond test_title_match."""

    def test_disc_pattern_in_folder(self):
        _, scores = infer_tmdb_media_type({}, ["CD1 Movie 2024"])
        self.assertGreaterEqual(scores["movie_score"], 0)

    def test_year_without_episode_boosts_movie(self):
        _, scores = infer_tmdb_media_type({}, ["Inception (2010) 1080p"])
        self.assertGreater(scores["movie_score"], scores["tv_score"])

    def test_season_hint_in_path_boosts_tv(self):
        _, scores = infer_tmdb_media_type({}, ["Show Season 01"])
        self.assertGreater(scores["tv_score"], scores["movie_score"])

    def test_multiple_names_checked(self):
        _, scores = infer_tmdb_media_type({}, ["Show", "S01E01 - Episode Title"])
        self.assertGreater(scores["tv_score"], scores["movie_score"])

    def test_no_episode_or_season_defaults_movie(self):
        _, scores = infer_tmdb_media_type({}, ["The Matrix"])
        self.assertGreater(scores["movie_score"], scores["tv_score"])


# ── Pending Review Database Operations ─────────────────────────────────────


class PendingReviewDBTest(unittest.TestCase):
    """Test pending_review database CRUD operations with a temp DB."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        cls.db_path = tmp.name
        cls._original_pool = None
        # Capture original pool state
        import app.database as db_module
        cls._db_module = db_module

    async def _setup_db(self, db):
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                code TEXT NOT NULL,
                title TEXT,
                actress TEXT,
                release_date TEXT,
                duration INTEGER,
                cover_local TEXT,
                cover_remote TEXT,
                javdb_url TEXT,
                javdb_score REAL,
                javdb_likes INTEGER,
                javdb_thumbnails TEXT,
                folder_levels TEXT,
                local_metadata TEXT DEFAULT '{}',
                tmdb_id INTEGER,
                tmdb_type TEXT,
                tmdb_season INTEGER,
                tmdb_episode INTEGER,
                episode_title TEXT,
                episode_overview TEXT,
                episode_still TEXT,
                episode_still_local TEXT,
                clean_title TEXT,
                episode_number INTEGER,
                display_title TEXT,
                external_audio_tracks TEXT DEFAULT '[]',
                "cast" TEXT DEFAULT '[]',
                crew TEXT DEFAULT '[]',
                scraper_source TEXT,
                source_id TEXT,
                bangumi_id TEXT,
                javdb_id TEXT,
                original_title TEXT,
                overview TEXT,
                scraper_raw TEXT,
                pending_review INTEGER DEFAULT 0,
                review_candidates TEXT,
                genre TEXT,
                keywords TEXT,
                studios TEXT,
                tagline TEXT,
                status TEXT,
                media_root TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        row_factory = aiosqlite.Row
        await db.commit()

    async def _get_test_db(self):
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await self._setup_db(db)
        return db

    def setUp(self):
        # Reset DB file
        import os
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        async def _init():
            db = await self._get_test_db()
            # Insert test movies
            await db.execute(
                "INSERT INTO movies (path, code, title, pending_review, review_candidates) "
                "VALUES (?, ?, ?, ?, ?)",
                ("/test/pending.mp4", "CODE-001", "Pending Movie", 1,
                 json.dumps(["candidate1", "candidate2"])),
            )
            await db.execute(
                "INSERT INTO movies (path, code, title, pending_review) "
                "VALUES (?, ?, ?, ?)",
                ("/test/approved.mp4", "CODE-002", "Approved Movie", 0),
            )
            await db.execute(
                "INSERT INTO movies (path, code, title, pending_review, review_candidates) "
                "VALUES (?, ?, ?, ?, ?)",
                ("/test/pending2.mp4", "CODE-003", "Pending Movie 2", 1,
                 json.dumps(["candidate3"])),
            )
            await db.commit()
            await db.close()

        asyncio.run(_init())

    def tearDown(self):
        import os
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _run_async(self, coro):
        return asyncio.run(coro)

    def test_get_review_queue_returns_pending_only(self):
        async def _test():
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            # Patch get_db to return our test db
            with patch.object(self._db_module, 'get_db', return_value=db):
                with patch.object(self._db_module, 'get_db_pool', return_value=db):
                    result = await get_review_queue()
            await db.close()
            return result

        result = self._run_async(_test())
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["movies"]), 2)
        titles = {m["title"] for m in result["movies"]}
        self.assertEqual(titles, {"Pending Movie", "Pending Movie 2"})

    def test_review_candidates_decoded(self):
        async def _test():
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            with patch.object(self._db_module, 'get_db', return_value=db):
                with patch.object(self._db_module, 'get_db_pool', return_value=db):
                    result = await get_review_queue()
            await db.close()
            return result

        result = self._run_async(_test())
        movie = result["movies"][0]
        if movie["code"] == "CODE-001":
            self.assertEqual(movie["review_candidates"], ["candidate1", "candidate2"])

    def test_approve_review_item_clears_flag(self):
        async def _test():
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            with patch.object(self._db_module, 'get_db', return_value=db):
                with patch.object(self._db_module, 'get_db_pool', return_value=db):
                    await approve_review_item(1)

                    # Verify
                    with patch.object(self._db_module, 'get_db', return_value=db):
                        with patch.object(self._db_module, 'get_db_pool', return_value=db):
                            result = await get_review_queue()
            await db.close()
            return result

        result = self._run_async(_test())
        self.assertEqual(result["total"], 1)

    def test_clear_review_queue_clears_all(self):
        async def _test():
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            with patch.object(self._db_module, 'get_db', return_value=db):
                with patch.object(self._db_module, 'get_db_pool', return_value=db):
                    await clear_review_queue()

                    with patch.object(self._db_module, 'get_db', return_value=db):
                        with patch.object(self._db_module, 'get_db_pool', return_value=db):
                            result = await get_review_queue()
            await db.close()
            return result

        result = self._run_async(_test())
        self.assertEqual(result["total"], 0)

    def test_approve_nonexistent_id_no_error(self):
        async def _test():
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            with patch.object(self._db_module, 'get_db', return_value=db):
                with patch.object(self._db_module, 'get_db_pool', return_value=db):
                    # Should not raise
                    await approve_review_item(99999)
            await db.close()

        # Should not raise
        self._run_async(_test())

    def test_review_queue_pagination(self):
        async def _test():
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            with patch.object(self._db_module, 'get_db', return_value=db):
                with patch.object(self._db_module, 'get_db_pool', return_value=db):
                    result = await get_review_queue(limit=1, offset=0)
            await db.close()
            return result

        result = self._run_async(_test())
        self.assertEqual(result["total"], 2)  # total ignores pagination
        self.assertEqual(len(result["movies"]), 1)  # limit=1


# ── Code Extraction Extended ───────────────────────────────────────────────


class CodeExtractionExtendedTest(unittest.TestCase):
    """Extended code extraction tests covering P1 edge cases."""

    def test_japanese_folder_with_code(self):
        """Japanese title folder containing a code should extract code."""
        self.assertEqual(extract_code("SORA-500"), "SORA-500")

    def test_code_in_complex_cjk_string(self):
        """Code embedded in CJK title string."""
        self.assertEqual(extract_code("【新作】ABP-999 女優名"), "ABP-999")

    def test_code_with_large_number(self):
        """Code with 4-6 digit number."""
        self.assertEqual(extract_code("STAR-123456"), "STAR-123456")

    def test_code_single_prefix_letter(self):
        """Single letter prefix (unlikely but valid)."""
        self.assertEqual(extract_code("A-12345"), "A-12345")

    def test_code_underscore_to_dash_normalization(self):
        """Underscore-separated code normalized to dash."""
        self.assertEqual(extract_code("SSNI_888"), "SSNI-888")


# ── has_local_data ─────────────────────────────────────────────────────────


class HasLocalDataTest(unittest.TestCase):
    """Test has_local_data() with various metadata/cover combinations."""

    def test_metadata_and_cover_true(self):
        meta = json.dumps({"title": "Movie", "year": "2024"})
        row = {"local_metadata": meta, "cover_local": "cover.jpg"}
        self.assertTrue(has_local_data(row))

    def test_metadata_only_no_cover_false(self):
        meta = json.dumps({"title": "Movie"})
        row = {"local_metadata": meta, "cover_local": None}
        self.assertFalse(has_local_data(row))

    def test_empty_metadata_with_cover_false(self):
        row = {"local_metadata": "{}", "cover_local": "cover.jpg"}
        self.assertFalse(has_local_data(row))

    def test_nfo_metadata_with_short_cover(self):
        meta = json.dumps({"nfo": {"nfo_type": "movie", "title": "Test"}})
        row = {"local_metadata": meta, "cover_local": "cover.jpg"}
        self.assertTrue(has_local_data(row))

    def test_cover_path_too_long(self):
        meta = json.dumps({"title": "Movie"})
        long_cover = "x" * 65
        row = {"local_metadata": meta, "cover_local": long_cover}
        # cover > 64 chars treated as path, checked with Path().exists()
        self.assertFalse(has_local_data(row))
