import asyncio
import os
from pathlib import Path

from watchfiles import awatch

from .config import settings, logger
from .database import get_all_library_settings
from .auto_scrape import (
    AutoScrapeScheduler,
    affected_media_roots_for_changes,
    is_auto_scrape_relevant_change,
    resolve_watch_force_polling,
    resolve_watch_poll_delay_ms,
)


_auto_scrape_scheduler = AutoScrapeScheduler()


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

        force_polling = resolve_watch_force_polling(
            os.environ.get("FILE_WATCHER_FORCE_POLLING"),
            in_container=Path("/.dockerenv").exists(),
        )
        poll_delay_ms = resolve_watch_poll_delay_ms(os.environ.get("FILE_WATCHER_POLL_DELAY_MS"))
        backend = "polling" if force_polling else ("auto" if force_polling is None else "native")
        logger.info(
            f"File watcher started on {len(roots)} enabled roots "
            f"backend={backend} poll_delay_ms={poll_delay_ms}"
        )
        try:
            iterator = awatch(
                *roots,
                debounce=15000,
                force_polling=force_polling,
                poll_delay_ms=poll_delay_ms,
            ).__aiter__()
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
                            logger.info(f"Watcher triggering initial scan for new root {r}")
                            _auto_scrape_scheduler.schedule_roots([r], trigger="watcher")
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

                relevant_changes = [
                    (change_type, Path(path_str))
                    for change_type, path_str in changes
                    if is_auto_scrape_relevant_change(change_type, Path(path_str))
                ]
                if not relevant_changes:
                    continue

                affected = affected_media_roots_for_changes(relevant_changes, roots)
                if not affected:
                    continue

                logger.info(
                    f"Watcher detected changes: paths={len(relevant_changes)} roots={len(affected)}"
                )
                _auto_scrape_scheduler.schedule_roots(affected, trigger="watcher")

                latest_roots = await _enabled_media_roots()
                if latest_roots != roots:
                    logger.info("Watcher media roots changed after event, refreshing watch targets")
                    new = [r for r in latest_roots if r not in set(roots)]
                    for r in sorted(new):
                        logger.info(f"Watcher triggering initial scan for new root {r}")
                        _auto_scrape_scheduler.schedule_roots([r], trigger="watcher")
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Watcher error: {e}")
            await asyncio.sleep(30)
