import asyncio
from pathlib import Path
from watchfiles import awatch
from .config import settings, logger
from .scanner import scan_media, scrape_for_library
from .database import upsert_movie, get_db


async def start_file_watcher(startup_task: asyncio.Task | None = None):
    if startup_task:
        await startup_task

    roots = settings.get_all_media_roots()
    if not roots:
        logger.info("No media roots to watch")
        return
    logger.info(f"File watcher started on {len(roots)} roots")

    while True:
        try:
            async for changes in awatch(*roots, debounce=15000):
                affected: set[str] = set()
                for _change_type, path_str in changes:
                    p = Path(path_str)
                    for root in roots:
                        if p.is_relative_to(root):
                            affected.add(root)
                            break

                for root in affected:
                    logger.info(f"Auto-scan triggered for {root}")
                    results = scan_media(root)
                    for item in results:
                        await upsert_movie(item)
                    await _cleanup_deleted(root)
                    await scrape_for_library(root)

        except Exception as e:
            logger.error(f"Watcher error: {e}")
            await asyncio.sleep(30)


async def _cleanup_deleted(media_root: str):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, path FROM movies WHERE media_root=?", (media_root,)
    )
    removed = 0
    for row in await cur.fetchall():
        if not Path(row["path"]).exists():
            await db.execute("DELETE FROM movies WHERE id=?", (row["id"],))
            removed += 1
    if removed:
        await db.commit()
        logger.info(f"Auto-scan: removed {removed} deleted files from {media_root}")
