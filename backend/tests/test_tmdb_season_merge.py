"""Tests for auto season-merge fallback in match_episodes_in_folder.

When TMDB has no separate season for a given season_number (e.g. S02),
try offset-mapping into an existing TMDB season via sibling folders.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import config, database, tmdb


class _FakeSeasonEpisodes:
    """Helper to build mock fetch_tv_season responses."""

    @staticmethod
    def build(season_num: int, episode_numbers: list[int]) -> dict:
        return {
            "season_number": season_num,
            "name": f"Season {season_num}",
            "overview": "",
            "poster_path": None,
            "air_date": None,
            "episode_count": len(episode_numbers),
            "episodes": [
                {
                    "episode_number": n,
                    "name": f"Episode {n}",
                    "overview": f"Overview {n}",
                    "still_path": None,
                    "air_date": None,
                }
                for n in episode_numbers
            ],
        }


class SeasonMergeBasicTest(unittest.IsolatedAsyncioTestCase):
    """S02 local E01-E12 with TMDB S01 E01-E24 -> match as S01 E13-E24."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.media_root = str(self.tmp_path / "media")
        Path(self.media_root).mkdir(parents=True)
        self.old_data_dir = config.settings.data_dir
        config.settings.data_dir = str(self.tmp_path / "data")
        await database.close_db_pool()
        await database.init_db()
        self.db = await database.get_db()

    async def asyncTearDown(self):
        await database.close_db_pool()
        config.settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    async def _insert_s01_matched(self):
        """S01: local EP01-EP12 already matched as TMDB S01 E01-E12."""
        for ep in range(1, 13):
            path = f"{self.media_root}/ShowName/S01/EP{ep:02d}.mkv"
            await self.db.execute(
                "INSERT INTO movies (path, code, folder_levels, media_root, "
                "tmdb_id, tmdb_type, tmdb_season, tmdb_episode, episode_title) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (path, f"EP{ep:02d}", "ShowName/S01", self.media_root,
                 12345, "tv", 1, ep, f"Ep {ep}"),
            )

    async def _insert_s02_local(self):
        """S02: local EP01-EP12, NOT yet matched (no tmdb_episode)."""
        for ep in range(1, 13):
            path = f"{self.media_root}/ShowName/S02/EP{ep:02d}.mkv"
            await self.db.execute(
                "INSERT INTO movies (path, code, folder_levels, media_root, "
                "tmdb_id, tmdb_type) VALUES (?,?,?,?,?,?)",
                (path, f"EP{ep:02d}", "ShowName/S02", self.media_root,
                 12345, "tv"),
            )

    def _mock_fetch_tv_season(self, series_id, season_number, lang="zh-CN"):
        """TMDB has S01 E01-E24, S02 has 0 episodes."""
        if season_number == 1:
            return _FakeSeasonEpisodes.build(1, list(range(1, 25)))
        return None

    async def test_season_merge_basic(self):
        await self._insert_s01_matched()
        await self._insert_s02_local()

        with patch.object(tmdb, "fetch_tv_season", side_effect=self._mock_fetch_tv_season):
            # The first call (season 2) returns None → triggers merge fallback
            # merge will call fetch_tv_season again with season 1
            result = await tmdb.match_episodes_in_folder(
                "12345", 2, "ShowName/S02", self.media_root
            )
            self.assertEqual(result, 12)

        # Verify DB: S02 movies now have tmdb_season=1, tmdb_episode=13..24
        cur = await self.db.execute(
            "SELECT tmdb_season, tmdb_episode FROM movies "
            "WHERE folder_levels='ShowName/S02' AND media_root=? "
            "ORDER BY tmdb_episode",
            (self.media_root,),
        )
        rows = await cur.fetchall()
        self.assertEqual(len(rows), 12)
        for i, row in enumerate(rows):
            expected_ep = 13 + i
            self.assertEqual(row["tmdb_season"], 1,
                             f"EP{i + 1:02d}: expected season 1")
            self.assertEqual(row["tmdb_episode"], expected_ep,
                             f"EP{i + 1:02d}: expected episode {expected_ep}")


