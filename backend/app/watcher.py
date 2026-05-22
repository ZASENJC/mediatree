import asyncio
import time
from pathlib import Path

from watchfiles import awatch

from .config import settings, logger
from .database import get_all_library_settings
from .scanner import run_scan_for_root


_POLL_INTERVAL_SECONDS = 300  # poll all roots every 5 minutes as inotify fallback
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

    existing_paths = {str(Path(row["media_root"])) for row in settings_rows}

    # Auto-register library_settings for newly discovered filesystem roots
    from .database import save_library_settings
    new_roots = [r for r in configured if r not in existing_paths and Path(r).exists()]
    if new_roots:
        for root in new_roots:
            await save_library_settings({
                "media_root": root,
                "scraper": "auto",
                "enabled": 1,
            })
            existing_paths.add(root)
            logger.info(f"Watcher auto-registered new media root: {root}")

    enabled = {
        str(Path(row["media_root"]))
        for row in settings_rows
        if int(row.get("enabled", 1)) == 1
    } | {r for r in new_roots}  # include newly registered roots
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
        last_poll = time.monotonic()
        try:
            iterator = awatch(*roots, debounce=15000).__aiter__()
            changes_task = asyncio.create_task(iterator.__anext__())
            while True:
                done, _pending = await asyncio.wait({changes_task}, timeout=60)
                if not done:
                    latest_roots = await _enabled_media_roots()
                    if latest_roots != roots:
                        logger.info("Watcher media roots changed, refreshing watch targets")
                        # Trigger initial scan for newly discovered roots
                        new = [r for r in latest_roots if r not in set(roots)]
                        for r in sorted(new):
                            if len(_active_scans) < _MAX_CONCURRENT_SCANS:
                                logger.info(f"Watcher triggering initial scan for new root {r}")
                                t = asyncio.create_task(run_scan_for_root(r, trigger="watcher"))
                                _track_scan_task(t)
                        changes_task.cancel()
                        try:
                            await changes_task
                        except BaseException:
                            pass
                        break

                    # Polling fallback: periodic scan when inotify doesn't fire
                    # (e.g. Docker bind mounts on macOS)
                    if time.monotonic() - last_poll >= _POLL_INTERVAL_SECONDS:
                        last_poll = time.monotonic()
                        for r in sorted(latest_roots):
                            if len(_active_scans) < _MAX_CONCURRENT_SCANS:
                                logger.info(f"Watcher polling scan for {r}")
                                t = asyncio.create_task(run_scan_for_root(r, trigger="watcher"))
                                _track_scan_task(t)
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
                    new = [r for r in latest_roots if r not in set(roots)]
                    for r in sorted(new):
                        if len(_active_scans) < _MAX_CONCURRENT_SCANS:
                            logger.info(f"Watcher triggering initial scan for new root {r}")
                            t = asyncio.create_task(run_scan_for_root(r, trigger="watcher"))
                            _track_scan_task(t)
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Watcher error: {e}")
            await asyncio.sleep(30)
