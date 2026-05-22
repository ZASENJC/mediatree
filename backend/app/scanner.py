import re
import os
import json
import hashlib
import asyncio
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime
from .config import settings
from .anime_naming import parse_anime_filename
from .scrapers.base import ScrapeCandidate, ScrapeResult, ScrapeStaff
from .scrapers.registry import get_scraper
from .scrapers.utils import scrape_result_to_legacy, _candidate_to_dict
from .scrapers.tmdb_scraper import tmdb_title_search
from .title_match import (
    TmdbIdToken, CODE_PATTERN, CODE_PATTERN_UNDERSCORE,
    extract_code, extract_tmdb_token_from_name, extract_tmdb_ref,
    extract_tmdb_id_from_name, remove_tmdb_id_token,
    clean_folder_name, generate_folder_identifier,
    extract_cjk, extract_alpha, extract_romaji,
    title_matches, candidate_title_matches,
    _is_specific_search_query, _first_tmdb_token,
    build_search_queries, clean_search_title,
    is_season_folder, infer_season_number,
    has_local_data, has_complete_scraped_data,
    infer_tmdb_media_type,
    EPISODE_HINT_PATTERN, SEASON_HINT_PATTERN, DISC_HINT_PATTERN,
    YEAR_HINT_PATTERN, SEASON_PATTERN,
    VIDEO_EXTS,
)

_scan_progress: dict[str, dict] = {}
_scan_locks: dict[str, asyncio.Lock] = {}
_scan_pending: set[str] = set()
_global_scrape_semaphore: asyncio.Semaphore | None = None
_global_scrape_limit = 0
_sqlite_write_semaphore = asyncio.Semaphore(1)


