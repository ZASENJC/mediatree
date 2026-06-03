import asyncio
import tempfile
import unittest
from pathlib import Path

from app.auto_scrape import (
    AutoScrapeScheduler,
    affected_media_roots_for_paths,
    is_auto_scrape_relevant_path,
)


class AutoScrapePathPolicyTest(unittest.TestCase):
    def test_relevant_paths_include_media_and_metadata_files(self):
        for name in ("Movie.mkv", "movie.nfo", "subtitle.ass", "poster.jpg"):
            self.assertTrue(is_auto_scrape_relevant_path(name))

    def test_relevant_paths_ignore_hidden_and_unrelated_files(self):
        for name in (".DS_Store", ".hidden.mkv", "notes.txt", "cache.tmp"):
            self.assertFalse(is_auto_scrape_relevant_path(name))

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
