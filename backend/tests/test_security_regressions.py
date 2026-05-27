import base64
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import config, database, main
from app.config import fetch_safe_image
from app.jellyfin_compat import jf_authenticate_by_name
from app.jellyfin_models import AuthByNameRequest
from app.updater import _format_command_for_logs, _trim_update_logs


class SecurityRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.media_root = self.root / "media"
        self.media_root.mkdir()
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()
        self.video_path = self.media_root / "Movie.mp4"
        self.video_path.write_bytes(b"video")

        self.orig_media_root = config.settings.media_root
        self.orig_data_dir = config.settings.data_dir
        self.orig_auth_user = config.settings.auth_user
        self.orig_auth_pass = config.settings.auth_pass
        self.orig_tmdb_token = config.settings.tmdb_access_token
        self.orig_db_pool = database._db_pool

        config.settings.media_root = str(self.media_root)
        config.settings.data_dir = str(self.data_dir)
        config.settings.auth_user = "admin"
        config.settings.auth_pass = "secret"
        config.settings.tmdb_access_token = ""
        database._db_pool = None

        async def fake_detail(movie_id: int):
            return {
                "id": movie_id,
                "path": str(self.video_path),
                "media_root": str(self.media_root),
                "cover_local": "",
                "cover_remote": "",
                "javdb_thumbnails": [],
            }

        self.detail_patch = patch("app.main.get_movie_detail", fake_detail)
        self.detail_patch.start()

    def tearDown(self):
        self.detail_patch.stop()
        database._db_pool = self.orig_db_pool
        config.settings.media_root = self.orig_media_root
        config.settings.data_dir = self.orig_data_dir
        config.settings.auth_user = self.orig_auth_user
        config.settings.auth_pass = self.orig_auth_pass
        config.settings.tmdb_access_token = self.orig_tmdb_token
        self.tmpdir.cleanup()

    def auth_headers(self):
        token = base64.b64encode(b"admin:secret").decode()
        return {"Authorization": f"Basic {token}"}

    def test_stream_requires_auth_or_media_token_when_auth_enabled(self):
        with TestClient(main.app) as client:
            response = client.get("/api/stream/1")
            self.assertEqual(response.status_code, 401)

            token_response = client.post("/api/media-token", headers=self.auth_headers())
            self.assertEqual(token_response.status_code, 200)
            media_token = token_response.json()["token"]

            authorized = client.get(f"/api/stream/1?token={media_token}")
            self.assertEqual(authorized.status_code, 200)

    def test_static_media_file_requires_media_token(self):
        relative_path = self.video_path.relative_to(self.media_root)
        with TestClient(main.app) as client:
            response = client.get(f"/api/media/{relative_path}")
            self.assertEqual(response.status_code, 401)

            token_response = client.post("/api/media-token", headers=self.auth_headers())
            media_token = token_response.json()["token"]

            authorized = client.get(f"/api/media/{relative_path}?token={media_token}")
            self.assertEqual(authorized.status_code, 200)

    def test_login_returns_signed_session_not_encoded_password(self):
        with TestClient(main.app) as client:
            response = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

            self.assertEqual(response.status_code, 200)
            session_token = response.json()["token"]
            self.assertNotEqual(session_token, config.settings.auth_token)

            authorized = client.get("/api/stream/1", headers={"Authorization": f"Bearer {session_token}"})
            self.assertEqual(authorized.status_code, 200)

    def test_subtitle_tracks_do_not_expose_local_paths(self):
        with TestClient(main.app) as client:
            token_response = client.post("/api/media-token", headers=self.auth_headers())
            media_token = token_response.json()["token"]

            with patch("app.main.get_subtitle_tracks", return_value=[{"index": 0, "stream_index": 0, "codec": "srt"}]), \
                    patch("app.main.find_external_subtitles", return_value=[{"path": str(self.media_root / "Movie.srt"), "format": "srt"}]):
                response = client.get(f"/api/subtitle-tracks/1?token={media_token}")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertNotIn("path", body[0])
            self.assertNotIn("path", body[1])

    def test_restore_upload_rejects_tar_members_that_escape_data_dir(self):
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w:gz") as tar:
            data = b"escape"
            info = tarfile.TarInfo("covers/../../escaped.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        payload.seek(0)

        with TestClient(main.app) as client:
            response = client.post(
                "/api/restore/upload",
                files={"file": ("bad.tar.gz", payload.getvalue(), "application/gzip")},
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / "escaped.txt").exists())

    def test_jellyfin_login_fails_closed_without_primary_auth(self):
        config.settings.auth_user = ""
        config.settings.auth_pass = ""

        class RequestStub:
            headers = {}

        async def run():
            body = AuthByNameRequest(Username="anyone", Pw="anything")
            with self.assertRaises(HTTPException) as ctx:
                await jf_authenticate_by_name(RequestStub(), body)
            self.assertEqual(ctx.exception.status_code, 401)

        import asyncio
        asyncio.run(run())

    def test_update_logs_redact_sensitive_env_values(self):
        command = ["docker", "run", "-e", "AUTH_PASS=secret", "-e", "TMDB_ACCESS_TOKEN=abc123", "-e", "PORT=80"]
        rendered = _format_command_for_logs(command)
        self.assertIn("AUTH_PASS=***", rendered)
        self.assertIn("TMDB_ACCESS_TOKEN=***", rendered)
        self.assertIn("PORT=80", rendered)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("abc123", rendered)

        logs = _trim_update_logs(["AUTH_PASS=secret", "plain output"])
        self.assertEqual(logs[0], "AUTH_PASS=***")
        self.assertEqual(logs[1], "plain output")

    def test_safe_image_fetch_rejects_redirect_to_untrusted_host(self):
        class FakeResponse:
            status_code = 302
            headers = {"location": "http://127.0.0.1/private.jpg"}
            url = "https://image.tmdb.org/t/p/original/poster.jpg"

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def stream(self, *args, **kwargs):
                return FakeResponse()

        with patch("httpx.AsyncClient", FakeClient):
            import asyncio
            result = asyncio.run(fetch_safe_image("https://image.tmdb.org/t/p/original/poster.jpg"))

        self.assertIsNone(result)

    def test_initial_setup_can_save_tmdb_token_without_existing_session(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/api/setup/save",
                json={
                    "tmdb_access_token": "Bearer setup-token",
                    "libraries": [{"media_root": str(self.media_root), "scraper": "tmdb_tv"}],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(config.settings.tmdb_access_token, "setup-token")

    def test_setup_save_requires_auth_after_initial_setup_completed(self):
        import asyncio

        async def seed_library():
            await database.init_db()
            await database.save_library_settings({
                "media_root": str(self.media_root),
                "scraper": "auto",
                "tmdb_key": "",
                "password_hash": None,
                "enabled": 1,
            })

        asyncio.run(seed_library())

        with TestClient(main.app) as client:
            response = client.post(
                "/api/setup/save",
                json={"libraries": [{"media_root": str(self.media_root), "scraper": "tmdb_movie"}]},
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
