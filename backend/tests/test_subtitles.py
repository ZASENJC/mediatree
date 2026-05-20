import tempfile
import unittest
from pathlib import Path

from app.subtitles import find_external_audio_tracks, find_external_subtitles, get_subtitle_content


class ExternalSubtitleDiscoveryTest(unittest.TestCase):
    def test_discovers_language_suffix_and_subtitle_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "Show.S01E01.mkv"
            video.write_bytes(b"")
            (root / "Show.S01E01.zh.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n中文\n", encoding="utf-8")
            subs = root / "Subtitles"
            subs.mkdir()
            (subs / "Show.S01E01.ja.ass").write_text(
                "[Script Info]\n[V4+ Styles]\n[Events]\n",
                encoding="utf-8",
            )

            tracks = find_external_subtitles(str(video))
            names = {track["name"] for track in tracks}
            langs = {track["name"]: track["language"] for track in tracks}

        self.assertIn("Show.S01E01.zh.srt", names)
        self.assertIn("Show.S01E01.ja.ass", names)
        self.assertEqual(langs["Show.S01E01.zh.srt"], "chi")
        self.assertEqual(langs["Show.S01E01.ja.ass"], "jpn")

    def test_gbk_subtitle_content_is_decoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Movie.chs.srt"
            path.write_bytes("1\n00:00:01,000 --> 00:00:02,000\n中文字幕\n".encode("gbk"))
            content = get_subtitle_content(str(path))
        self.assertIsNotNone(content)
        self.assertIn("中文字幕", content or "")

    def test_single_video_folder_includes_related_subtitle_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "Movie.mkv"
            video.write_bytes(b"")
            (root / "简体中文.ass").write_text("[Script Info]\n", encoding="utf-8")
            subs = root / "Subs"
            subs.mkdir()
            (subs / "English.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")

            tracks = find_external_subtitles(str(video))
            names = {track["name"] for track in tracks}

        self.assertIn("简体中文.ass", names)
        self.assertIn("English.srt", names)

    def test_multi_video_folder_does_not_attach_unmatched_generic_subtitle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "Show.S01E01.mkv"
            video.write_bytes(b"")
            (root / "Show.S01E02.mkv").write_bytes(b"")
            subs = root / "Subs"
            subs.mkdir()
            (subs / "English.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
            (subs / "Show.S01E01.zh.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n中文\n", encoding="utf-8")

            tracks = find_external_subtitles(str(video))
            names = {track["name"] for track in tracks}

        self.assertIn("Show.S01E01.zh.srt", names)
        self.assertNotIn("English.srt", names)

    def test_vcb_language_suffix_subtitle_matches_exact_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv"
            video.write_bytes(b"")
            sub = root / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].zh.ass"
            sub.write_text("[Script Info]\n", encoding="utf-8")
            other = root / "[VCB-Studio] Senpai wa Otokonoko [11][Ma10p_1080p][x265_flac].zh.ass"
            other.write_text("[Script Info]\n", encoding="utf-8")

            tracks = find_external_subtitles(str(video))
            names = {track["name"] for track in tracks}
            by_name = {track["name"]: track for track in tracks}

        self.assertIn(sub.name, names)
        self.assertNotIn(other.name, names)
        self.assertEqual(by_name[sub.name]["language"], "chi")
        self.assertEqual(by_name[sub.name]["format"], "ass")
        self.assertTrue(by_name[sub.name]["is_external"])

    def test_vcb_external_audio_matches_exact_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv"
            video.write_bytes(b"")
            audio = root / "[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mka"
            audio.write_bytes(b"")
            other = root / "[VCB-Studio] Senpai wa Otokonoko [11][Ma10p_1080p][x265_flac].mka"
            other.write_bytes(b"")

            tracks = find_external_audio_tracks(str(video))
            names = {track["name"] for track in tracks}
            by_name = {track["name"]: track for track in tracks}

        self.assertIn(audio.name, names)
        self.assertNotIn(other.name, names)
        self.assertEqual(by_name[audio.name]["format"], "mka")
        self.assertTrue(by_name[audio.name]["is_external"])


if __name__ == "__main__":
    unittest.main()