def _bounded_int(value, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _get_global_scrape_semaphore() -> asyncio.Semaphore:
    global _global_scrape_semaphore, _global_scrape_limit
    limit = _bounded_int(settings.scrape_global_concurrency, 8)
    if _global_scrape_semaphore is None or _global_scrape_limit != limit:
        _global_scrape_semaphore = asyncio.Semaphore(limit)
        _global_scrape_limit = limit
    return _global_scrape_semaphore


def _set_scan_progress(media_root: str, **fields):
    current = dict(_scan_progress.get(media_root, {}))
    current.update(fields)
    current.setdefault("media_root", media_root)
    current.setdefault("done", 0)
    current.setdefault("total", 0)
    current.setdefault("success", 0)
    current.setdefault("failed", 0)
    current.setdefault("skipped", 0)
    current.setdefault("active_concurrency", 0)
    current.setdefault("trigger", current.get("trigger"))
    _scan_progress[media_root] = current


# ── File system scanning ───────────────────────────────────────────────────

COVER_NAMES = {"poster.jpg", "poster.png", "cover.jpg", "cover.png", "folder.jpg", "folder.png",
               "movie-poster.jpg", "movie-poster.png", "season-poster.jpg", "season-poster.png",
               "banner.jpg", "banner.png", "fanart.jpg", "fanart.png", "backdrop.jpg", "backdrop.png"}
NFO_NAMES = {"movie.nfo", "tvshow.nfo"}
SKIP_DIRS = {".DS_Store", "__MACOSX", "Thumbs.db", ".Trashes"}

def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")

def find_cover(folder: Path) -> str | None:
    for name in COVER_NAMES:
        p = folder / name
        if p.exists():
            return str(p)
    for f in sorted(folder.glob("*.jpg")):
        return str(f)
    for f in sorted(folder.glob("*.png")):
        return str(f)
    return None

def find_cover_recursive(folder: Path, media_root: str) -> str | None:
    current = folder
    root = Path(media_root)
    while current >= root:
        cover = find_cover(current)
        if cover:
            return cover
        if current == root:
            break
        current = current.parent
    return None

def find_nfo_file(folder: Path) -> str | None:
    for name in NFO_NAMES:
        p = folder / name
        if p.exists():
            return str(p)
    for f in sorted(folder.glob("*.nfo")):
        return str(f)
    return None

def parse_nfo(filepath: str) -> dict:
    try:
        parser = ET.XMLParser(resolve_entities=False)
        tree = ET.parse(filepath, parser=parser)
        root = tree.getroot()
    except Exception:
        return {}
    result = {"nfo_type": (root.tag or "").lower()}
    def _text(tag: str) -> str | None:
        el = root.find(tag)
        return el.text.strip() if el is not None and el.text else None
    title = _text("title")
    if title: result["title"] = title
    original_title = _text("originaltitle")
    if original_title: result["original_title"] = original_title
    plot = _text("plot")
    if plot: result["plot"] = plot
    year = _text("year")
    if year:
        try: result["year"] = int(year)
        except ValueError: pass
    premiered = _text("premiered") or _text("release_date")
    if premiered:
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", premiered)
        if date_match: result["premiered"] = date_match.group()
    rating = _text("rating")
    if rating:
        try: result["rating"] = float(rating)
        except ValueError: pass
    runtime = _text("runtime")
    if runtime:
        try: result["runtime"] = int(runtime)
        except ValueError: pass
    genres = [g.text.strip() for g in root.findall("genre") if g.text]
    if genres: result["genre"] = ", ".join(genres)
    actors = []
    for actor_el in root.findall("actor"):
        name_el = actor_el.find("name")
        if name_el is not None and name_el.text:
            actors.append(name_el.text.strip())
    if actors: result["actors"] = actors
    director = _text("director")
    if director: result["director"] = director
    studio = _text("studio")
    if studio: result["studio"] = studio
    return result

def extract_year_from_name(name: str) -> int | None:
    match = re.search(r'[\(\[](\d{4})[\)\]]', name)
    if match: return int(match.group(1))
    match = re.search(r'(?:^|[._\-\s])(\d{4})(?:[._\-\s]|$)', name.replace('1080p', '').replace('2160p', '').replace('720p', ''))
    if match:
        year = int(match.group(1))
        if 1888 <= year <= 2030: return year
    return None

def build_local_metadata(folder: Path, folder_name: str, code: str) -> dict:
    metadata: dict = {}
    nfo_path = find_nfo_file(folder)
    if nfo_path:
        nfo_data = parse_nfo(nfo_path)
        if nfo_data: metadata["nfo"] = nfo_data
    year = extract_year_from_name(folder_name)
    if year: metadata["detected_year"] = year
    return metadata

def scan_media(root: str = None) -> list[dict]:
    from .covers import find_local_episode_still
    from .subtitles import find_external_audio_tracks

    if root is None:
        roots = settings.get_all_media_roots()
    else:
        roots = [root]
    results = []
    for media_root in roots:
        base = Path(media_root)
        if not base.exists(): continue
        trigger = _scan_progress.get(media_root, {}).get("trigger")
        _set_scan_progress(media_root, status="scanning", done=0, total=0, trigger=trigger)
        for dirpath, dirnames, filenames in os.walk(base):
            folder = Path(dirpath)
            media_files = sorted({folder / f for f in filenames if Path(f).suffix.lower() in VIDEO_EXTS})
            if not media_files: continue
            detected_code = extract_code(folder.name)
            code = detected_code
            if not code and filenames:
                for f in filenames:
                    code = extract_code(Path(f).stem)
                    if code:
                        detected_code = code
                        break
            if not code:
                code = generate_folder_identifier(folder.name)
            rel_path = str(folder.relative_to(base))
            folder_levels = rel_path.replace("\\", "/")
            cover_local = find_cover_recursive(folder, media_root)
            try:
                folder_mtime = os.path.getmtime(str(folder))
            except OSError:
                folder_mtime = None
            local_meta = build_local_metadata(folder, folder.name, code)
            nfo_data = local_meta.get("nfo", {})
            title = nfo_data.get("title") or None
            release_date = nfo_data.get("premiered") or None
            duration = nfo_data.get("runtime") or None
            for mf in media_files:
                anime_info = parse_anime_filename(mf.name)
                clean_title = anime_info.clean_title or title or ""
                item_code = code
                if not detected_code and clean_title:
                    item_code = clean_title
                local_still = find_local_episode_still(str(mf))
                external_audio_tracks = find_external_audio_tracks(str(mf))
                item_meta = dict(local_meta)
                item_meta["anime_naming"] = anime_info.as_dict()
                item_meta_json = json.dumps(item_meta, ensure_ascii=False) if item_meta else "{}"
                item = {
                    "path": str(mf), "code": item_code, "title": title or clean_title or None,
                    "folder_levels": folder_levels, "cover_local": cover_local,
                    "media_root": media_root, "local_metadata": item_meta_json,
                    "clean_title": clean_title or None,
                    "episode_number": anime_info.episode,
                    "display_title": anime_info.display_title or clean_title or None,
                    "external_audio_tracks": json.dumps(external_audio_tracks, ensure_ascii=False),
                }
                if anime_info.episode is not None:
                    item["tmdb_type"] = "tv"
                    item["tmdb_season"] = 1
                    item["tmdb_episode"] = anime_info.episode
                if local_still:
                    item["episode_still"] = local_still
                    item["episode_still_local"] = local_still
                if release_date: item["release_date"] = release_date
                if duration: item["duration"] = duration
                if folder_mtime:
                    item["created_at"] = datetime.fromtimestamp(folder_mtime).strftime("%Y-%m-%d %H:%M:%S")
                results.append(item)
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        _set_scan_progress(media_root, status="scanned", done=0, total=0, trigger=trigger)
    return results

def normalize_scraper_name(scraper: str | None) -> str:
    value = (scraper or "auto").strip().lower()
    if value == "tmdb":
        return "tmdb_movie"
    if value in {"tmdb_movie", "tmdb_tv", "bangumi", "javdatabase", "auto", "none"}:
        return value
    return "auto"


def build_fallback_chain(preferred: str) -> list[str]:
    preferred = normalize_scraper_name(preferred)
    if preferred == "none":
        return []
    if preferred == "javdatabase":
        return ["javdatabase"]
    if preferred == "auto":
        return ["auto"]
    if preferred == "tmdb_movie":
        return ["tmdb_movie"]
    if preferred == "tmdb_tv":
        return ["tmdb_tv"]
    if preferred == "bangumi":
        return ["bangumi", "tmdb_tv_search", "tmdb_movie_search"]
    return ["auto"]


# ── Thin wrappers for rescrape/manual scrape compat ─────────────────────────

async def _search_scraper_candidates(scraper_name: str, query: str, media_type: str | None = None, limit: int = 10) -> list[ScrapeCandidate]:
    try:
        scraper = get_scraper(scraper_name)
        return await scraper.search(query, media_type=media_type, limit=limit)
    except Exception as e:
        from .config import logger
        logger.warning(f"  {scraper_name}: search error for '{query}': {e}")
        return []


async def _fetch_detail_legacy(
    source: str,
    source_id: str,
    media_type: str | None = None,
    *,
    exact: bool = True,
) -> dict | None:
    from .config import logger
    value = (source or "auto").strip().lower()
    if value in {"tmdb", "tmdb_movie", "tmdb_tv"}:
        scraper_name = "tmdb_tv" if media_type == "tv" or value == "tmdb_tv" else "tmdb_movie"
    else:
        scraper_name = normalize_scraper_name(value)
    try:
        scraper = get_scraper(scraper_name)
        result = await scraper.get_detail(source_id, media_type=media_type)
    except Exception as e:
        logger.warning(f"  {scraper_name}: detail error for {source_id}: {e}")
        return None
    if not result or not result.title:
        return None
    return scrape_result_to_legacy(result, exact=exact)


# ── Scraped data application ────────────────────────────────────────────────

async def _apply_scraped_data(folder_levels: str, data: dict, media_root: str = "", replace: bool = False) -> int:
    from .database import get_db
    from .config import logger
    db = await get_db()
    fields = {
        "title": data.get("title") or "",
        "original_title": data.get("original_title") or "",
        "overview": data.get("overview") or "",
        "actress": data.get("actress") or "",
        "release_date": data.get("release_date") or "",
        "duration": data.get("duration"),
        "javdb_url": data.get("javdb_url") or "",
        "javdb_score": data.get("javdb_score"),
        "javdb_likes": data.get("javdb_likes"),
        "javdb_thumbnails": data.get("javdb_thumbnails") or "",
        "cover_remote": data.get("cover_remote") or "",
        "fanart_local": data.get("backdrop_url") or data.get("fanart_local") or "",
        "tmdb_id": data.get("tmdb_id"),
        "tmdb_type": data.get("tmdb_type") or "",
        "tmdb_season": data.get("tmdb_season"),
        "tmdb_episode": data.get("tmdb_episode"),
        "episode_title": data.get("episode_title") or "",
        "episode_still": data.get("episode_still") or "",
        "scraper_source": data.get("scraper_source") or data.get("source") or "",
        "source_id": data.get("source_id") or "",
        "bangumi_id": data.get("bangumi_id") or "",
        "javdb_id": data.get("javdb_id") or "",
        "scraper_raw": data.get("scraper_raw") or (json.dumps(data.get("_raw"), ensure_ascii=False) if data.get("_raw") else ""),
        "cast": json.dumps(data.get("cast") or [], ensure_ascii=False),
        "crew": json.dumps(data.get("crew") or [], ensure_ascii=False),
    }
    if replace:
        set_sql = """
               title=NULLIF(?, ''),
               original_title=NULLIF(?, ''),
               overview=NULLIF(?, ''),
               actress=NULLIF(?, ''),
               release_date=NULLIF(?, ''),
               duration=?,
               javdb_url=NULLIF(?, ''),
               javdb_score=?,
               javdb_likes=?,
               javdb_thumbnails=NULLIF(?, ''),
               cover_remote=NULLIF(?, ''),
               fanart_local=NULLIF(?, ''),
               tmdb_id=?,
               tmdb_type=NULLIF(?, ''),
               "cast"=NULLIF(?, '[]'),
               crew=NULLIF(?, '[]'),
               scraper_source=NULLIF(?, ''),
               source_id=NULLIF(?, ''),
               bangumi_id=NULLIF(?, ''),
               javdb_id=NULLIF(?, ''),
               scraper_raw=NULLIF(?, ''),
               tmdb_season=?,
               tmdb_episode=?,
               episode_title=NULLIF(?, ''),
               episode_overview=NULL,
               episode_still=NULLIF(?, ''),
               episode_still_local=NULL,
               updated_at=datetime('now')
        """
    else:
        set_sql = """
               title=COALESCE(NULLIF(?, ''), title),
               original_title=COALESCE(NULLIF(?, ''), original_title),
               overview=COALESCE(NULLIF(?, ''), overview),
               actress=COALESCE(NULLIF(?, ''), actress),
               release_date=COALESCE(NULLIF(?, ''), release_date),
               duration=COALESCE(?, duration),
               javdb_url=COALESCE(NULLIF(?, ''), javdb_url),
               javdb_score=COALESCE(?, javdb_score),
               javdb_likes=COALESCE(?, javdb_likes),
               javdb_thumbnails=COALESCE(NULLIF(?, ''), javdb_thumbnails),
               cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
               fanart_local=COALESCE(NULLIF(?, ''), fanart_local),
               tmdb_id=COALESCE(?, tmdb_id),
               tmdb_type=COALESCE(NULLIF(?, ''), tmdb_type),
               "cast"=COALESCE(NULLIF(?, '[]'), "cast"),
               crew=COALESCE(NULLIF(?, '[]'), crew),
               scraper_source=COALESCE(NULLIF(?, ''), scraper_source),
               source_id=COALESCE(NULLIF(?, ''), source_id),
               bangumi_id=COALESCE(NULLIF(?, ''), bangumi_id),
               javdb_id=COALESCE(NULLIF(?, ''), javdb_id),
               scraper_raw=COALESCE(NULLIF(?, ''), scraper_raw),
               tmdb_season=COALESCE(?, tmdb_season),
               tmdb_episode=COALESCE(?, tmdb_episode),
               episode_title=COALESCE(NULLIF(?, ''), episode_title),
               episode_still=COALESCE(NULLIF(?, ''), episode_still),
               updated_at=datetime('now')
        """
    values = (
        fields["title"], fields["original_title"], fields["overview"],
        fields["actress"], fields["release_date"], fields["duration"],
        fields["javdb_url"], fields["javdb_score"], fields["javdb_likes"],
        fields["javdb_thumbnails"], fields["cover_remote"], fields["fanart_local"],
        fields["tmdb_id"], fields["tmdb_type"], fields["cast"], fields["crew"],
        fields["scraper_source"], fields["source_id"], fields["bangumi_id"], fields["javdb_id"],
        fields["scraper_raw"],
        fields["tmdb_season"], fields["tmdb_episode"], fields["episode_title"], fields["episode_still"],
    )
    if media_root:
        cur = await db.execute(
            f"UPDATE movies SET {set_sql} WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
            (*values, folder_levels, f"{folder_levels}/%", media_root)
        )
    else:
        cur = await db.execute(
            f"UPDATE movies SET {set_sql} WHERE (folder_levels=? OR folder_levels LIKE ?)",
            (*values, folder_levels, f"{folder_levels}/%")
        )
    affected = cur.rowcount
    logger.info(f"  _apply_scraped_data: folder='{folder_levels}' media_root='{media_root}' affected={affected} rows")

    folder_name = Path(folder_levels).name if folder_levels else ""
    if is_season_folder(folder_name) and data.get("cover_remote"):
        parent = str(Path(folder_levels).parent) if str(Path(folder_levels).parent) != "." else ""
        if parent:
            if media_root:
                await db.execute(
                    """UPDATE movies SET
                       cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
                       updated_at=datetime('now')
                       WHERE folder_levels LIKE ? AND media_root=?""",
                    (data.get("cover_remote", ""), parent + "/%", media_root)
                )
            else:
                await db.execute(
                    """UPDATE movies SET
                       cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
                       updated_at=datetime('now')
                       WHERE folder_levels LIKE ?""",
                    (data.get("cover_remote", ""), parent + "/%")
                )

    if data.get("cover_remote") or replace:
        if media_root:
            await db.execute(
                "UPDATE movies SET cover_local=NULL WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
                (folder_levels, f"{folder_levels}/%", media_root),
            )
        else:
            await db.execute(
                "UPDATE movies SET cover_local=NULL WHERE (folder_levels=? OR folder_levels LIKE ?)",
                (folder_levels, f"{folder_levels}/%"),
            )
    if data.get("cover_remote"):
        try:
            from .covers import download_and_compress_cover
            cache_key = hashlib.md5(data["cover_remote"].encode()).hexdigest()[:16]
            cached = await download_and_compress_cover(data["cover_remote"], cache_key)
            if cached:
                if media_root:
                    await db.execute(
                        "UPDATE movies SET cover_local=? WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
                        (cache_key, folder_levels, f"{folder_levels}/%", media_root),
                    )
                else:
                    await db.execute(
                        "UPDATE movies SET cover_local=? WHERE (folder_levels=? OR folder_levels LIKE ?)",
                        (cache_key, folder_levels, f"{folder_levels}/%"),
                    )
        except Exception:
            pass

    await db.commit()
    return affected

def is_season_folder(name: str) -> bool:
    return bool(SEASON_PATTERN.match(name))


def infer_season_number(folder_name: str, data: dict) -> int | None:
    if is_season_folder(folder_name):
        match = re.search(r'\d+', folder_name)
        if match:
            return int(match.group())
    if data.get("tmdb_type") == "tv":
        seasons = data.get("seasons") or []
        numbered = [
            s.get("season_number") for s in seasons
            if isinstance(s, dict) and isinstance(s.get("season_number"), int) and s.get("season_number") > 0
        ]
        if len(numbered) == 1:
            return numbered[0]
        return 1
    return None

async def scrape_for_library(media_root: str):
    from .database import get_library_settings, get_db
    from .config import logger

    lib_setting = await get_library_settings(media_root)
    scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
    trigger = _scan_progress.get(media_root, {}).get("trigger")
    if scraper == "none":
        logger.info(f"Scraping disabled for {media_root}")
        _set_scan_progress(media_root, status="disabled", done=0, total=0, trigger=trigger)
        return

    chain = build_fallback_chain(scraper)
    logger.info(f"Scraping {media_root}: scraper={normalize_scraper_name(scraper)} chain={' → '.join(chain)}")

    db = await get_db()
    cur = await db.execute(
        """SELECT DISTINCT id, code, folder_levels, path, title, cover_local, cover_remote,
                  javdb_url, local_metadata, tmdb_id, tmdb_type, tmdb_season, tmdb_episode,
                  clean_title, episode_number, display_title, source_id, bangumi_id, javdb_id
           FROM movies WHERE media_root=?""",
        (media_root,)
    )
    rows = await cur.fetchall()
    if not rows:
        _set_scan_progress(media_root, status="done", done=0, total=0, trigger=trigger)
        return

    folder_rows: list[dict] = []
    seen_folders = set()
    for r in rows:
        folder_levels = r["folder_levels"] or ""
        if not folder_levels or folder_levels in seen_folders:
            continue
        seen_folders.add(folder_levels)
        folder_rows.append(dict(r))

    total_folders = len(folder_rows)
    if not total_folders:
        _set_scan_progress(media_root, status="done", done=0, total=0, trigger=trigger)
        return

    per_library_limit = _bounded_int(settings.scrape_concurrency_per_library, 4)
    per_library_sem = asyncio.Semaphore(per_library_limit)
    global_sem = _get_global_scrape_semaphore()
    done_count = 0
    success_count = 0
    failed_count = 0
    skipped_count = 0
    active_count = 0
    progress_lock = asyncio.Lock()

    _set_scan_progress(
        media_root,
        status="scraping",
        done=0,
        total=total_folders,
        success=0,
        failed=0,
        skipped=0,
        active_concurrency=0,
        trigger=trigger,
        per_library_concurrency=per_library_limit,
        global_concurrency=_global_scrape_limit,
    )

    async def process_folder(r: dict):
        nonlocal done_count, success_count, failed_count, skipped_count, active_count
        folder_levels = r.get("folder_levels") or ""
        folder_name = Path(folder_levels).name if folder_levels else ""
        code = r.get("code") or ""
        movie_path = r.get("path") or ""
        row_clean_title = (r.get("clean_title") or "").strip()

        if not folder_name:
            async with progress_lock:
                skipped_count += 1
                done_count += 1
                _set_scan_progress(media_root, done=done_count, skipped=skipped_count)
            return

        if has_local_data(r):
            logger.info(f"  Skip (local data exists): {folder_name}")
            async with progress_lock:
                skipped_count += 1
                done_count += 1
                _set_scan_progress(media_root, done=done_count, skipped=skipped_count)
            return

        if has_complete_scraped_data(r):
            logger.info(f"  Skip (complete scraped data exists): {folder_name}")
            async with progress_lock:
                skipped_count += 1
                done_count += 1
                _set_scan_progress(media_root, done=done_count, skipped=skipped_count)
            return

        # 使用源文件夹名进行搜索（参考 Jellyfin 刮削逻辑），而非视频文件名
        search_name = folder_name
        search_levels = folder_levels
        if is_season_folder(folder_name):
            parent = Path(folder_levels).parent
            parent_name = parent.name if str(parent) != "." else ""
            if parent_name:
                search_name = parent_name
                search_levels = str(parent)

        if search_levels != folder_levels:
            logger.info(f"  Season folder detected: '{folder_name}' → searching as '{search_name}'")

        candidate_names = [
            row_clean_title,
            folder_name,
            Path(folder_levels).parent.name if folder_levels and str(Path(folder_levels).parent) != "." else "",
            Path(movie_path).stem if movie_path else "",
            r.get("title") or "",
            r.get("display_title") or "",
            code,
            search_name,
        ]
        clean_title_for_log = clean_search_title(search_name, candidate_names)
        token_for_log = _first_tmdb_token(candidate_names)
        logger.info(
            f"Scrape item: media_root='{media_root}' movie_id={r.get('id') or ''} "
            f"scraper='{normalize_scraper_name(scraper)}' raw_title='{search_name}' "
            f"clean_title='{clean_title_for_log}' tmdb_token={'yes' if token_for_log else 'no'} "
            f"tmdb_id='{r.get('tmdb_id') or ''}'"
        )

        scraped = False
        async with per_library_sem:
            async with global_sem:
                async with progress_lock:
                    active_count += 1
                    _set_scan_progress(media_root, active_concurrency=active_count)
                try:
                    for sb in chain:
                        try:
                            if sb == "tmdb_tv_search":
                                clean_title = clean_search_title(search_name, candidate_names)
                                data = await tmdb_title_search(clean_title, search_name, code, "tv")
                            elif sb == "tmdb_movie_search":
                                clean_title = clean_search_title(search_name, candidate_names)
                                data = await tmdb_title_search(clean_title, search_name, code, "movie")
                            else:
                                scraper_obj = get_scraper(sb)
                                if sb == "javdatabase":
                                    data = await scraper_obj.full_scrape(search_name, code=code)
                                else:
                                    data = await scraper_obj.full_scrape(search_name, code=code, candidate_names=candidate_names, movie=r)
                            if not data or not data.get("title"):
                                logger.info(f"  {sb}: no result for '{search_name}'")
                                continue
                            if sb in {"javdatabase", "auto"} and data.get("_exact_match"):
                                passed = True
                            elif sb == "javdatabase":
                                passed = True
                            else:
                                passed = (
                                    bool(data.get("_exact_match"))
                                    or bool(data.get("_search_match_passed"))
                                    or title_matches(data.get("title", ""), search_name, code)
                                    or title_matches(data.get("original_title", ""), search_name, code)
                                )
                            if passed:
                                async with _sqlite_write_semaphore:
                                    await _apply_scraped_data(folder_levels, data, media_root)
                                logger.info(
                                    f"  {sb}: applied source='{data.get('source') or data.get('scraper_source') or sb}' "
                                    f"source_id='{data.get('source_id') or data.get('tmdb_id') or data.get('bangumi_id') or data.get('javdb_id') or ''}' "
                                    f"clean_title='{clean_title_for_log}' title='{data.get('title', search_name)}'"
                                )

                                if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                                    season_num = infer_season_number(folder_name, data)
                                    if season_num:
                                        try:
                                            from .tmdb import match_episodes_in_folder
                                            async with _sqlite_write_semaphore:
                                                matched = await match_episodes_in_folder(
                                                    str(data["tmdb_id"]), season_num, folder_levels, media_root
                                                )
                                            if matched:
                                                logger.info(f"  TMDB: matched {matched} episodes in '{folder_levels}'")
                                        except Exception as e:
                                            logger.warning(f"  TMDB: episode matching error: {e}")

                                scraped = True
                                break
                            logger.info(f"  {sb}: title mismatch '{data.get('title', '')}' vs '{search_name}', trying fallback")
                        except Exception:
                            logger.exception(
                                f"  {sb}: error for media_root='{media_root}' folder='{folder_name}' "
                                f"cleaned_title='{search_name}'"
                            )
                finally:
                    async with progress_lock:
                        active_count -= 1
                        _set_scan_progress(media_root, active_concurrency=active_count)

        async with progress_lock:
            if scraped:
                success_count += 1
            else:
                failed_count += 1
                logger.info(f"  All scrapers failed for '{search_name}'")
            done_count += 1
            _set_scan_progress(
                media_root,
                done=done_count,
                success=success_count,
                failed=failed_count,
                skipped=skipped_count,
            )

    results = await asyncio.gather(*(process_folder(row) for row in folder_rows), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Scrape task failed for {media_root}: {result}")
            failed_count += 1

    _set_scan_progress(
        media_root,
        status="done",
        done=total_folders,
        total=total_folders,
        success=success_count,
        failed=failed_count,
        skipped=skipped_count,
        active_concurrency=0,
        trigger=trigger,
    )


def _scan_lock_for(media_root: str) -> asyncio.Lock:
    lock = _scan_locks.get(media_root)
    if lock is None:
        lock = asyncio.Lock()
        _scan_locks[media_root] = lock
    return lock


async def cleanup_deleted_files(media_root: str) -> int:
    from .database import get_db
    from .config import logger
    db = await get_db()
    cur = await db.execute("SELECT id, path FROM movies WHERE media_root=?", (media_root,))
    removed = 0
    for row in await cur.fetchall():
        if not Path(row["path"]).exists():
            await db.execute("DELETE FROM movies WHERE id=?", (row["id"],))
            removed += 1
    if removed:
        await db.commit()
        logger.info(f"Scan cleanup: removed {removed} deleted files from {media_root}")
    return removed


async def run_scan_for_root(media_root: str, trigger: str = "manual") -> dict:
    from .database import upsert_movie
    from .config import logger
    lock = _scan_lock_for(media_root)
    if lock.locked():
        _scan_pending.add(media_root)
        logger.info(f"Scan skipped/queued for {media_root}: another scan is already running")
        return {"media_root": media_root, "queued": True, "trigger": trigger}

    total_results = 0
    removed_total = 0
    runs = 0
    async with lock:
        while True:
            _scan_pending.discard(media_root)
            runs += 1
            _set_scan_progress(
                media_root,
                status="scanning",
                done=0,
                total=0,
                success=0,
                failed=0,
                skipped=0,
                active_concurrency=0,
                trigger=trigger,
            )
            logger.info(f"Scan started for {media_root} trigger={trigger}")
            results = await asyncio.to_thread(scan_media, root=media_root)
            for item in results:
                async with _sqlite_write_semaphore:
                    await upsert_movie(item)
            async with _sqlite_write_semaphore:
                removed_total += await cleanup_deleted_files(media_root)
            total_results += len(results)
            _set_scan_progress(media_root, status="scraping", done=0, total=0, trigger=trigger)
            await scrape_for_library(media_root)
            logger.info(f"Scan and scrape complete for {media_root} trigger={trigger} files={len(results)}")
            if media_root not in _scan_pending:
                break
            logger.info(f"Queued changes detected during scan for {media_root}; running one follow-up scan")
            trigger = "queued"

    return {
        "media_root": media_root,
        "queued": False,
        "trigger": trigger,
        "runs": runs,
        "total": total_results,
        "removed": removed_total,
    }


async def clear_library_scraped_data(media_root: str):
    from .database import get_db
    from .config import logger

    if not media_root:
        logger.warning("clear_library_scraped_data rejected: media_root is required")
        raise ValueError("media_root required")

    db = await get_db()
    cur = await db.execute(
        """UPDATE movies SET title=NULL, actress=NULL, release_date=NULL,
           duration=NULL, cover_local=NULL, cover_remote=NULL, fanart_local=NULL,
           javdb_url=NULL, javdb_score=NULL, javdb_likes=NULL, javdb_thumbnails=NULL,
           tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
           scraper_source=NULL, source_id=NULL, bangumi_id=NULL, javdb_id=NULL,
           original_title=NULL, overview=NULL, scraper_raw=NULL,
           episode_title=NULL, episode_overview=NULL, episode_still=NULL, episode_still_local=NULL,
           "cast"='[]', crew='[]',
           updated_at=datetime('now')
           WHERE media_root=?""",
        (media_root,)
    )
    await db.commit()

    affected = cur.rowcount if cur.rowcount is not None else 0
    logger.info(
        f"Cleared scraped fields for media_root='{media_root}', affected={affected}; "
        "scraper_cache/javdb_cache and other media roots preserved"
    )


async def rescrape_movie(movie_id: int) -> dict:
    from .database import get_db, get_library_settings
    from .config import logger

    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "Movie not found"}

    movie = dict(row)
    folder_levels = movie.get("folder_levels", "")
    folder_name = Path(folder_levels).name if folder_levels else ""
    code = movie.get("code", "")
    media_root = movie.get("media_root", "")

    if not folder_name:
        return {"ok": False, "error": "No folder name"}

    lib_setting = await get_library_settings(media_root)
    scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
    if scraper == "none":
        return {"ok": False, "error": "Scraper not configured for this library"}

    chain = build_fallback_chain(scraper)

    row_clean_title = (movie.get("clean_title") or "").strip()
    search_name = folder_name
    search_levels = folder_levels
    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if parent_name:
            search_name = parent_name
            search_levels = str(parent)

    logger.info(
        f"rescrape_movie start: media_root='{media_root}' movie_id={movie_id} "
        f"scraper='{scraper}' chain={chain} folder='{folder_levels}' clean_title='{row_clean_title}' "
        f"search_name='{search_name}' tmdb_id='{movie.get('tmdb_id') or ''}'"
    )

    candidate_names = [
        row_clean_title,
        folder_name,
        Path(folder_levels).parent.name if folder_levels and str(Path(folder_levels).parent) != "." else "",
        Path(movie.get("path", "")).stem,
        movie.get("title") or "",
        movie.get("display_title") or "",
        code,
        search_name,
    ]
    clean_title_for_log = clean_search_title(search_name, candidate_names)
    token_for_log = _first_tmdb_token(candidate_names)
    logger.info(
        f"rescrape_movie item: media_root='{media_root}' movie_id={movie_id} "
        f"scraper='{normalize_scraper_name(scraper)}' raw_title='{search_name}' "
        f"clean_title='{clean_title_for_log}' tmdb_token={'yes' if token_for_log else 'no'} "
        f"tmdb_id='{movie.get('tmdb_id') or ''}'"
    )

    failures: list[str] = []
    for sb in chain:
        try:
            if sb == "tmdb_tv_search":
                clean_title = clean_search_title(search_name, candidate_names)
                data = await tmdb_title_search(clean_title, search_name, code, "tv")
            elif sb == "tmdb_movie_search":
                clean_title = clean_search_title(search_name, candidate_names)
                data = await tmdb_title_search(clean_title, search_name, code, "movie")
            else:
                scraper_obj = get_scraper(sb)
                if sb == "javdatabase":
                    data = await scraper_obj.full_scrape(search_name, code=code)
                else:
                    data = await scraper_obj.full_scrape(search_name, code=code, candidate_names=candidate_names, movie=movie)
            if not data or not data.get("title"):
                failures.append(f"{sb}: no result")
                logger.info(
                    f"rescrape_movie no result: media_root='{media_root}' movie_id={movie_id} "
                    f"scraper='{sb}' search='{search_name}'"
                )
                continue
            if sb in {"javdatabase", "auto"} and data.get("_exact_match"):
                passed = True
            elif sb == "javdatabase":
                passed = True
            else:
                passed = (
                    bool(data.get("_exact_match"))
                    or bool(data.get("_search_match_passed"))
                    or title_matches(data.get("title", ""), search_name, code)
                    or title_matches(data.get("original_title", ""), search_name, code)
                )
            if passed:
                async with _sqlite_write_semaphore:
                    affected = await _apply_scraped_data(folder_levels, data, media_root)
                if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                    season_num = infer_season_number(folder_name, data)
                    if season_num:
                        try:
                            from .tmdb import match_episodes_in_folder
                            async with _sqlite_write_semaphore:
                                await match_episodes_in_folder(
                                    str(data["tmdb_id"]), season_num, folder_levels, media_root
                                )
                        except Exception:
                            pass
                logger.info(
                    f"rescrape_movie success: media_root='{media_root}' movie_id={movie_id} "
                    f"scraper='{sb}' title='{data.get('title', search_name)}' affected={affected}"
                )
                return {"ok": True, "source": sb, "title": data.get("title", search_name), "affected": affected}
            else:
                failures.append(f"{sb}: title mismatch '{data.get('title', '')}'")
                logger.info(
                    f"rescrape_movie title mismatch: media_root='{media_root}' movie_id={movie_id} "
                    f"scraper='{sb}' cleaned_title='{search_name}' result_title='{data.get('title', '')}' "
                    f"source_id='{data.get('source_id') or data.get('tmdb_id') or data.get('bangumi_id') or data.get('javdb_id') or ''}'"
                )
        except Exception as e:
            failures.append(f"{sb}: {e}")
            logger.exception(
                f"rescrape_movie error: media_root='{media_root}' movie_id={movie_id} "
                f"scraper='{sb}' cleaned_title='{search_name}'"
            )

    failure_text = "; ".join(failures) if failures else "no handlers tried"
    logger.warning(
        f"rescrape_movie failed: media_root='{media_root}' movie_id={movie_id} "
        f"library_scraper='{scraper}' cleaned_title='{search_name}' failures={failure_text}"
    )
    return {"ok": False, "error": f"All scrapers failed: {failure_text}"}


async def rescrape_movie_manual(movie_id: int, query: str, preferred_scraper: str = None, source_id: str = None, media_type: str = "movie") -> dict:
    from .database import get_db, get_library_settings
    from .config import logger

    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "Movie not found"}

    movie = dict(row)
    folder_levels = movie.get("folder_levels", "")
    code = movie.get("code", "")
    media_root = movie.get("media_root", "")

    preferred = normalize_scraper_name(preferred_scraper)

    if source_id and preferred_scraper:
        data = None
        if preferred in {"tmdb_movie", "tmdb_tv"}:
            forced_media_type = "tv" if preferred == "tmdb_tv" else "movie"
            data = await _fetch_detail_legacy("tmdb", source_id, forced_media_type)
        elif preferred == "bangumi":
            data = await _fetch_detail_legacy("bangumi", source_id, "tv")
        elif preferred == "javdatabase":
            data = await _fetch_detail_legacy("javdatabase", source_id, "movie")

        if data and data.get("title"):
            async with _sqlite_write_semaphore:
                await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                folder_name = Path(folder_levels).name if folder_levels else ""
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        async with _sqlite_write_semaphore:
                            await match_episodes_in_folder(
                                str(data["tmdb_id"]), season_num, folder_levels, media_root
                            )
                    except Exception:
                        pass
            return {"ok": True, "source": preferred, "title": data.get("title", query)}
        else:
            return {"ok": False, "error": f"Failed to fetch detail from {preferred_scraper}"}

    if preferred_scraper and preferred in {"tmdb_movie", "tmdb_tv", "bangumi", "javdatabase", "auto"}:
        chain = [preferred]
    else:
        lib_setting = await get_library_settings(media_root)
        scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
        chain = build_fallback_chain(scraper) if scraper != "none" else ["tmdb_movie", "bangumi"]

    for sb in chain:
        try:
            if sb == "tmdb_tv_search":
                clean_title = clean_search_title(query, [query, movie.get("title") or "", code])
                data = await tmdb_title_search(clean_title, query, code, "tv")
            elif sb == "tmdb_movie_search":
                clean_title = clean_search_title(query, [query, movie.get("title") or "", code])
                data = await tmdb_title_search(clean_title, query, code, "movie")
            else:
                scraper_obj = get_scraper(sb)
                if sb == "javdatabase":
                    data = await scraper_obj.full_scrape(query, code=code)
                else:
                    data = await scraper_obj.full_scrape(query, code=code, candidate_names=[query, movie.get("title") or "", code], movie=movie)
            if not data or not data.get("title"):
                continue
            async with _sqlite_write_semaphore:
                await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                folder_name = Path(folder_levels).name if folder_levels else ""
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        async with _sqlite_write_semaphore:
                            await match_episodes_in_folder(
                                str(data["tmdb_id"]), season_num, folder_levels, media_root
                            )
                    except Exception:
                        pass
            return {"ok": True, "source": sb, "title": data.get("title", query)}
        except Exception as e:
            logger.warning(f"  manual scrape: {sb} error: {e}")

    return {"ok": False, "error": "All scrapers failed"}


