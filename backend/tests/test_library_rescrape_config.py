import unittest
from unittest.mock import patch

from app import scanner
from app.scraper_cache_policy import should_bypass_scraper_cache


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeDb:
    def __init__(self, row):
        self._row = row

    async def execute(self, *_args):
        return _FakeCursor(self._row)


def _movie_row(media_root="/media/movies", folder_levels="Alien"):
    return {
        "id": 7,
        "folder_levels": folder_levels,
        "clean_title": "",
        "code": "Alien",
        "path": f"{media_root}/{folder_levels}/movie.mkv",
        "title": "",
        "display_title": "",
        "media_root": media_root,
        "content_role": "main",
        "tmdb_id": None,
        "tmdb_season": None,
    }


class LibraryRescrapeConfigTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_get_scraper = scanner.get_scraper
        self.orig_apply = scanner._apply_scraped_data
        self.orig_tmdb_title_search = scanner.tmdb_title_search

    async def asyncTearDown(self):
        scanner.get_scraper = self.orig_get_scraper
        scanner._apply_scraped_data = self.orig_apply
        scanner.tmdb_title_search = self.orig_tmdb_title_search

    async def test_rescrape_movie_uses_configured_bangumi_without_tmdb_fallback(self):
        calls = []

        class EmptyBangumiScraper:
            async def full_scrape(self, search_name, *, code="", candidate_names=None, movie=None):
                calls.append(("bangumi", search_name))
                return None

        def get_scraper(name):
            calls.append(("get_scraper", name))
            return EmptyBangumiScraper()

        async def tmdb_title_search(*_args):
            calls.append(("tmdb_title_search",))
            return {
                "source": "tmdb",
                "title": "Alien",
                "_exact_match": True,
            }

        async def apply(*_args, **_kwargs):
            calls.append(("apply",))
            return 1

        scanner.get_scraper = get_scraper
        scanner.tmdb_title_search = tmdb_title_search
        scanner._apply_scraped_data = apply

        with (
            patch("app.database.get_db", return_value=_FakeDb(_movie_row())),
            patch("app.database.get_library_settings", return_value={"scraper": "bangumi"}),
        ):
            result = await scanner.rescrape_movie(7)

        self.assertFalse(result["ok"])
        self.assertNotIn(("tmdb_title_search",), calls)
        self.assertNotIn(("apply",), calls)
        self.assertEqual(calls, [("get_scraper", "bangumi"), ("bangumi", "Alien")])

    async def test_rescrape_movie_applies_configured_collection_scraper(self):
        calls = []

        class CollectionScraper:
            async def full_scrape(self, search_name, *, code="", candidate_names=None, movie=None):
                calls.append(("full_scrape", search_name, code))
                return {
                    "source": "tmdb_collection",
                    "scraper_source": "tmdb_collection",
                    "title": "Alien",
                    "source_id": "8091",
                    "_exact_match": True,
                }

        def get_scraper(name):
            calls.append(("get_scraper", name))
            return CollectionScraper()

        async def apply(folder_levels, data, media_root="", replace=False):
            calls.append(("apply", folder_levels, data["title"], media_root, replace))
            return 2

        scanner.get_scraper = get_scraper
        scanner._apply_scraped_data = apply

        with (
            patch("app.database.get_db", return_value=_FakeDb(_movie_row())),
            patch("app.database.get_library_settings", return_value={"scraper": "tmdb_collection"}),
        ):
            result = await scanner.rescrape_movie(7)

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "tmdb_collection")
        self.assertEqual(calls[0], ("get_scraper", "tmdb_collection"))
        self.assertEqual(calls[1], ("full_scrape", "Alien", "Alien"))
        self.assertEqual(calls[2], ("apply", "Alien", "Alien", "/media/movies", True))

    async def test_rescrape_movie_bypasses_scraper_cache(self):
        bypass_states = []

        class CollectionScraper:
            async def full_scrape(self, search_name, *, code="", candidate_names=None, movie=None):
                bypass_states.append(should_bypass_scraper_cache())
                return {
                    "source": "tmdb_collection",
                    "scraper_source": "tmdb_collection",
                    "title": "Alien",
                    "source_id": "8091",
                    "_exact_match": True,
                }

        def get_scraper(_name):
            return CollectionScraper()

        async def apply(*_args, **_kwargs):
            return 1

        scanner.get_scraper = get_scraper
        scanner._apply_scraped_data = apply

        with (
            patch("app.database.get_db", return_value=_FakeDb(_movie_row())),
            patch("app.database.get_library_settings", return_value={"scraper": "tmdb_collection"}),
        ):
            result = await scanner.rescrape_movie(7)

        self.assertTrue(result["ok"])
        self.assertEqual(bypass_states, [True])


if __name__ == "__main__":
    unittest.main()
