import unittest
from unittest.mock import AsyncMock

from app import scanner
from app.scrapers.base import ScrapeCandidate


class ManualAutoScrapeSearchTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_search_candidates = scanner._search_scraper_candidates
        self.orig_ensure_javdatabase_allowed = scanner.ensure_javdatabase_allowed

    async def asyncTearDown(self):
        scanner._search_scraper_candidates = self.orig_search_candidates
        scanner.ensure_javdatabase_allowed = self.orig_ensure_javdatabase_allowed

    async def test_auto_search_returns_candidates_from_full_manual_chain_for_javdatabase_library(self):
        calls = []

        async def search_candidates(scraper_name, query, media_type=None, limit=10):
            calls.append((scraper_name, query, media_type, limit))
            return [
                ScrapeCandidate(
                    source="tmdb" if scraper_name in {"tmdb_movie", "tmdb_tv"} else scraper_name,
                    source_id=f"{scraper_name}-1",
                    title=f"{scraper_name} result",
                    media_type=media_type or "tv",
                )
            ]

        scanner._search_scraper_candidates = search_candidates
        scanner.ensure_javdatabase_allowed = AsyncMock(return_value=True)

        results = await scanner.search_for_scrape("Alien", "auto", "/media/jav")

        self.assertEqual(
            calls,
            [
                ("tmdb_movie", "Alien", "movie", 10),
                ("tmdb_tv", "Alien", "tv", 10),
                ("tmdb_collection", "Alien", "collection", 10),
                ("bangumi", "Alien", None, 10),
                ("javdatabase", "Alien", "movie", 10),
            ],
        )
        self.assertEqual(
            [item["scraper"] for item in results],
            ["tmdb_movie", "tmdb_tv", "tmdb_collection", "bangumi", "javdatabase"],
        )
        self.assertEqual([item["title"] for item in results], [
            "tmdb_movie result",
            "tmdb_tv result",
            "tmdb_collection result",
            "bangumi result",
            "javdatabase result",
        ])

    async def test_auto_search_skips_javdatabase_for_non_javdatabase_library(self):
        calls = []

        async def search_candidates(scraper_name, query, media_type=None, limit=10):
            calls.append((scraper_name, media_type))
            return [
                ScrapeCandidate(
                    source="tmdb" if scraper_name in {"tmdb_movie", "tmdb_tv"} else scraper_name,
                    source_id=f"{scraper_name}-1",
                    title=f"{scraper_name} result",
                    media_type=media_type or "tv",
                )
            ]

        scanner._search_scraper_candidates = search_candidates
        scanner.ensure_javdatabase_allowed = AsyncMock(return_value=False)

        results = await scanner.search_for_scrape("Alien", "auto", "/media/movies")

        self.assertEqual(
            calls,
            [
                ("tmdb_movie", "movie"),
                ("tmdb_tv", "tv"),
                ("tmdb_collection", "collection"),
                ("bangumi", None),
            ],
        )
        self.assertEqual(
            [item["scraper"] for item in results],
            ["tmdb_movie", "tmdb_tv", "tmdb_collection", "bangumi"],
        )

    async def test_explicit_scraper_search_marks_result_with_selected_scraper(self):
        async def search_candidates(scraper_name, query, media_type=None, limit=10):
            return [
                ScrapeCandidate(
                    source="tmdb_collection",
                    source_id="42",
                    title="Alien Collection",
                    media_type=media_type,
                )
            ]

        scanner._search_scraper_candidates = search_candidates

        results = await scanner.search_for_scrape("Alien", "tmdb_collection")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["scraper"], "tmdb_collection")
        self.assertEqual(results[0]["media_type"], "collection")


if __name__ == "__main__":
    unittest.main()