async def rescrape_folder(folder_levels: str, media_root: str) -> dict:
    from .database import get_db
    from .config import logger

    if not media_root:
        return {"ok": False, "error": "media_root required"}

    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) AS total FROM movies WHERE folder_levels=? AND media_root=?",
        (folder_levels, media_root),
    )
    count_row = await cur.fetchone()
    total = int(count_row["total"] or 0) if count_row else 0
    if total <= 0:
        return {"ok": False, "error": "No movies found in folder"}

    cur = await db.execute(
        "SELECT id FROM movies WHERE folder_levels=? AND media_root=? ORDER BY id LIMIT 1",
        (folder_levels, media_root),
    )
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "No movies found in folder"}

    logger.info(
        f"Folder rescrape start: media_root='{media_root}' folder='{folder_levels}' "
        f"movie_count={total} representative_movie_id={row['id']}"
    )
    result = await rescrape_movie(row["id"])
    if not result.get("ok"):
        logger.warning(
            f"Folder rescrape failed: media_root='{media_root}' folder='{folder_levels}' "
            f"movie_count={total} error='{result.get('error', '')}'"
        )
        return result

    affected = int(result.get("affected") or total)
    logger.info(
        f"Folder rescrape complete: media_root='{media_root}' folder='{folder_levels}' "
        f"affected={affected} total={total} source='{result.get('source')}'"
    )
    return {"ok": True, "rescraped": affected, "total": total, "source": result.get("source"), "title": result.get("title")}


