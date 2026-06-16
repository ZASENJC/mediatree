import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database
from app.config import settings
from app.covers import (
    continue_snapshot_path,
    delete_continue_snapshot,
    find_local_episode_still,
    generate_continue_snapshot,
)
from app.main import app


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


class ContinueSnapshotTest(unittest.TestCase):
    def test_generate_and_delete_continue_snapshot_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_data_dir = settings.data_dir
            settings.data_dir = str(root / "data")
            video = root / "movie.mkv"
            video.write_bytes(b"video")
            expected = continue_snapshot_path(str(video))
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_bytes(b"old")

            def fake_run(cmd, capture_output, timeout):
                out = Path(cmd[-1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"jpg")
                return type("Result", (), {"returncode": 0})()

            try:
                with patch("app.covers.subprocess.run", side_effect=fake_run) as run_mock:
                    generated = generate_continue_snapshot(str(video), position_seconds=123.4)

                self.assertEqual(generated, str(expected))
                self.assertTrue(expected.exists())
                self.assertIn("-ss", run_mock.call_args.args[0])
                self.assertIn("123.400", run_mock.call_args.args[0])

                self.assertTrue(delete_continue_snapshot(str(video)))
                self.assertFalse(expected.exists())
            finally:
                settings.data_dir = old_data_dir


class ContinueSnapshotRouteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.media_root = self.root / "media"
        self.media_root.mkdir()
        self.video = self.media_root / "movie.mkv"
        self.video.write_bytes(b"video")
        self.old_data_dir = settings.data_dir
        self.old_media_root = settings.media_root
        self.old_auth_user = settings.auth_user
        self.old_auth_pass = settings.auth_pass
        self.old_auth_password_hash = settings.auth_password_hash
        settings.data_dir = str(self.root / "data")
        settings.media_root = str(self.media_root)
        settings.auth_user = "admin"
        settings.auth_pass = "secret"
        settings.auth_password_hash = ""

    def tearDown(self):
        import asyncio
        asyncio.run(database.close_db_pool())
        settings.data_dir = self.old_data_dir
        settings.media_root = self.old_media_root
        settings.auth_user = self.old_auth_user
        settings.auth_pass = self.old_auth_pass
        settings.auth_password_hash = self.old_auth_password_hash
        self.tmp.cleanup()

    def auth_headers(self):
        import base64
        token = base64.b64encode(b"admin:secret").decode()
        return {"Authorization": f"Basic {token}"}

    def test_snapshot_progress_generates_cache_readable_by_continue_cover(self):
        import asyncio

        async def seed_movie():
            await database.close_db_pool()
            await database.init_db()
            return await database.upsert_movie({
                "path": str(self.video),
                "code": "movie",
                "title": "movie",
                "duration": 1200,
                "folder_levels": "",
                "media_root": str(self.media_root),
                "tmdb_type": "movie",
            })

        movie_id = asyncio.run(seed_movie())

        def fake_run(cmd, capture_output, timeout):
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"snapshot")
            return type("Result", (), {"returncode": 0})()

        with TestClient(app) as client, patch("app.covers.subprocess.run", side_effect=fake_run):
            progress = client.post(
                f"/api/progress/{movie_id}",
                json={"position": 123.4, "duration": 1200, "stopped": True, "snapshot": True},
                headers=self.auth_headers(),
            )
            self.assertEqual(progress.status_code, 200)

            cover = client.get(f"/api/continue-cover/{movie_id}", headers=self.auth_headers())

        self.assertEqual(cover.status_code, 200)
        self.assertEqual(cover.content, b"snapshot")


if __name__ == "__main__":
    unittest.main()
