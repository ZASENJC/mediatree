import os
import sys
import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import windows_runtime


def make_app_dir(root: Path, version: str) -> Path:
    app_dir = root / version
    (app_dir / "app").mkdir(parents=True)
    (app_dir / "frontend" / "dist").mkdir(parents=True)
    (app_dir / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (app_dir / "frontend" / "dist" / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (app_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    return app_dir


class WindowsRuntimeTest(unittest.TestCase):
    def test_choose_app_dir_prefers_current_app_package_when_newer_than_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_dir = make_app_dir(root / "base", "1.0.01")
            releases_dir = root / "data" / "releases"
            current_dir = make_app_dir(releases_dir, "1.0.02")
            (releases_dir / "current").write_text("1.0.02\n", encoding="utf-8")

            choice = windows_runtime.choose_app_dir(root / "data", base_dir)

        self.assertEqual(choice.app_dir, current_dir)
        self.assertEqual(choice.source, "app-package")
        self.assertEqual(choice.version, "1.0.02")

    def test_choose_app_dir_prefers_newer_base_over_outdated_current_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_dir = make_app_dir(root / "base", "1.0.03")
            releases_dir = root / "data" / "releases"
            make_app_dir(releases_dir, "1.0.02")
            (releases_dir / "current").write_text("1.0.02\n", encoding="utf-8")

            choice = windows_runtime.choose_app_dir(root / "data", base_dir)

        self.assertEqual(choice.app_dir, base_dir)
        self.assertEqual(choice.source, "base")
        self.assertEqual(choice.version, "1.0.03")

    def test_choose_app_dir_recovers_previous_when_current_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_dir = make_app_dir(root / "base", "1.0.01")
            releases_dir = root / "data" / "releases"
            previous_dir = make_app_dir(releases_dir, "1.0.02")
            (releases_dir / "current").write_text("1.0.03\n", encoding="utf-8")
            (releases_dir / "previous").write_text("1.0.02\n", encoding="utf-8")

            choice = windows_runtime.choose_app_dir(root / "data", base_dir)

            self.assertEqual((releases_dir / "current").read_text(encoding="utf-8").strip(), "1.0.02")

        self.assertEqual(choice.app_dir, previous_dir)
        self.assertEqual(choice.source, "app-package")

    def test_prepare_environment_sets_windows_runtime_paths_before_importing_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            base_dir = make_app_dir(root / "base", "1.0.01")
            bin_dir = root / "bin"
            media_root = root / "media"
            original_path = os.environ.get("PATH", "")

            with patch.dict(os.environ, {}, clear=True):
                fake_app = types.ModuleType("app")
                fake_app.__path__ = []
                original_app = sys.modules.get("app")
                sys.modules["app"] = fake_app
                choice = windows_runtime.prepare_environment(
                    data_dir=data_dir,
                    base_dir=base_dir,
                    bin_dir=bin_dir,
                    media_root=media_root,
                )

                try:
                    self.assertEqual(os.environ["DATA_DIR"], str(data_dir.resolve()))
                    self.assertEqual(os.environ["MEDIA_ROOT"], str(media_root.resolve()))
                    self.assertEqual(os.environ["MEDIATREE_BASE_DIR"], str(base_dir.resolve()))
                    self.assertEqual(os.environ["MEDIATREE_APP_DIR"], str(base_dir.resolve()))
                    self.assertEqual(os.environ["MEDIATREE_APP_SOURCE"], "base")
                    self.assertEqual(os.environ["MEDIATREE_UPDATE_PLATFORM"], "windows")
                    self.assertEqual(os.environ["MEDIATREE_RUNTIME"], "windows")
                    self.assertEqual(os.environ["MEDIATREE_FRONTEND_DIR"], str((base_dir / "frontend" / "dist").resolve()))
                    self.assertEqual(fake_app.__path__, [str(base_dir.resolve() / "app")])
                    self.assertTrue(os.environ["PATH"].startswith(str(bin_dir.resolve())))
                    self.assertNotEqual(os.environ.get("PATH", ""), original_path)
                finally:
                    if original_app is None:
                        sys.modules.pop("app", None)
                    else:
                        sys.modules["app"] = original_app

        self.assertEqual(choice.source, "base")

    def test_default_base_dir_uses_pyinstaller_internal_base_when_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe_path = root / "mediatree-server.exe"
            exe_path.write_text("", encoding="utf-8")
            internal_base = root / "_internal" / "base"
            internal_base.mkdir(parents=True)

            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(exe_path)):
                self.assertEqual(windows_runtime.default_base_dir(), internal_base.resolve())

    def test_default_base_dir_keeps_legacy_sibling_base_fallback_when_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe_path = root / "mediatree-server.exe"
            exe_path.write_text("", encoding="utf-8")

            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(exe_path)):
                self.assertEqual(windows_runtime.default_base_dir(), (root / "base").resolve())


if __name__ == "__main__":
    unittest.main()
