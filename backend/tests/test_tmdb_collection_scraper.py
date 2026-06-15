import unittest

from app import scanner, tmdb
from app.database import _valid_scraper
from app.scrapers.registry import get_scraper, list_scrapers


class TMDBCollectionScraperTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_search = getattr(tmdb, "search_tmdb_collections", None)
        self.orig_detail = getattr(tmdb, "fetch_tmdb_collection_detail", None)
        self.orig_fetch_detail_legacy = scanner._fetch_detail_legacy
        self.orig_apply_scraped_data = scanner._apply_scraped_data

    async def asyncTearDown(self):
        if self.orig_search is not None:
            tmdb.search_tmdb_collections = self.orig_search
        if self.orig_detail is not None:
            tmdb.fetch_tmdb_collection_detail = self.orig_detail
        scanner._fetch_detail_legacy = self.orig_fetch_detail_legacy
        scanner._apply_scraped_data = self.orig_apply_scraped_data

    async def test_registry_exposes_collection_without_auto_chain(self):
        scraper = get_scraper("tmdb_collection")
        self.assertEqual(scraper.name, "tmdb_collection")
        self.assertEqual(scraper.supported_media_types, {"collection"})

        names = {info.name for info in list_scrapers()}
        self.assertIn("tmdb_collection", names)

        self.assertEqual(scanner.normalize_scraper_name("tmdb_collection"), "tmdb_collection")
        self.assertEqual(scanner.build_fallback_chain("tmdb_collection"), [])
        self.assertNotIn("tmdb_collection", scanner.build_fallback_chain("auto"))
        self.assertEqual(_valid_scraper("tmdb_collection"), "tmdb_collection")

    async def test_search_for_scrape_returns_collection_candidates(self):
        async def search(query, lang="zh-CN"):
            self.assertEqual(query, "Alien")
            return [{
                "source": "tmdb_collection",
                "source_id": "8091",
                "media_type": "collection",
                "title": "Alien Collection",
                "original_title": "Alien Saga",
                "overview": "The Alien films.",
                "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
                "backdrop_url": "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
                "release_date": "1979-05-25",
                "score": None,
            }]

        tmdb.search_tmdb_collections = search

        results = await scanner.search_for_scrape("Alien", "tmdb_collection", "/media/movies")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "tmdb_collection")
        self.assertEqual(results[0]["media_type"], "collection")
        self.assertEqual(results[0]["source_id"], "8091")
        self.assertEqual(results[0]["original_title"], "Alien Saga")

    async def test_collection_detail_maps_to_manual_legacy_data(self):
        async def detail(source_id, lang="zh-CN"):
            self.assertEqual(source_id, "8091")
            return {
                "source": "tmdb_collection",
                "source_id": "8091",
                "media_type": "collection",
                "title": "Alien Collection",
                "original_title": "Alien Saga",
                "overview": "The Alien films.",
                "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
                "backdrop_url": "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
                "release_date": "1979-05-25",
                "parts": [
                    {"id": 348, "title": "Alien", "release_date": "1979-05-25"},
                    {"id": 679, "title": "Aliens", "release_date": "1986-07-18"},
                ],
            }

        tmdb.fetch_tmdb_collection_detail = detail

        data = await scanner._fetch_detail_legacy(
            "tmdb_collection",
            "8091",
            "collection",
        )

        self.assertIsNotNone(data)
        self.assertEqual(data["source"], "tmdb_collection")
        self.assertEqual(data["source_id"], "8091")
        self.assertEqual(data["title"], "Alien Collection")
        self.assertEqual(data["original_title"], "Alien Saga")
        self.assertEqual(data["cover_remote"], "https://image.tmdb.org/t/p/w500/poster.jpg")
        self.assertEqual(data["backdrop_url"], "https://image.tmdb.org/t/p/w1280/backdrop.jpg")
        self.assertEqual(data["tmdb_type"], "")
        self.assertIsNone(data["tmdb_id"])
        self.assertIn("Alien", data["scraper_raw"])

    async def test_apply_folder_scrape_result_accepts_collection_source(self):
        calls = []

        async def fetch_detail(source, source_id, media_type=None, *, exact=True):
            calls.append(("fetch", source, source_id, media_type, exact))
            return {
                "source": "tmdb_collection",
                "source_id": source_id,
                "title": "Alien Collection",
                "cover_remote": "https://image.tmdb.org/t/p/w500/poster.jpg",
                "backdrop_url": "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
                "tmdb_id": None,
                "tmdb_type": "",
            }

        async def apply_data(folder_levels, data, media_root="", replace=False):
            calls.append((
                "apply",
                folder_levels,
                data.get("source"),
                data.get("source_id"),
                data.get("tmdb_id"),
                data.get("tmdb_type"),
                media_root,
                replace,
            ))
            return 2

        scanner._fetch_detail_legacy = fetch_detail
        scanner._apply_scraped_data = apply_data

        result = await scanner.apply_folder_scrape_result(
            "Alien",
            "/media/movies",
            "8091",
            "tmdb_collection",
            "collection",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "tmdb_collection")
        self.assertEqual(result["affected"], 2)
        self.assertEqual(calls[0], ("fetch", "tmdb_collection", "8091", "collection", True))
        self.assertEqual(calls[1], (
            "apply",
            "Alien",
            "tmdb_collection",
            "8091",
            None,
            "",
            "/media/movies",
            True,
        ))


if __name__ == "__main__":
    unittest.main()