class SeasonMergeCumulativeTest(unittest.IsolatedAsyncioTestCase):
    """S03: cumulative offset from S01(12ep) + S02(12ep) = 24."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.media_root = str(self.tmp_path / "media")
        Path(self.media_root).mkdir(parents=True)
        self.old_data_dir = config.settings.data_dir
        config.settings.data_dir = str(self.tmp_path / "data")
        await database.close_db_pool()
        await database.init_db()
        self.db = await database.get_db()

    async def asyncTearDown(self):
        await database.close_db_pool()
        config.settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    async def _insert_two_siblings_matched(self):
        """S01: 12ep matched, S02: 12ep matched (both → TMDB S01)."""
        tmdb_id = 12345
        for ep in range(1, 13):
            await self.db.execute(
                "INSERT INTO movies (path, code, folder_levels, media_root, "
                "tmdb_id, tmdb_type, tmdb_season, tmdb_episode, episode_title) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"{self.media_root}/Show/S01/E{ep:02d}.mkv", f"E{ep:02d}",
                 "Show/S01", self.media_root, tmdb_id, "tv", 1, ep, f"Ep {ep}"),
            )
        for ep in range(1, 13):
            await self.db.execute(
                "INSERT INTO movies (path, code, folder_levels, media_root, "
                "tmdb_id, tmdb_type, tmdb_season, tmdb_episode, episode_title) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"{self.media_root}/Show/S02/E{ep:02d}.mkv", f"E{ep:02d}",
                 "Show/S02", self.media_root, tmdb_id, "tv", 1, 12 + ep, f"Ep {12+ep}"),
            )

    async def _insert_s03_local(self):
        for ep in range(1, 7):
            await self.db.execute(
                "INSERT INTO movies (path, code, folder_levels, media_root, "
                "tmdb_id, tmdb_type) VALUES (?,?,?,?,?,?)",
                (f"{self.media_root}/Show/S03/E{ep:02d}.mkv", f"E{ep:02d}",
                 "Show/S03", self.media_root, 12345, "tv"),
            )

    def _mock_fetch(self, series_id, season_number, lang="zh-CN"):
        if season_number == 1:
            return _FakeSeasonEpisodes.build(1, list(range(1, 31)))
        return None

    async def test_season_merge_cumulative(self):
        await self._insert_two_siblings_matched()
        await self._insert_s03_local()

        with patch.object(tmdb, "fetch_tv_season", side_effect=self._mock_fetch):
            result = await tmdb.match_episodes_in_folder(
                "12345", 3, "Show/S03", self.media_root
            )
            self.assertEqual(result, 6)

            cur = await self.db.execute(
                "SELECT tmdb_season, tmdb_episode FROM movies "
                "WHERE folder_levels='Show/S03' AND media_root=? "
                "ORDER BY tmdb_episode",
                (self.media_root,),
            )
            rows = await cur.fetchall()
            self.assertEqual(len(rows), 6)
            for i, row in enumerate(rows):
                expected_ep = 25 + i  # offset = 24
                self.assertEqual(row["tmdb_season"], 1)
                self.assertEqual(row["tmdb_episode"], expected_ep)


class SeasonMergeNoMergeTest(unittest.IsolatedAsyncioTestCase):
    """Normal case: S01 and S02 both exist on TMDB with episodes — no merge."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.media_root = str(self.tmp_path / "media")
        Path(self.media_root).mkdir(parents=True)
        self.old_data_dir = config.settings.data_dir
        config.settings.data_dir = str(self.tmp_path / "data")
        await database.close_db_pool()
        await database.init_db()
        self.db = await database.get_db()

    async def asyncTearDown(self):
        await database.close_db_pool()
        config.settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    async def _insert_s02_local(self):
        for ep in range(1, 6):
            await self.db.execute(
                "INSERT INTO movies (path, code, folder_levels, media_root, "
                "tmdb_id, tmdb_type) VALUES (?,?,?,?,?,?)",
                (f"{self.media_root}/Show/S02/E{ep:02d}.mkv", f"E{ep:02d}",
                 "Show/S02", self.media_root, 12345, "tv"),
            )

    def _mock_fetch(self, series_id, season_number, lang="zh-CN"):
        """Both S01 and S02 exist on TMDB with their own episodes."""
        if season_number == 1:
            return _FakeSeasonEpisodes.build(1, list(range(1, 13)))
        if season_number == 2:
            return _FakeSeasonEpisodes.build(2, list(range(1, 6)))
        return None

    async def test_no_merge_when_tmdb_has_season(self):
        await self._insert_s02_local()

        with patch.object(tmdb, "fetch_tv_season", side_effect=self._mock_fetch):
            result = await tmdb.match_episodes_in_folder(
                "12345", 2, "Show/S02", self.media_root
            )
            # Normal matching: S02 local E01-E05 → TMDB S02 E01-E05
            self.assertEqual(result, 5)

            cur = await self.db.execute(
                "SELECT tmdb_season, tmdb_episode FROM movies "
                "WHERE folder_levels='Show/S02' AND media_root=? "
                "ORDER BY tmdb_episode",
                (self.media_root,),
            )
            rows = await cur.fetchall()
            for row in rows:
                self.assertEqual(row["tmdb_season"], 2,
                                 "Should match their own season, not merged")


class SeasonMergeSpecialsTest(unittest.IsolatedAsyncioTestCase):
    """Specials (S00 / season_number=0) should NOT trigger merge."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.media_root = str(self.tmp_path / "media")
        Path(self.media_root).mkdir(parents=True)
        self.old_data_dir = config.settings.data_dir
        config.settings.data_dir = str(self.tmp_path / "data")
        await database.close_db_pool()
        await database.init_db()
        self.db = await database.get_db()

    async def asyncTearDown(self):
        await database.close_db_pool()
        config.settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    def _mock_fetch(self, series_id, season_number, lang="zh-CN"):
        return None  # S00 doesn't exist as a real season

    async def test_specials_no_merge(self):
        await self.db.execute(
            "INSERT INTO movies (path, code, folder_levels, media_root, "
            "tmdb_id, tmdb_type) VALUES (?,?,?,?,?,?)",
            (f"{self.media_root}/Show/Specials/OVA.mkv", "OVA",
             "Show/Specials", self.media_root, 12345, "tv"),
        )
        await self.db.execute(
            "INSERT INTO movies (path, code, folder_levels, media_root, "
            "tmdb_id, tmdb_type, tmdb_season, tmdb_episode) VALUES (?,?,?,?,?,?,?,?)",
            (f"{self.media_root}/Show/S01/E01.mkv", "E01",
             "Show/S01", self.media_root, 12345, "tv", 1, 1),
        )
        await self.db.commit()

        with patch.object(tmdb, "fetch_tv_season", side_effect=self._mock_fetch):
            result = await tmdb.match_episodes_in_folder(
                "12345", 0, "Show/Specials", self.media_root
            )
            # season_number=0 → guarded by season_number > 0 in merge fallback
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
