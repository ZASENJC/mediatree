import tempfile
import unittest
from pathlib import Path

from app import database
from app.config import settings


class ContinueWatchingTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.old_data_dir = settings.data_dir
        settings.data_dir = str(self.tmp_path / "data")
        await database.close_db_pool()
        await database.init_db()
        self.media_root = str(self.tmp_path / "media")
        self.other_root = str(self.tmp_path / "other")

    async def asyncTearDown(self):
        await database.close_db_pool()
        settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    async def _movie(self, code: str, **overrides) -> int:
        root = overrides.pop("media_root", self.media_root)
        data = {
            "path": f"{root}/{code}.mkv",
            "code": code,
            "title": code,
            "duration": 1200,
            "folder_levels": "",
            "media_root": root,
            "created_at": "2026-01-01 00:00:00",
        }
        data.update(overrides)
        return await database.upsert_movie(data)

    async def _episode(self, episode: int, *, season: int = 1, root: str | None = None, **overrides) -> int:
        media_root = root or self.media_root
        data = {
            "path": f"{media_root}/Show/S{season:02d}/E{episode:02d}.mkv",
            "code": f"S{season:02d}E{episode:02d}",
            "title": "Show",
            "duration": 1200,
            "folder_levels": f"Show/S{season:02d}",
            "media_root": media_root,
            "tmdb_id": 1000,
            "tmdb_type": "tv",
            "tmdb_season": season,
            "tmdb_episode": episode,
            "episode_title": f"Episode {episode}",
            "clean_title": "Show",
            "display_title": f"Show - EP{episode:02d}",
            "created_at": "2026-01-01 00:00:00",
        }
        data.update(overrides)
        return await database.upsert_movie(data)

    async def test_partial_movie_after_one_minute_is_included_with_progress(self):
        movie_id = await self._movie("partial-movie")
        await database.save_progress(movie_id, position=61, duration=1200)

        result = await database.get_recent_watched()

        self.assertEqual([movie["id"] for movie in result["movies"]], [movie_id])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["movies"][0]["playback_position"], 61)
        self.assertEqual(result["movies"][0]["progress_percent"], 5)

    async def test_completed_movies_and_episodes_are_not_included(self):
        movie_id = await self._movie("completed-movie")
        episode_id = await self._episode(1)
        await database.save_progress(movie_id, position=1100, duration=1200)
        await database.save_progress(episode_id, position=1100, duration=1200)

        result = await database.get_recent_watched()

        self.assertEqual(result["movies"], [])
        self.assertEqual(result["total"], 0)

    async def test_manually_watched_partial_movie_is_not_included(self):
        movie_id = await self._movie("manually-watched")
        await database.save_progress(movie_id, position=61, duration=1200)
        await database.add_tag(movie_id, "watched")

        result = await database.get_recent_watched()

        self.assertEqual(result["movies"], [])
        self.assertEqual(result["total"], 0)

    async def test_partial_at_one_minute_is_not_included(self):
        movie_id = await self._movie("short-progress")
        await database.save_progress(movie_id, position=60, duration=1200)

        result = await database.get_recent_watched()

        self.assertEqual(result["movies"], [])
        self.assertEqual(result["total"], 0)

    async def test_partially_completed_season_returns_next_episode(self):
        episode_1 = await self._episode(1)
        episode_2 = await self._episode(2)
        await self._episode(3)
        await database.save_progress(episode_1, position=1100, duration=1200)

        result = await database.get_recent_watched()

        self.assertEqual([movie["id"] for movie in result["movies"]], [episode_2])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["movies"][0]["tmdb_episode"], 2)
        self.assertEqual(result["movies"][0]["progress_percent"], 0)

    async def test_completed_season_is_not_included(self):
        episode_ids = [await self._episode(ep) for ep in (1, 2, 3)]
        for episode_id in episode_ids:
            await database.save_progress(episode_id, position=1100, duration=1200)

        result = await database.get_recent_watched()

        self.assertEqual(result["movies"], [])
        self.assertEqual(result["total"], 0)

    async def test_partial_next_episode_is_returned_once(self):
        episode_1 = await self._episode(1)
        episode_2 = await self._episode(2)
        await self._episode(3)
        await database.save_progress(episode_1, position=1100, duration=1200)
        await database.save_progress(episode_2, position=300, duration=1200)

        result = await database.get_recent_watched()

        self.assertEqual([movie["id"] for movie in result["movies"]], [episode_2])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["movies"][0]["progress_percent"], 25)

    async def test_media_root_filter_limits_continue_watching_candidates(self):
        included = await self._movie("included-root")
        excluded = await self._movie("excluded-root", media_root=self.other_root, path=f"{self.other_root}/excluded-root.mkv")
        await database.save_progress(included, position=61, duration=1200)
        await database.save_progress(excluded, position=61, duration=1200)

        result = await database.get_recent_watched(media_root=self.media_root)

        self.assertEqual([movie["id"] for movie in result["movies"]], [included])
        self.assertEqual(result["total"], 1)


if __name__ == "__main__":
    unittest.main()
