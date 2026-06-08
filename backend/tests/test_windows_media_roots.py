import tempfile
import unittest
from pathlib import Path

from app.config import Settings


class WindowsMediaRootsTest(unittest.TestCase):
    def test_extra_media_roots_are_available_alongside_child_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "media"
            child = base / "Movies"
            extra = root / "External Library"
            child.mkdir(parents=True)
            extra.mkdir()

            settings = Settings(media_root=str(base), extra_media_roots=[str(extra)])
            self.assertEqual(settings.get_all_media_roots(), [str(extra.resolve()), str(child.resolve())])

    def test_extra_media_roots_skip_missing_paths_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "media"
            child = base / "Movies"
            child.mkdir(parents=True)

            settings = Settings(
                media_root=str(base),
                extra_media_roots=[str(child), str(root / "missing")],
            )

            self.assertEqual(settings.get_all_media_roots(), [str(child.resolve())])

    def test_persisted_config_round_trips_extra_media_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            extra = root / "Library"
            extra.mkdir()
            settings = Settings(data_dir=str(data), extra_media_roots=[str(extra)])

            settings.save_config()
            reloaded = Settings(data_dir=str(data))
            reloaded.load_persisted_config()

        self.assertEqual(reloaded.extra_media_roots, [str(extra)])


if __name__ == "__main__":
    unittest.main()