async def search_for_scrape(query: str, scraper: str = "tmdb") -> list[dict]:
    scraper = normalize_scraper_name(scraper)
    if scraper in {"tmdb_movie", "tmdb_tv"}:
        media_type = "tv" if scraper == "tmdb_tv" else "movie"
        items = await _search_scraper_candidates(scraper, query, media_type=media_type, limit=10)
        return [_candidate_to_dict(item) for item in items]
    elif scraper == "bangumi":
        items = await _search_scraper_candidates("bangumi", query, limit=10)
        return [_candidate_to_dict(item) for item in items]
    elif scraper == "javdatabase":
        items = await _search_scraper_candidates("javdatabase", query, media_type="movie", limit=10)
        return [_candidate_to_dict(item) for item in items]
    return []


async def fetch_search_backdrops(results: list[dict]) -> list[dict]:
    backdrops = []
    seen = set()
    for r in results:
        sid = r.get("source_id", "")
        src = r.get("source", "")
        mtype = r.get("media_type", "movie")
        key = f"{src}:{sid}"
        if not sid or key in seen:
            continue
        seen.add(key)
        backdrop = None
        if src == "tmdb":
            detail = await _fetch_detail_legacy("tmdb", sid, mtype)
        elif src == "bangumi":
            detail = await _fetch_detail_legacy("bangumi", sid, "tv")
        else:
            detail = None
        backdrop = detail.get("backdrop_url") if detail else None
        backdrops.append({"source_id": sid, "source": src, "backdrop_url": backdrop, "poster_url": r.get("poster_url")})
    return backdrops


