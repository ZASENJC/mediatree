import unittest

from app import scanner
from app.scrapers.base import ScrapeCandidate


class ManualAutoScrapeSearchTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_search_candidates = scanner._search_scraper_candidates

    async def asyncTearDown(self):
        scanner._search_scraper_candidates = self.orig_search_candidates

    async def test_auto_search_returns_candidates_from_full_manual_chain(self):
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

        results = await scanner.search_for_scrape("Alien", "auto")

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
