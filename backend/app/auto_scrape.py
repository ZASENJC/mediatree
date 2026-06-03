import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Iterable

from .config import logger
from .scanner import run_scan_for_root


AUTO_SCRAPE_EXTS = {
    ".mkv", ".mp4", ".mov", ".avi", ".m2ts", ".ts", ".webm",
    ".nfo", ".srt", ".ass", ".ssa", ".vtt",
    ".jpg", ".jpeg", ".png", ".webp",
}
MAX_CONCURRENT_AUTO_SCRAPES = 3

ScanRunner = Callable[[str, str], Awaitable[dict]]


def is_auto_scrape_relevant_path(path: str | Path) -> bool:
    p = Path(path)
    if p.name.startswith("."):
        return False
    return p.suffix.lower() in AUTO_SCRAPE_EXTS


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def affected_media_roots_for_paths(paths: Iterable[str | Path], roots: Iterable[str]) -> list[str]:
    relevant_paths = [Path(p) for p in paths if is_auto_scrape_relevant_path(p)]
    affected: list[str] = []
    for root in roots:
        root_path = Path(root)
        if any(_is_relative_to(path, root_path) for path in relevant_paths):
            affected.append(str(root_path))
    return affected


class AutoScrapeScheduler:
    def __init__(self, max_concurrent: int = MAX_CONCURRENT_AUTO_SCRAPES):
        self.max_concurrent = max(1, int(max_concurrent or MAX_CONCURRENT_AUTO_SCRAPES))
        self._active_tasks: set[asyncio.Task] = set()

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    def _track_task(self, task: asyncio.Task):
        self._active_tasks.add(task)
        task.add_done_callback(self._complete_task)

    def _complete_task(self, task: asyncio.Task):
        self._active_tasks.discard(task)
        if task.cancelled():
            return
        try:
            exc = task.exception()
        except Exception as e:
            logger.warning(f"Auto scrape task state check failed: {e}")
            return
        if exc:
            logger.warning(f"Auto scrape task failed: {exc}")

    def schedule_roots(
        self,
        roots: Iterable[str],
        runner: ScanRunner = run_scan_for_root,
        *,
        trigger: str = "watcher",
    ) -> list[asyncio.Task]:
        scheduled: list[asyncio.Task] = []
        seen: set[str] = set()
        for root in roots:
            if root in seen:
                continue
            seen.add(root)
            pending = self.active_count
            if pending >= self.max_concurrent:
                logger.warning(
                    f"Auto scrape throttled: {pending} scans already in progress, skipping {root}"
                )
                continue
            logger.info(f"Auto scrape scheduling scan for {root} trigger={trigger}")
            task = asyncio.create_task(runner(root, trigger))
            self._track_task(task)
            scheduled.append(task)
        return scheduled
