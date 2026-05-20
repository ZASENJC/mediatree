import tempfile
import unittest
from pathlib import Path

from app.covers import find_local_episode_still


class EpisodeStillDiscoveryTest(unittest.TestCase):
    def test_finds_exact_basename_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv"
            video.write_bytes(b"")
            still = root / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].jpg"
            still.write_bytes(b"image")

            self.assertEqual(find_local_episode_still(str(video)), str(still))

    def test_finds_cover_still_thumb_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "Show.S01E01.mkv"
            video.write_bytes(b"")
            still = root / "Show.S01E01.still.webp"
            still.write_bytes(b"image")

            self.assertEqual(find_local_episode_still(str(video)), str(still))


if __name__ == "__main__":
    unittest.main()
