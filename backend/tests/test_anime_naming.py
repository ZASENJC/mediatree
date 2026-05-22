import tempfile
import unittest
from pathlib import Path

from app.anime_naming import parse_anime_filename
from app.scanner import scan_media
from app.config import settings
from app import database


class AnimeNamingTest(unittest.TestCase):
    def test_title_episode_and_display_title_samples(self):
        cases = [
            (
                "[ANi] 葬送的芙莉莲 [01][1080P][Baha][WEB-DL][AAC AVC].mkv",
                "葬送的芙莉莲", 1, "葬送的芙莉莲 - EP01",
            ),
            (
                "[NC-Raws] 孤独摇滚 [1080p][HEVC][AAC].mkv",
                "孤独摇滚", None, "孤独摇滚",
            ),
            (
                "[Lilith-Raws] 进击的巨人 [EP12][1080P][HEVC][AAC].mkv",
                "进击的巨人", 12, "进击的巨人 - EP12",
            ),
            (
                "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv",
                "Senpai wa Otokonoko", 12, "Senpai wa Otokonoko - EP12",
            ),
            (
                "[VCB-Studio] Senpai wa Otokonoko [09][Ma10p_1080p][x265_flac].mkv",
                "Senpai wa Otokonoko", 9, "Senpai wa Otokonoko - EP09",
            ),
        ]
        for name, title, episode, display_title in cases:
            with self.subTest(name=name):
                parsed = parse_anime_filename(name)
                self.assertEqual(parsed.clean_title, title)
                self.assertEqual(parsed.episode, episode)
                self.assertEqual(parsed.display_title, display_title)

    def test_does_not_treat_quality_year_or_bit_depth_as_episode(self):
        cases = [
            "[ANi] 某电影 [1080P][HEVC][AAC].mkv",
            "[ANi] 某电影 [2024][1080P][HEVC].mkv",
            "[ANi] 某番剧 [10bit][1080P][HEVC].mkv",
            "[VCB-Studio] Some Movie [Ma10p_1080p][x265_flac].mkv",
        ]
        for name in cases:
            with self.subTest(name=name):
                self.assertIsNone(parse_anime_filename(name).episode)

    def test_volume_pattern_extracts_episode(self):
        cases = [
            ("[Release] Anime Vol.01 [1080p].mkv", 1),
            ("[Release] Anime Vol01 [1080p].mkv", 1),
            ("[Release] Anime VOL 03 [HD].mkv", 3),
            ("[Release] Anime Vol 12 [1080p].mkv", 12),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                parsed = parse_anime_filename(name)
                self.assertEqual(parsed.episode, expected)

    def test_double_episode_extracts_first(self):
        cases = [
            ("[Release] Show S01E01-02 [1080p].mkv", 1),
            ("[Release] Show E05-06 [HD].mkv", 5),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                parsed = parse_anime_filename(name)
                self.assertEqual(parsed.episode, expected)

    def test_large_season_and_episode_numbers(self):
        cases = [
            ("[Release] Show S100E1000 [1080p].mkv", 1000),
            ("[Release] Show 10x100 [HD].mkv", 100),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                parsed = parse_anime_filename(name)
                self.assertEqual(parsed.episode, expected)

    def test_scan_records_clean_episode_fields_audio_and_still(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            series = root / "Series"
            series.mkdir()
            video = series / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv"
            video.write_bytes(b"")
            audio = series / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mka"
            audio.write_bytes(b"")
            still = series / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].jpg"
            still.write_bytes(b"image")

            results = scan_media(str(root))

        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item["clean_title"], "Senpai wa Otokonoko")
        self.assertEqual(item["episode_number"], 12)
        self.assertEqual(item["tmdb_episode"], 12)
        self.assertEqual(item["display_title"], "Senpai wa Otokonoko - EP12")
        self.assertEqual(item["episode_still_local"], str(still))
        self.assertIn(str(audio), item["external_audio_tracks"])


class AnimeEpisodeSortingTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_folder_listing_orders_by_episode_number(self):
        root = Path(self.tmp.name) / "media"
        series = root / "Series"
        series.mkdir(parents=True)
        for episode in (12, 5, 9):
            (series / f"[VCB-Studio] Senpai wa Otokonoko [{episode:02d}][Ma10p_1080p][x265_flac].mkv").write_bytes(b"")

        for item in scan_media(str(root)):
            await database.upsert_movie(item)
        result = await database.get_movies(folder="Series", media_root=str(root), limit=10)

        self.assertEqual(
            [movie["display_title"] for movie in result["movies"]],
            ["Senpai wa Otokonoko - EP05", "Senpai wa Otokonoko - EP09", "Senpai wa Otokonoko - EP12"],
        )


if __name__ == "__main__":
    unittest.main()
