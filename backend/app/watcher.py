import asyncio
from pathlib import Path

from watchfiles import awatch

from .config import settings, logger
from .database import get_all_library_settings
from .scanner import run_scan_for_root


_MAX_CONCURRENT_SCANS = 3
_active_scans: set[asyncio.Task] = set()

def _track_scan_task(task: asyncio.Task):
    _active_scans.add(task)
    task.add_done_callback(_active_scans.discard)

WATCH_EXTS = {
    ".mkv", ".mp4", ".mov", ".avi", ".m2ts", ".ts", ".webm",
    ".nfo", ".srt", ".ass", ".ssa", ".vtt",
    ".jpg", ".jpeg", ".png", ".webp",
}


def _is_relative_to(path: Path, root: str) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_relevant_path(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    return path.suffix.lower() in WATCH_EXTS


async def _enabled_media_roots() -> list[str]:
    configured = [str(Path(r)) for r in settings.get_all_media_roots()]
    try:
        settings_rows = await get_all_library_settings()
    except Exception as e:
        logger.warning(f"Watcher could not load library settings, falling back to configured roots: {e}")
        return [r for r in configured if Path(r).exists()]

    if not settings_rows:
        return [r for r in configured if Path(r).exists()]

    enabled = {
        str(Path(row["media_root"]))
        for row in settings_rows
        if int(row.get("enabled", 1)) == 1
    }
    return [r for r in configured if r in enabled and Path(r).exists()]


async def start_file_watcher(startup_task: asyncio.Task | None = None):
    await asyncio.sleep(1)
    if startup_task:
        try:
            await startup_task
        except Exception as e:
            logger.warning(f"Watcher ignored startup scan error: {e}")

    while True:
        roots = await _enabled_media_roots()
        if not roots:
            logger.info("No enabled media roots to watch")
            await asyncio.sleep(30)
            continue

        logger.info(f"File watcher started on {len(roots)} enabled roots")
        try:
            iterator = awatch(*roots, debounce=15000).__aiter__()
            changes_task = asyncio.create_task(iterator.__anext__())
            while True:
                done, _pending = await asyncio.wait({changes_task}, timeout=60)
                if not done:
                    latest_roots = await _enabled_media_roots()
                    if latest_roots != roots:
                        logger.info("Watcher media roots changed, refreshing watch targets")
                        changes_task.cancel()
                        try:
                            await changes_task
                        except BaseException:
                            pass
                        break
                    continue
                try:
                    changes = changes_task.result()
                except StopAsyncIteration:
                    break
                changes_task = asyncio.create_task(iterator.__anext__())

                relevant_paths = [Path(path_str) for _change_type, path_str in changes if _is_relevant_path(Path(path_str))]
                if not relevant_paths:
                    continue

                affected: set[str] = set()
                for p in relevant_paths:
                    for root in roots:
                        if _is_relative_to(p, root):
                            affected.add(root)
                            break

                if not affected:
                    continue

                logger.info(
                    f"Watcher detected changes: paths={len(relevant_paths)} roots={len(affected)}"
                )
                for root in sorted(affected):
                    pending = len(_active_scans)
                    if pending >= _MAX_CONCURRENT_SCANS:
                        logger.warning(f"Watcher throttled: {pending} scans already in progress, skipping {root}")
                        continue
                    logger.info(f"Watcher triggering auto scan for {root}")
                    t = asyncio.create_task(run_scan_for_root(root, trigger="watcher"))
                    _track_scan_task(t)

                latest_roots = await _enabled_media_roots()
                if latest_roots != roots:
                    logger.info("Watcher media roots changed after event, refreshing watch targets")
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Watcher error: {e}")
            await asyncio.sleep(30)