async def change_folder_backdrop(folder_levels: str, media_root: str, fanart_url: str) -> dict:
    from .database import get_db
    from .config import logger
    if not fanart_url:
        return {"ok": False, "error": "No URL provided"}
    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    await db.execute("UPDATE movies SET fanart_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?", (fanart_url, folder_levels, media_root))
    await db.commit()
    logger.info(f"Backdrop changed for folder {folder_levels}")
    return {"ok": True}


async def rescrape_folder_manual(folder_levels: str, media_root: str, query: str, preferred_scraper: str = "") -> dict:
    from .database import get_db, get_library_settings
    from .config import logger

    if not media_root:
        return {"ok": False, "error": "media_root required"}

    db = await get_db()
    folder_name = Path(folder_levels).name if folder_levels else ""
    search_name = folder_name

    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if parent_name:
            search_name = parent_name

    preferred = normalize_scraper_name(preferred_scraper)
    if preferred_scraper and preferred in {"tmdb_movie", "tmdb_tv", "bangumi", "javdatabase", "auto"}:
        chain = [preferred]
    else:
        lib_setting = await get_library_settings(media_root)
        scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
        chain = build_fallback_chain(scraper) if scraper != "none" else ["tmdb_movie", "bangumi"]

    cur = await db.execute("SELECT code FROM movies WHERE folder_levels=? AND media_root=? LIMIT 1", (folder_levels, media_root))
    row = await cur.fetchone()
    code = row["code"] if row else ""

    for sb in chain:
        try:
            if sb == "tmdb_tv_search":
                clean_title = clean_search_title(query, [folder_name, search_name, query, code or ""])
                data = await tmdb_title_search(clean_title, query, code or query, "tv")
            elif sb == "tmdb_movie_search":
                clean_title = clean_search_title(query, [folder_name, search_name, query, code or ""])
                data = await tmdb_title_search(clean_title, query, code or query, "movie")
            else:
                scraper_obj = get_scraper(sb)
                if sb == "javdatabase":
                    data = await scraper_obj.full_scrape(query, code=code or query)
                else:
                    data = await scraper_obj.full_scrape(query, code=code or query, candidate_names=[folder_name, search_name, query, code or ""], movie={})
            if not data or not data.get("title"):
                continue
            async with _sqlite_write_semaphore:
                await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        async with _sqlite_write_semaphore:
                            await match_episodes_in_folder(str(data["tmdb_id"]), season_num, folder_levels, media_root)
                    except Exception:
                        pass
            return {"ok": True, "source": sb, "title": data.get("title", search_name)}
        except Exception as e:
            logger.warning(f"  folder manual scrape {sb}: {e}")
    return {"ok": False, "error": "All scrapers failed"}


