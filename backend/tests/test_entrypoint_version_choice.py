import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class EntrypointVersionChoiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.base_dir = self.root / "base"
        self.releases_dir = self.root / "data" / "releases"
        self.base_dir.mkdir(parents=True)
        self.releases_dir.mkdir(parents=True)
        self.entrypoint = Path(__file__).resolve().parents[2] / "docker" / "entrypoint.sh"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_app_dir(self, path: Path, version: str) -> None:
        (path / "app").mkdir(parents=True)
        (path / "frontend" / "dist").mkdir(parents=True)
        (path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
        (path / "frontend" / "dist" / "index.html").write_text("<html></html>\n", encoding="utf-8")
        (path / "VERSION").write_text(f"{version}\n", encoding="utf-8")

    def _choose(self) -> str:
        env = os.environ.copy()
        env.update({
            "MEDIATREE_BASE_DIR": str(self.base_dir),
            "DATA_DIR": str(self.root / "data"),
            "MEDIATREE_ENTRYPOINT_PRINT_CHOICE": "1",
        })
        result = subprocess.run(
            ["sh", str(self.entrypoint)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_prefers_newer_base_over_outdated_app_package(self):
        self._make_app_dir(self.base_dir, "1.0.04")
        current_dir = self.releases_dir / "1.0.03"
        self._make_app_dir(current_dir, "1.0.03")
        (self.releases_dir / "current").write_text("1.0.03\n", encoding="utf-8")

        choice = self._choose()

        self.assertEqual(choice, f"{self.base_dir}|base")

    def test_prefers_newer_app_package_over_older_base(self):
        self._make_app_dir(self.base_dir, "1.0.04")
        current_dir = self.releases_dir / "1.0.05"
        self._make_app_dir(current_dir, "1.0.05")
        (self.releases_dir / "current").write_text("1.0.05\n", encoding="utf-8")

        choice = self._choose()

        self.assertEqual(choice, f"{current_dir}|app-package")


if __name__ == "__main__":
    unittest.main()
