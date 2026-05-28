import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import updater


class UpdaterVersionStateTest(unittest.IsolatedAsyncioTestCase):
    def test_get_version_state_marks_outdated_overlay(self):
        with patch.object(updater, "APP_SOURCE", "app-package"), \
                patch.object(updater, "get_current_version", return_value="1.0.03"), \
                patch.object(updater, "get_base_version", return_value="1.0.04"):
            state = updater.get_version_state()

        self.assertEqual(state["current_version"], "1.0.04")
        self.assertEqual(state["runtime_version"], "1.0.03")
        self.assertEqual(state["base_version"], "1.0.04")
        self.assertEqual(state["effective_version"], "1.0.04")
        self.assertTrue(state["overlay_active"])
        self.assertTrue(state["overlay_is_outdated"])
        self.assertIn("当前已更新到 1.0.04", state["status_note"])

    async def test_get_available_versions_exposes_base_version_and_overlay_state(self):
        release = {
            "version": "1.0.04",
            "display_version": "v1.0.04",
            "name": "v1.0.04",
            "published_at": "2026-05-29T00:00:00Z",
            "html_url": "https://example.com/release/v1.0.04",
            "body": "",
            "source": "github",
            "assets": [],
        }
        release_entry = {
            "version": "1.0.04",
            "display_version": "v1.0.04",
            "published_at": "2026-05-29T00:00:00Z",
            "html_url": "https://example.com/release/v1.0.04",
            "source": "github-release",
            "update_type": "docker-image-required",
            "size": 0,
            "requires_image_update": True,
            "reason": "该版本需要完整镜像更新。",
        }
        version_state = {
            "current_version": "1.0.04",
            "runtime_version": "1.0.03",
            "current_source": "app-package",
            "base_version": "1.0.04",
            "effective_version": "1.0.04",
            "overlay_active": True,
            "overlay_is_outdated": True,
            "status_note": "当前已更新到 1.0.04。运行中的应用包仍是 1.0.03，镜像内置版本是 1.0.04。",
        }

        with patch.object(updater, "get_version_state", return_value=version_state), \
                patch.object(updater, "fetch_github_releases", AsyncMock(return_value=[release])), \
                patch.object(updater, "_build_release_entry", AsyncMock(return_value=release_entry)):
            result = await updater.get_available_versions()

        self.assertEqual(result["current_version"], "1.0.04")
        self.assertEqual(result["base_version"], "1.0.04")
        self.assertEqual(result["effective_version"], "1.0.04")
        self.assertTrue(result["overlay_active"])
        self.assertTrue(result["overlay_is_outdated"])
        self.assertFalse(result["has_update"])
        self.assertEqual(result["versions"][0]["display_version"], "v1.0.04")

    def test_get_update_status_clears_stale_error_for_current_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases_dir = root / "releases"
            updates_dir = root / "updates"
            status_file = updates_dir / "status.json"
            updates_dir.mkdir(parents=True)
            status_file.write_text(json.dumps({
                "status": "error",
                "version": "1.0.04",
                "downloaded": 0,
                "total": 0,
                "message": "Docker CLI not found in container.",
                "update_type": "docker-image",
                "logs": ["Docker CLI not found in container."],
            }), encoding="utf-8")

            with patch.object(updater, "RELEASES_DIR", releases_dir), \
                    patch.object(updater, "UPDATES_DIR", updates_dir), \
                    patch.object(updater, "UPDATE_STATUS_FILE", status_file), \
                    patch.object(updater, "get_version_state", return_value={"current_version": "1.0.04"}):
                status = updater.get_update_status()

        self.assertEqual(status["status"], "success")
        self.assertEqual(status["version"], "1.0.04")
        self.assertEqual(status["message"], "更新已完成。")
        self.assertEqual(status["logs"], [])


if __name__ == "__main__":
    unittest.main()