async def apply_folder_scrape_result(folder_levels: str, media_root: str, source_id: str, source: str, media_type: str = "movie") -> dict:
    from .config import logger
    from pathlib import Path

    if not media_root:
        return {"ok": False, "error": "media_root required"}

    data = None
    if source == "tmdb":
        data = await _fetch_detail_legacy("tmdb", source_id, media_type)
    elif source == "bangumi":
        data = await _fetch_detail_legacy("bangumi", source_id, "tv")
    elif source == "javdatabase":
        data = await _fetch_detail_legacy("javdatabase", source_id, "movie")

    if not data or not data.get("title"):
        return {"ok": False, "error": f"Failed to fetch detail from {source}"}

    folder_name = Path(folder_levels).name if folder_levels else ""
    async with _sqlite_write_semaphore:
        affected = await _apply_scraped_data(folder_levels, data, media_root, replace=True)

    if source == "tmdb" and media_type == "tv" and data.get("tmdb_id"):
        season_num = infer_season_number(folder_name, data)
        if season_num:
            try:
                from .tmdb import match_episodes_in_folder
                async with _sqlite_write_semaphore:
                    await match_episodes_in_folder(str(data["tmdb_id"]), season_num, folder_levels, media_root)
            except Exception:
                pass

    logger.info(f"apply_folder_scrape: source={source} folder='{folder_levels}' media_root='{media_root}' affected={affected} rows title='{data.get('title')}'")
    return {"ok": True, "source": source, "title": data.get("title", ""), "affected": affected}


