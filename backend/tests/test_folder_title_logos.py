import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app import main, tmdb


class _Cursor:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _Database:
    async def execute(self, _query, _params):
        return _Cursor({"tmdb_id": 123, "tmdb_type": "tv", "folder_levels": "Show"})


class FolderTitleLogoTest(unittest.IsolatedAsyncioTestCase):
    async def test_tmdb_images_request_includes_chinese_and_english(self):
        response = MagicMock()
        response.json.return_value = {
            "posters": [],
            "backdrops": [],
            "logos": [
                {"file_path": "/zh.svg", "iso_639_1": "zh", "width": 900, "height": 260},
                {"file_path": "/en.svg", "iso_639_1": "en", "width": 800, "height": 240},
            ],
        }

        with (
            patch.object(tmdb, "_has_tmdb_auth", return_value=True),
            patch.object(tmdb, "get_scraper_cache", AsyncMock(return_value=None)) as cache_get,
            patch.object(tmdb, "set_scraper_cache", AsyncMock()),
            patch.object(tmdb, "_tmdb_get", AsyncMock(return_value=response)) as tmdb_get,
        ):
            result = await tmdb.fetch_tmdb_images(123, "tv")

        tmdb_get.assert_awaited_once_with(
            "/tv/123/images",
            {"include_image_language": "zh,en,null"},
        )
        self.assertEqual([logo["language"] for logo in result["logos"]], ["zh", "en"])
        self.assertIn("zh,en,null", cache_get.await_args.args[1])

    async def test_folder_visuals_returns_logos_with_backdrops(self):
        images = {
            "backdrops": [{"url": "https://image/backdrop.jpg", "width": 1280, "height": 720}],
            "logos": [
                {"url": "https://image/zh.svg", "width": 900, "height": 260, "language": "zh"},
                {"url": "https://image/en.svg", "width": 800, "height": 240, "language": "en"},
            ],
        }

        with (
            patch.object(main.settings, "tmdb_access_token", "test-token"),
            patch("app.database.get_db", AsyncMock(return_value=_Database())),
            patch("app.tmdb.fetch_tmdb_images", AsyncMock(return_value=images)),
        ):
            result = await main.api_folder_backdrops(path="Show", media_root="/media")

        self.assertEqual(result, images)


if __name__ == "__main__":
    unittest.main()
