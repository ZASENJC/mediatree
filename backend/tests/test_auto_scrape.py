import asyncio
import tempfile
import unittest
from pathlib import Path

from app.auto_scrape import (
    AutoScrapeScheduler,
    affected_media_roots_for_changes,
    affected_media_roots_for_paths,
    is_auto_scrape_relevant_change,
    is_auto_scrape_relevant_path,
    resolve_watch_force_polling,
    resolve_watch_poll_delay_ms,
)


class AutoScrapePathPolicyTest(unittest.TestCase):
    def test_relevant_paths_include_media_and_metadata_files(self):
        for name in ("Movie.mkv", "movie.nfo", "subtitle.ass", "poster.jpg"):
            self.assertTrue(is_auto_scrape_relevant_path(name))

    def test_relevant_paths_ignore_hidden_and_unrelated_files(self):
        for name in (".DS_Store", ".hidden.mkv", "notes.txt", "cache.tmp"):
            self.assertFalse(is_auto_scrape_relevant_path(name))

    def test_existing_directory_paths_are_relevant(self):
        with tempfile.TemporaryDirectory() as tmp:
            season_dir = Path(tmp) / "Show.Name.2024" / "Season 01"
            season_dir.mkdir(parents=True)

            self.assertTrue(is_auto_scrape_relevant_path(season_dir))

    def test_added_or_deleted_paths_trigger_as_folder_structure_changes(self):
        self.assertTrue(is_auto_scrape_relevant_change("added", "/media/movies/Movie.Name.2024"))
        self.assertTrue(is_auto_scrape_relevant_change("deleted", "/media/movies/Old Folder"))
        self.assertFalse(is_auto_scrape_relevant_change("modified", "/media/movies/notes.txt"))

    def test_affected_roots_only_include_roots_with_relevant_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root_a = base / "movies"
            root_b = base / "anime"
            outside = base / "outside"
            for p in (root_a, root_b, outside):
                p.mkdir()

            changed = [
                root_a / "New Movie" / "Movie.mkv",
                root_b / "notes.txt",
                outside / "Other.mkv",
            ]

            affected = affected_media_roots_for_paths(changed, [str(root_a), str(root_b)])

            self.assertEqual(affected, [str(root_a)])

    def test_affected_roots_include_folder_structure_changes_without_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root_a = base / "movies"
            root_b = base / "anime"
            for p in (root_a, root_b):
                p.mkdir()

            changes = [
                ("added", root_a / "Movie.Name.2024"),
                ("deleted", root_b / "Old Season"),
            ]

            affected = affected_media_roots_for_changes(changes, [str(root_a), str(root_b)])

            self.assertEqual(affected, [str(root_a), str(root_b)])

    def test_watchfiles_polling_defaults_to_container_safe_mode(self):
        self.assertTrue(resolve_watch_force_polling(None, in_container=True))
        self.assertIsNone(resolve_watch_force_polling(None, in_container=False))

    def test_watchfiles_polling_env_override(self):
        self.assertTrue(resolve_watch_force_polling("true", in_container=False))
        self.assertFalse(resolve_watch_force_polling("false", in_container=True))
        self.assertIsNone(resolve_watch_force_polling("auto", in_container=True))

    def test_watchfiles_poll_delay_uses_safe_default_and_env_override(self):
        self.assertEqual(resolve_watch_poll_delay_ms(None), 1000)
        self.assertEqual(resolve_watch_poll_delay_ms("2500"), 2500)
        self.assertEqual(resolve_watch_poll_delay_ms("0"), 1000)
        self.assertEqual(resolve_watch_poll_delay_ms("bad"), 1000)


class AutoScrapeSchedulerTest(unittest.TestCase):
    def test_scheduler_starts_one_task_per_affected_root(self):
        calls = []

        async def fake_scan(root: str, trigger: str):
            calls.append((root, trigger))
            return {"media_root": root}

        async def run():
            scheduler = AutoScrapeScheduler(max_concurrent=3)
            scheduler.schedule_roots(["/media/a", "/media/a", "/media/b"], fake_scan, trigger="watcher")
            await asyncio.sleep(0)

        asyncio.run(run())

        self.assertEqual(calls, [("/media/a", "watcher"), ("/media/b", "watcher")])

    def test_scheduler_respects_concurrency_limit(self):
        calls = []

        async def fake_scan(root: str, trigger: str):
            calls.append((root, trigger))
            await asyncio.Event().wait()

        async def run():
            scheduler = AutoScrapeScheduler(max_concurrent=1)
            scheduled = scheduler.schedule_roots(["/media/a", "/media/b"], fake_scan, trigger="watcher")
            await asyncio.sleep(0)
            for task in scheduled:
                task.cancel()
            await asyncio.gather(*scheduled, return_exceptions=True)

        asyncio.run(run())

        self.assertEqual(calls, [("/media/a", "watcher")])


if __name__ == "__main__":
    unittest.main()