async def change_folder_cover(folder_levels: str, media_root: str, cover_url: str) -> dict:
    from .database import get_db
    from .config import logger
    import hashlib

    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    try:
        from .covers import download_and_compress_cover
        cache_key = hashlib.md5(cover_url.encode()).hexdigest()[:16]
        await download_and_compress_cover(cover_url, cache_key)
        await db.execute(
            "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?",
            (cover_url, cache_key, folder_levels, media_root)
        )
        await db.commit()
        logger.info(f"Cover changed for folder {folder_levels}")
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Change folder cover error: {e}")
        return {"ok": False, "error": str(e)}


async def edit_folder_movies(folder_levels: str, media_root: str, fields: dict) -> dict:
    from .database import get_db
    from .config import logger

    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    sets = []
    values = []
    for f in ("title", "release_date", "duration"):
        if f in fields and fields[f]:
            sets.append(f"{f}=?")
            values.append(fields[f])
    if not sets:
        return {"ok": False, "error": "No fields to update"}
    sets.append("updated_at=datetime('now')")
    values.extend([folder_levels, media_root])
    await db.execute(
        f"UPDATE movies SET {', '.join(sets)} WHERE folder_levels=? AND media_root=?",
        values
    )
    await db.commit()
    logger.info(f"Edited {len(sets)-1} fields for folder {folder_levels}")
    return {"ok": True}


async def delete_folder_movies(folder_levels: str, media_root: str) -> dict:
    from .database import get_db
    from .config import logger

    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    cur = await db.execute("SELECT id FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    rows = await cur.fetchall()
    count = len(rows)
    for r in rows:
        await db.execute("DELETE FROM tags WHERE movie_id=?", (r["id"],))
    await db.execute("DELETE FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    await db.commit()
    logger.info(f"Deleted {count} movies from folder {folder_levels}")
    return {"ok": True, "deleted": count}
