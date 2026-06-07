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

    async def test_build_release_entry_marks_windows_base_update_on_windows_runtime(self):
        release = {
            "version": "1.0.11",
            "display_version": "v1.0.11",
            "name": "v1.0.11",
            "published_at": "2026-06-08T00:00:00Z",
            "html_url": "https://example.com/release/v1.0.11",
            "body": "",
            "source": "github",
            "assets": [
                {
                    "name": "mediatree-app-1.0.11.manifest.json",
                    "browser_download_url": "https://example.com/manifest.json",
                },
                {
                    "name": "mediatree-app-1.0.11.tar.gz",
                    "browser_download_url": "https://example.com/archive.tar.gz",
                    "size": 123,
                },
            ],
        }
        manifest = {
            "version": "1.0.11",
            "base_api": 1,
            "requires_image_update": False,
            "requires_windows_base_update": True,
            "reason": "应用包级更新；不需要完整 Docker 镜像更新。",
            "windows_reason": "Windows runtime changed.",
            "sha256": "abc",
            "size": 123,
        }

        with patch.object(updater, "UPDATE_PLATFORM", "windows"), \
                patch.object(updater, "_fetch_json_url", AsyncMock(return_value=manifest)):
            entry = await updater._build_release_entry(release)

        self.assertEqual(entry["update_type"], "windows-base-required")
        self.assertTrue(entry["requires_windows_base_update"])
        self.assertFalse(entry["requires_image_update"])
        self.assertEqual(entry["reason"], "Windows runtime changed.")

    async def test_build_release_entry_keeps_docker_app_package_when_only_windows_base_required(self):
        release = {
            "version": "1.0.11",
            "display_version": "v1.0.11",
            "name": "v1.0.11",
            "published_at": "2026-06-08T00:00:00Z",
            "html_url": "https://example.com/release/v1.0.11",
            "body": "",
            "source": "github",
            "assets": [
                {
                    "name": "mediatree-app-1.0.11.manifest.json",
                    "browser_download_url": "https://example.com/manifest.json",
                },
                {
                    "name": "mediatree-app-1.0.11.tar.gz",
                    "browser_download_url": "https://example.com/archive.tar.gz",
                    "size": 123,
                },
            ],
        }
        manifest = {
            "version": "1.0.11",
            "base_api": 1,
            "requires_image_update": False,
            "requires_windows_base_update": True,
            "reason": "应用包级更新；不需要完整 Docker 镜像更新。",
            "windows_reason": "Windows runtime changed.",
            "sha256": "abc",
            "size": 123,
        }

        with patch.object(updater, "UPDATE_PLATFORM", "docker"), \
                patch.object(updater, "_fetch_json_url", AsyncMock(return_value=manifest)):
            entry = await updater._build_release_entry(release)

        self.assertEqual(entry["update_type"], "app-package")
        self.assertTrue(entry["requires_windows_base_update"])
        self.assertFalse(entry["requires_image_update"])
        self.assertEqual(entry["reason"], "应用包级更新；不需要完整 Docker 镜像更新。")

    async def test_perform_app_package_update_rejects_windows_base_required_release(self):
        release_entry = {
            "version": "1.0.11",
            "requires_image_update": False,
            "requires_windows_base_update": True,
            "reason": "Windows runtime changed.",
            "archive_url": "https://example.com/archive.tar.gz",
            "base_api": updater.BASE_API_VERSION,
        }

        with patch.object(updater, "UPDATE_PLATFORM", "windows"), \
                patch.object(updater, "_get_release_entry", AsyncMock(return_value=release_entry)):
            result = await updater.perform_app_package_update("1.0.11")

        self.assertFalse(result["ok"])
        self.assertTrue(result["requires_windows_base_update"])
        self.assertIn("Windows runtime changed.", result["error"])

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

    def test_cleanup_old_app_packages_keeps_current_and_previous_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases_dir = root / "releases"
            updates_dir = root / "updates"
            releases_dir.mkdir(parents=True)
            updates_dir.mkdir(parents=True)

            def make_app(version: str) -> None:
                app_dir = releases_dir / version
                (app_dir / "app").mkdir(parents=True)
                (app_dir / "frontend" / "dist").mkdir(parents=True)
                (app_dir / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
                (app_dir / "frontend" / "dist" / "index.html").write_text("<html></html>\n", encoding="utf-8")
                (app_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")

            for version in ("1.0.01", "1.0.02", "1.0.03", "1.0.04"):
                make_app(version)
                (updates_dir / f"mediatree-app-{version}.tar.gz").write_bytes(b"archive")
            (releases_dir / "1.0.05.staging").mkdir()
            (releases_dir / "manual-notes").mkdir()
            (releases_dir / "current").write_text("1.0.04\n", encoding="utf-8")
            (releases_dir / "previous").write_text("1.0.03\n", encoding="utf-8")

            with patch.object(updater, "RELEASES_DIR", releases_dir), \
                    patch.object(updater, "UPDATES_DIR", updates_dir):
                removed = updater._cleanup_old_app_packages("1.0.04")

            self.assertEqual(removed["release_dirs"], ["1.0.01", "1.0.02", "1.0.05.staging"])
            self.assertEqual(removed["archives"], ["mediatree-app-1.0.01.tar.gz", "mediatree-app-1.0.02.tar.gz"])
            self.assertTrue((releases_dir / "1.0.03").exists())
            self.assertTrue((releases_dir / "1.0.04").exists())
            self.assertTrue((updates_dir / "mediatree-app-1.0.03.tar.gz").exists())
            self.assertTrue((updates_dir / "mediatree-app-1.0.04.tar.gz").exists())
            self.assertTrue((releases_dir / "manual-notes").exists())
            self.assertFalse((releases_dir / "1.0.01").exists())
            self.assertFalse((updates_dir / "mediatree-app-1.0.01.tar.gz").exists())

    def test_mark_update_success_after_restart_cleans_old_app_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases_dir = root / "releases"
            updates_dir = root / "updates"
            status_file = updates_dir / "status.json"
            releases_dir.mkdir(parents=True)
            updates_dir.mkdir(parents=True)

            def make_app(version: str) -> None:
                app_dir = releases_dir / version
                (app_dir / "app").mkdir(parents=True)
                (app_dir / "frontend" / "dist").mkdir(parents=True)
                (app_dir / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
                (app_dir / "frontend" / "dist" / "index.html").write_text("<html></html>\n", encoding="utf-8")
                (app_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")

            for version in ("1.0.02", "1.0.03", "1.0.04"):
                make_app(version)
                (updates_dir / f"mediatree-app-{version}.tar.gz").write_bytes(b"archive")
            (releases_dir / "current").write_text("1.0.04\n", encoding="utf-8")
            (releases_dir / "previous").write_text("1.0.03\n", encoding="utf-8")
            status_file.write_text(json.dumps({
                "status": "restarting",
                "version": "1.0.04",
                "downloaded": 0,
                "total": 0,
                "message": "正在重启服务...",
                "update_type": "app-package",
                "logs": [],
            }), encoding="utf-8")

            with patch.object(updater, "RELEASES_DIR", releases_dir), \
                    patch.object(updater, "UPDATES_DIR", updates_dir), \
                    patch.object(updater, "UPDATE_STATUS_FILE", status_file), \
                    patch.object(updater, "get_current_version", return_value="1.0.04"):
                updater.mark_update_success_after_restart()

            status = json.loads(status_file.read_text(encoding="utf-8"))

            self.assertEqual(status["status"], "success")
            self.assertEqual(status["version"], "1.0.04")
            self.assertTrue((releases_dir / "1.0.04").exists())
            self.assertTrue((releases_dir / "1.0.03").exists())
            self.assertFalse((releases_dir / "1.0.02").exists())
            self.assertTrue((updates_dir / "mediatree-app-1.0.04.tar.gz").exists())
            self.assertTrue((updates_dir / "mediatree-app-1.0.03.tar.gz").exists())
            self.assertFalse((updates_dir / "mediatree-app-1.0.02.tar.gz").exists())


if __name__ == "__main__":
    unittest.main()
