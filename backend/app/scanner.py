import re
import os
import json
import hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime
from .config import settings

CODE_PATTERN = re.compile(r"(?i)([A-Z]{1,})-?(\d{2,6})")
CODE_PATTERN_UNDERSCORE = re.compile(r"(?i)([A-Z]{1,})_(\d{2,6})")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".webm", ".mpg", ".mpeg"}
COVER_NAMES = {"poster.jpg", "poster.png", "cover.jpg", "cover.png", "folder.jpg", "folder.png",
               "movie-poster.jpg", "movie-poster.png", "season-poster.jpg", "season-poster.png",
               "banner.jpg", "banner.png", "fanart.jpg", "fanart.png", "backdrop.jpg", "backdrop.png"}
NFO_NAMES = {"movie.nfo", "tvshow.nfo"}
SKIP_DIRS = {".DS_Store", "__MACOSX", "Thumbs.db", ".Trashes"}
SEASON_PATTERN = re.compile(r'^(S|Season\s*|第)\s*\d{1,2}$', re.I)

_scan_progress: dict[str, dict] = {}

def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")

def extract_code(name: str) -> str | None:
    match = CODE_PATTERN.search(name)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    match = CODE_PATTERN_UNDERSCORE.search(name)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    return None

def find_media_files(folder: Path) -> list[Path]:
    files = []
    for ext in VIDEO_EXTS:
        files.extend(folder.glob(f"*{ext}"))
        files.extend(folder.glob(f"*{ext.upper()}"))
    return sorted(set(files))

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
        tree = ET.parse(filepath)
        root = tree.getroot()
    except Exception:
        return {}
    result = {}
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

def generate_folder_identifier(folder_name: str) -> str:
    clean = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', '', folder_name)
    clean = re.sub(r'\d{3,4}p', '', clean)
    clean = re.sub(r'[._\-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean or folder_name.strip()

def generate_keyword_queries(name: str) -> list[str]:
    clean = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', '', name)
    clean = re.sub(r'\d{3,4}p', '', clean, flags=re.I)
    clean = re.sub(r'(?i)\b(bluray|bdrip|webrip|web-dl|brrip|dvdrip|hdtv|hdcam|x264|x265|hevc|h264|avc|av1)\b', '', clean)
    clean = clean.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    clean = re.sub(r'[._\-\[\]{}()!！?？：:．,、\'\"\u300c\u300d\u300e\u300f\u3010\u3011\u2019\u2018\u201c\u201d]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if not clean or clean == name: return []
    return [clean]

def clean_folder_name(name: str) -> str:
    name = re.sub(r'\(?\d{4}\)?', '', name)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\{.*?\}', '', name)
    name = re.sub(r'\d{3,4}p', '', name, flags=re.I)
    name = re.sub(r'(?i)\b(bluray|bdrip|webrip|web-dl|brrip|dvdrip|hdtv|hdcam|x264|x265|hevc|h264|avc|av1)\b', '', name)
    name = name.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    name = re.sub(r'[._\-!！?？：:．,、\'\"\u300c\u300d\u300e\u300f\u3010\u3011\u2019\u2018\u201c\u201d]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name

def extract_cjk(text: str) -> str:
    return ''.join(c for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')

def extract_alpha(text: str) -> str:
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    return ''.join(c for c in text if c.isascii() and (c.isalpha() or c in "' ")).strip().lower()

def extract_romaji(text: str) -> str:
    t = text.replace('\u2019', "'").replace('\u2018', "'")
    return ' '.join(w.lower() for w in re.findall(r"[a-zA-Z'']{2,}", t))

def title_matches(scraped_title: str, folder_name: str, code: str | None = None) -> bool:
    if not scraped_title: return False

    s_clean = clean_folder_name(scraped_title)
    f_clean = clean_folder_name(folder_name)
    if not s_clean or not f_clean: return False

    if s_clean == f_clean: return True
    if len(s_clean) >= 4 and len(f_clean) >= 4:
        if s_clean in f_clean or f_clean in s_clean: return True

    s_cjk = extract_cjk(scraped_title)
    f_cjk = extract_cjk(folder_name)
    if s_cjk and f_cjk and len(s_cjk) >= 2 and len(f_cjk) >= 2:
        if s_cjk == f_cjk or s_cjk in f_cjk or f_cjk in s_cjk: return True

    s_romaji = extract_romaji(scraped_title)
    f_romaji = extract_romaji(folder_name)
    if s_romaji and f_romaji and len(s_romaji) >= 3 and len(f_romaji) >= 3:
        if s_romaji == f_romaji or s_romaji in f_romaji or f_romaji in s_romaji: return True

    s_alpha = extract_alpha(scraped_title)
    f_alpha = extract_alpha(folder_name)
    if s_alpha and f_alpha and len(s_alpha) >= 4 and len(f_alpha) >= 4:
        if s_alpha == f_alpha or s_alpha in f_alpha or f_alpha in s_alpha: return True

    if code:
        if code.upper() in scraped_title.upper(): return True
    return False

def scan_media(root: str = None) -> list[dict]:
    if root is None:
        roots = settings.get_all_media_roots()
    else:
        roots = [root]
    results = []
    for media_root in roots:
        base = Path(media_root)
        if not base.exists(): continue
        for dirpath, dirnames, filenames in os.walk(base):
            folder = Path(dirpath)
            media_files = find_media_files(folder)
            if not media_files: continue
            code = extract_code(folder.name)
            if not code and filenames:
                for f in filenames:
                    code = extract_code(Path(f).stem)
                    if code: break
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
            local_meta_json = json.dumps(local_meta, ensure_ascii=False) if local_meta else "{}"
            nfo_data = local_meta.get("nfo", {})
            title = nfo_data.get("title") or None
            release_date = nfo_data.get("premiered") or None
            duration = nfo_data.get("runtime") or None
            for mf in media_files:
                item = {
                    "path": str(mf), "code": code, "title": title,
                    "folder_levels": folder_levels, "cover_local": cover_local,
                    "media_root": media_root, "local_metadata": local_meta_json,
                }
                if release_date: item["release_date"] = release_date
                if duration: item["duration"] = duration
                if folder_mtime:
                    item["created_at"] = datetime.fromtimestamp(folder_mtime).strftime("%Y-%m-%d %H:%M:%S")
                results.append(item)
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
    return results

def build_fallback_chain(preferred: str) -> list[str]:
    if preferred == "none": return []
    if preferred == "javdatabase": return ["javdatabase"]
    chain = [preferred]
    for s in ["tmdb", "bangumi"]:
        if s not in chain: chain.append(s)
    return chain

async def try_scrape_javdb(code: str) -> dict | None:
    from .javdb import search_javdb
    data = await search_javdb(code)
    if data and data.get("title"):
        return {
            "source": "javdatabase", "title": data.get("title", ""),
            "actress": data.get("actress", ""), "release_date": data.get("release_date", ""),
            "duration": data.get("duration"), "cover_remote": data.get("cover_remote", ""),
            "javdb_url": data.get("javdb_url", ""), "javdb_score": data.get("javdb_score"),
            "javdb_likes": data.get("javdb_likes"), "javdb_thumbnails": data.get("javdb_thumbnails", ""),
        }
    return None

async def try_scrape_tmdb(folder_name: str, code: str) -> dict | None:
    from .tmdb import search_tmdb, fetch_tmdb_detail
    from .config import logger
    if not settings.tmdb_api_key and not settings.tmdb_access_token:
        logger.warning(f"TMDB credentials not configured, skipping for '{folder_name}'")
        return None
    queries = [folder_name, clean_folder_name(folder_name), generate_folder_identifier(folder_name)]
    queries.extend(generate_keyword_queries(folder_name))
    best = None
    for query in queries:
        if not query: continue
        results = await search_tmdb(query)
        if results:
            for candidate in results[:3]:
                if title_matches(candidate.get("title", ""), folder_name, code):
                    best = candidate
                    break
            if best: break
    if not best:
        logger.info(f"  TMDB: no match for '{folder_name}'")
        return None
    detail = await fetch_tmdb_detail(best["source_id"], best["media_type"])
    if not detail: return None
    return {
        "source": "tmdb", "title": detail.get("title", best.get("title", "")),
        "release_date": detail.get("release_date", ""),
        "duration": detail.get("runtime") or detail.get("duration", 0),
        "cover_remote": detail.get("poster_url", ""),
        "backdrop_url": detail.get("backdrop_url", ""),
        "javdb_score": detail.get("score"), "javdb_likes": detail.get("votes"),
        "tmdb_id": int(best["source_id"]), "tmdb_type": best["media_type"],
        "seasons": detail.get("seasons", []), "cast": detail.get("cast", []),
        "crew": detail.get("crew", []), "imdb_id": detail.get("imdb_id"),
    }

async def try_scrape_bangumi(folder_name: str, code: str) -> dict | None:
    from .bangumi import search_bangumi, fetch_bangumi_detail
    from .config import logger
    queries = [folder_name, clean_folder_name(folder_name), generate_folder_identifier(folder_name)]
    queries.extend(generate_keyword_queries(folder_name))
    best = None
    for query in queries:
        if not query: continue
        results = await search_bangumi(query)
        if results:
            for candidate in results[:3]:
                if title_matches(candidate.get("title", ""), folder_name, code):
                    best = candidate
                    break
            if best: break
    if not best:
        logger.info(f"  Bangumi: no match for '{folder_name}'")
        return None
    detail = await fetch_bangumi_detail(best["source_id"])
    if not detail: return None
    return {
        "source": "bangumi", "title": detail.get("title", best.get("title", "")),
        "release_date": detail.get("release_date", ""),
        "cover_remote": detail.get("poster_url", ""),
        "javdb_score": detail.get("score"),
        "javdb_likes": detail.get("votes") or detail.get("collection_total"),
    }

FALLBACK_HANDLERS = {
    "javdatabase": try_scrape_javdb,
    "tmdb": try_scrape_tmdb,
    "bangumi": try_scrape_bangumi,
}

def has_local_data(movie_row: dict) -> bool:
    if movie_row.get("cover_local") and Path(movie_row["cover_local"]).exists():
        if movie_row.get("local_metadata") and movie_row["local_metadata"] != "{}":
            return True
    return False

async def _apply_scraped_data(code: str, folder_levels: str, data: dict, media_root: str = "") -> int:
    from .database import get_db
    from .config import logger
    db = await get_db()
    if media_root:
        cur = await db.execute(
            """UPDATE movies SET
               title=COALESCE(NULLIF(?, ''), title),
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
               updated_at=datetime('now')
               WHERE folder_levels=? AND media_root=?""",
            (data.get("title", ""), data.get("actress", ""),
             data.get("release_date", ""), data.get("duration"),
             data.get("javdb_url", ""), data.get("javdb_score"),
             data.get("javdb_likes"), data.get("javdb_thumbnails", ""),
             data.get("cover_remote", ""), data.get("backdrop_url", ""),
             data.get("tmdb_id"), data.get("tmdb_type", ""),
             folder_levels, media_root)
        )
    else:
        cur = await db.execute(
            """UPDATE movies SET
               title=COALESCE(NULLIF(?, ''), title),
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
               updated_at=datetime('now')
               WHERE folder_levels=?""",
            (data.get("title", ""), data.get("actress", ""),
             data.get("release_date", ""), data.get("duration"),
             data.get("javdb_url", ""), data.get("javdb_score"),
             data.get("javdb_likes"), data.get("javdb_thumbnails", ""),
             data.get("cover_remote", ""), data.get("backdrop_url", ""),
             data.get("tmdb_id"), data.get("tmdb_type", ""),
             folder_levels)
        )
    affected = cur.rowcount
    logger.info(f"  _apply_scraped_data: folder='{folder_levels}' media_root='{media_root}' affected={affected} rows")

    folder_name = Path(folder_levels).name if folder_levels else ""
    if is_season_folder(folder_name) and data.get("cover_remote"):
        parent = str(Path(folder_levels).parent) if str(Path(folder_levels).parent) != "." else ""
        if parent:
            await db.execute(
                """UPDATE movies SET
                   cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
                   updated_at=datetime('now')
                   WHERE folder_levels LIKE ?""",
                (data.get("cover_remote", ""), parent + "/%")
            )

    if data.get("cover_remote"):
        # clear old local cache so new remote URL is used even if download fails
        await db.execute("UPDATE movies SET cover_local=NULL WHERE folder_levels=?", (folder_levels,))
        try:
            from .covers import download_and_compress_cover
            cache_key = hashlib.md5(data["cover_remote"].encode()).hexdigest()[:16]
            cached = await download_and_compress_cover(data["cover_remote"], cache_key)
            if cached:
                await db.execute("UPDATE movies SET cover_local=? WHERE folder_levels=?", (cache_key, folder_levels))
        except Exception:
            pass

    await db.commit()

def is_season_folder(name: str) -> bool:
    return bool(SEASON_PATTERN.match(name))

async def scrape_for_library(media_root: str):
    from .database import get_library_settings, get_db
    from .config import logger

    lib_setting = await get_library_settings(media_root)
    scraper = lib_setting.get("scraper", "none") if lib_setting else "none"
    if scraper == "none":
        logger.info(f"Scraping disabled for {media_root}")
        _scan_progress[media_root] = {"status": "disabled", "done": 0, "total": 0}
        return

    chain = build_fallback_chain(scraper)
    logger.info(f"Scraping {media_root} with chain: {' → '.join(chain)}")

    db = await get_db()
    cur = await db.execute(
        "SELECT DISTINCT code, folder_levels, cover_local, local_metadata FROM movies WHERE media_root=?",
        (media_root,)
    )
    rows = await cur.fetchall()
    if not rows:
        _scan_progress[media_root] = {"status": "done", "done": 0, "total": 0}
        return

    total_folders = len(set(r["folder_levels"] for r in rows if r["folder_levels"]))
    _scan_progress[media_root] = {"status": "scraping", "done": 0, "total": total_folders}

    scraped_folders = set()
    done_count = 0
    for r in rows:
        folder_levels = r["folder_levels"] or ""
        folder_name = Path(folder_levels).name if folder_levels else ""
        code = r["code"] or ""

        if not folder_name: continue
        if folder_levels in scraped_folders: continue

        if has_local_data(dict(r)):
            logger.info(f"  Skip (local data exists): {folder_name}")
            scraped_folders.add(folder_levels)
            done_count += 1
            _scan_progress[media_root] = {"status": "scraping", "done": done_count, "total": total_folders}
            continue

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

        scraped = False
        for sb in chain:
            handler = FALLBACK_HANDLERS.get(sb)
            if not handler: continue
            try:
                if sb == "javdatabase":
                    data = await handler(code)
                else:
                    data = await handler(search_name, code)
                if not data or not data.get("title"):
                    logger.info(f"  {sb}: no result for '{search_name}'")
                    continue
                if sb == "javdatabase":
                    passed = True
                else:
                    passed = title_matches(data.get("title", ""), search_name, code)
                if passed:
                    await _apply_scraped_data(code, folder_levels, data, media_root)
                    logger.info(f"  {sb}: {search_name} → {data.get('title', search_name)}")

                    if sb == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                        season_num = None
                        if is_season_folder(folder_name):
                            match = re.search(r'\d+', folder_name)
                            if match: season_num = int(match.group())
                        if season_num:
                            try:
                                from .tmdb import match_episodes_in_folder
                                matched = await match_episodes_in_folder(
                                    str(data["tmdb_id"]), season_num, folder_levels, media_root
                                )
                                if matched:
                                    logger.info(f"  TMDB: matched {matched} episodes in '{folder_levels}'")
                            except Exception as e:
                                logger.warning(f"  TMDB: episode matching error: {e}")

                    scraped = True
                    break
                else:
                    logger.info(f"  {sb}: title mismatch '{data.get('title', '')}' vs '{search_name}', trying fallback")
            except Exception as e:
                logger.warning(f"  {sb}: error for '{folder_name}': {e}")

        if not scraped:
            logger.info(f"  All scrapers failed for '{search_name}'")
        scraped_folders.add(folder_levels)
        done_count += 1
        _scan_progress[media_root] = {"status": "scraping", "done": done_count, "total": total_folders}

    _scan_progress[media_root] = {"status": "done", "done": total_folders, "total": total_folders}


async def clear_library_scraped_data(media_root: str):
    from .database import get_db
    from .config import logger
    import shutil

    db = await get_db()
    await db.execute(
        """UPDATE movies SET title=NULL, actress=NULL, release_date=NULL,
           duration=NULL, cover_remote=NULL, javdb_url=NULL, javdb_score=NULL,
           javdb_likes=NULL, javdb_thumbnails=NULL,
           tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
           episode_title=NULL, episode_overview=NULL, episode_still=NULL,
           updated_at=datetime('now')
           WHERE media_root=? AND local_metadata='{}'""",
        (media_root,)
    )
    await db.execute(
        """UPDATE movies SET cover_remote=NULL, javdb_url=NULL, javdb_score=NULL,
           javdb_likes=NULL, javdb_thumbnails=NULL,
           tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
           episode_title=NULL, episode_overview=NULL, episode_still=NULL,
           updated_at=datetime('now')
           WHERE media_root=? AND local_metadata!='{}'""",
        (media_root,)
    )
    await db.execute("DELETE FROM scraper_cache WHERE query LIKE ?", (f"%{media_root}%",))
    await db.execute("DELETE FROM javdb_cache WHERE code IN (SELECT code FROM movies WHERE media_root=?)", (media_root,))
    await db.commit()

    covers_dir = Path(settings.covers_dir)
    if covers_dir.exists():
        for f in covers_dir.glob("*.jpg"):
            try: f.unlink()
            except Exception: pass

    logger.info(f"Cleared all scraped data for {media_root}")


async def rescrape_movie(movie_id: int) -> dict:
    from .database import get_db
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
    scraper = lib_setting.get("scraper", "none") if lib_setting else "none"
    if scraper == "none":
        return {"ok": False, "error": "Scraper not configured for this library"}

    chain = build_fallback_chain(scraper)

    search_name = folder_name
    search_levels = folder_levels
    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if parent_name:
            search_name = parent_name
            search_levels = str(parent)

    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code)
            else:
                data = await handler(search_name, code)
            if not data or not data.get("title"):
                continue
            if sb == "javdatabase":
                passed = True
            else:
                passed = title_matches(data.get("title", ""), search_name, code)
            if passed:
                await _apply_scraped_data(code, folder_levels, data, media_root)
                if sb == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                    season_num = None
                    if is_season_folder(folder_name):
                        match_season = re.search(r'\d+', folder_name)
                        if match_season:
                            season_num = int(match_season.group())
                    if season_num:
                        try:
                            from .tmdb import match_episodes_in_folder
                            await match_episodes_in_folder(
                                str(data["tmdb_id"]), season_num, folder_levels, media_root
                            )
                        except Exception:
                            pass
                return {"ok": True, "source": sb, "title": data.get("title", search_name)}
            else:
                logger.info(f"  rescrape: {sb} title mismatch")
        except Exception as e:
            logger.warning(f"  rescrape: {sb} error: {e}")

    return {"ok": False, "error": "All scrapers failed"}


async def rescrape_movie_manual(movie_id: int, query: str, preferred_scraper: str = None) -> dict:
    from .database import get_db
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

    if preferred_scraper and preferred_scraper in FALLBACK_HANDLERS:
        chain = [preferred_scraper]
    else:
        lib_setting = await get_library_settings(media_root)
        scraper = lib_setting.get("scraper", "none") if lib_setting else "none"
        chain = build_fallback_chain(scraper) if scraper != "none" else ["tmdb", "bangumi"]

    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code)
            else:
                data = await handler(query, code)
            if not data or not data.get("title"):
                continue
            await _apply_scraped_data(code, folder_levels, data, media_root)
            if sb == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                season_num = None
                folder_name = Path(folder_levels).name if folder_levels else ""
                if is_season_folder(folder_name):
                    match_season = re.search(r'\d+', folder_name)
                    if match_season:
                        season_num = int(match_season.group())
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
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

    db = await get_db()
    if media_root:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    else:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=?", (folder_levels,))
    rows = await cur.fetchall()
    if not rows:
        return {"ok": False, "error": "No movies found in folder"}

    count = 0
    for row in rows:
        result = await rescrape_movie(row["id"])
        if result.get("ok"):
            count += 1

    logger.info(f"Folder rescrape: {count}/{len(rows)} movies updated in {folder_levels}")
    return {"ok": True, "rescraped": count, "total": len(rows)}


async def search_for_scrape(query: str, scraper: str = "tmdb") -> list[dict]:
    results = []
    if scraper == "tmdb":
        from .tmdb import search_tmdb
        items = await search_tmdb(query)
        for item in items[:10]:
            results.append({
                "source": "tmdb",
                "source_id": item.get("source_id", ""),
                "media_type": item.get("media_type", ""),
                "title": item.get("title", ""),
                "original_title": item.get("original_title", ""),
                "year": item.get("release_date", "")[:4] if item.get("release_date") else "",
                "poster_url": item.get("poster_url"),
                "overview": item.get("overview", ""),
            })
    elif scraper == "bangumi":
        from .bangumi import search_bangumi
        items = await search_bangumi(query)
        for item in items[:10]:
            results.append({
                "source": "bangumi",
                "source_id": item.get("source_id", ""),
                "media_type": "tv",
                "title": item.get("title", ""),
                "original_title": item.get("original_title", ""),
                "year": item.get("release_date", "")[:4] if item.get("release_date") else "",
                "poster_url": item.get("poster_url"),
                "overview": item.get("overview", ""),
            })
    elif scraper == "javdatabase":
        from .javdb import search_javdb
        data = await search_javdb(query)
        if data and data.get("title"):
            results.append({
                "source": "javdatabase",
                "source_id": query,
                "media_type": "movie",
                "title": data.get("title", ""),
                "original_title": "",
                "year": data.get("release_date", "")[:4] if data.get("release_date") else "",
                "poster_url": data.get("cover_remote"),
                "overview": "",
            })
    return results


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
        detail = None
        if src == "tmdb":
            from .tmdb import fetch_tmdb_detail
            detail = await fetch_tmdb_detail(sid, mtype)
        elif src == "bangumi":
            from .bangumi import fetch_bangumi_detail
            detail = await fetch_bangumi_detail(sid)
        backdrop = detail.get("backdrop_url") if detail else None
        backdrops.append({"source_id": sid, "source": src, "backdrop_url": backdrop, "poster_url": r.get("poster_url")})
    return backdrops


async def change_folder_backdrop(folder_levels: str, media_root: str, fanart_url: str) -> dict:
    from .database import get_db
    from .config import logger
    if not fanart_url:
        return {"ok": False, "error": "No URL provided"}
    db = await get_db()
    if media_root:
        await db.execute("UPDATE movies SET fanart_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?", (fanart_url, folder_levels, media_root))
    else:
        await db.execute("UPDATE movies SET fanart_local=?, updated_at=datetime('now') WHERE folder_levels=?", (fanart_url, folder_levels))
    await db.commit()
    logger.info(f"Backdrop changed for folder {folder_levels}")
    return {"ok": True}


async def rescrape_folder_manual(folder_levels: str, media_root: str, query: str, preferred_scraper: str = "") -> dict:
    from .database import get_db, get_library_settings
    from .config import logger

    db = await get_db()
    folder_name = Path(folder_levels).name if folder_levels else ""
    search_name = folder_name

    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if parent_name:
            search_name = parent_name

    if preferred_scraper and preferred_scraper in FALLBACK_HANDLERS:
        chain = [preferred_scraper]
    else:
        lib_setting = await get_library_settings(media_root)
        scraper = lib_setting.get("scraper", "none") if lib_setting else "none"
        chain = build_fallback_chain(scraper) if scraper != "none" else ["tmdb", "bangumi"]

    if media_root:
        cur = await db.execute("SELECT code FROM movies WHERE folder_levels=? AND media_root=? LIMIT 1", (folder_levels, media_root))
    else:
        cur = await db.execute("SELECT code FROM movies WHERE folder_levels=? LIMIT 1", (folder_levels,))
    row = await cur.fetchone()
    code = row["code"] if row else ""

    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code or query)
            else:
                data = await handler(query, code or query)
            if not data or not data.get("title"):
                continue
            await _apply_scraped_data(code or query, folder_levels, data, media_root)
            if sb == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                season_num = None
                if is_season_folder(folder_name):
                    match = re.search(r'\d+', folder_name)
                    if match:
                        season_num = int(match.group())
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
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

    data = None
    if source == "tmdb":
        from .tmdb import fetch_tmdb_detail
        detail = await fetch_tmdb_detail(source_id, media_type)
        if detail:
            data = {
                "source": "tmdb", "title": detail.get("title") or "",
                "release_date": detail.get("release_date") or "",
                "duration": detail.get("runtime") or detail.get("duration", 0),
                "cover_remote": detail.get("poster_url") or "",
                "backdrop_url": detail.get("backdrop_url") or "",
                "tmdb_id": int(source_id), "tmdb_type": media_type,
                "cast": detail.get("cast", []), "crew": detail.get("crew", []),
                "seasons": detail.get("seasons", []),
                "imdb_id": detail.get("imdb_id") or "",
            }
    elif source == "bangumi":
        from .bangumi import fetch_bangumi_detail
        detail = await fetch_bangumi_detail(source_id)
        if detail:
            data = {
                "source": "bangumi", "title": detail.get("title") or "",
                "release_date": detail.get("release_date") or "",
                "cover_remote": detail.get("poster_url") or "",
            }
    elif source == "bangumi":
        from .bangumi import fetch_bangumi_detail
        detail = await fetch_bangumi_detail(source_id)
        if detail:
            data = {
                "source": "bangumi", "title": detail.get("title", ""),
                "release_date": detail.get("release_date", ""),
                "cover_remote": detail.get("poster_url", ""),
            }
    elif source == "javdatabase":
        data = await try_scrape_javdb(source_id)

    if not data or not data.get("title"):
        return {"ok": False, "error": f"Failed to fetch detail from {source}"}

    folder_name = Path(folder_levels).name if folder_levels else ""
    affected = await _apply_scraped_data(source_id, folder_levels, data, media_root)

    if source == "tmdb" and media_type == "tv" and data.get("tmdb_id"):
        season_num = None
        if is_season_folder(folder_name):
            match = re.search(r'\d+', folder_name)
            if match:
                season_num = int(match.group())
        if season_num:
            try:
                from .tmdb import match_episodes_in_folder
                await match_episodes_in_folder(str(data["tmdb_id"]), season_num, folder_levels, media_root)
            except Exception:
                pass

    logger.info(f"apply_folder_scrape: source={source} folder='{folder_levels}' media_root='{media_root}' affected={affected} rows title='{data.get('title')}'")
    return {"ok": True, "source": source, "title": data.get("title", ""), "affected": affected}


async def change_folder_cover(folder_levels: str, media_root: str, cover_url: str) -> dict:
    from .database import get_db
    from .config import logger
    import hashlib

    db = await get_db()
    try:
        from .covers import download_and_compress_cover
        cache_key = hashlib.md5(cover_url.encode()).hexdigest()[:16]
        await download_and_compress_cover(cover_url, cache_key)
        if media_root:
            await db.execute(
                "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?",
                (cover_url, cache_key, folder_levels, media_root)
            )
        else:
            await db.execute(
                "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE folder_levels=?",
                (cover_url, cache_key, folder_levels)
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
    if media_root:
        values.extend([folder_levels, media_root])
        await db.execute(
            f"UPDATE movies SET {', '.join(sets)} WHERE folder_levels=? AND media_root=?",
            values
        )
    else:
        values.append(folder_levels)
        await db.execute(
            f"UPDATE movies SET {', '.join(sets)} WHERE folder_levels=?",
            values
        )
    await db.commit()
    logger.info(f"Edited {len(sets)-1} fields for folder {folder_levels}")
    return {"ok": True}


async def delete_folder_movies(folder_levels: str, media_root: str) -> dict:
    from .database import get_db
    from .config import logger

    db = await get_db()
    if media_root:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    else:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=?", (folder_levels,))
    rows = await cur.fetchall()
    count = len(rows)
    for r in rows:
        await db.execute("DELETE FROM tags WHERE movie_id=?", (r["id"],))
    if media_root:
        await db.execute("DELETE FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    else:
        await db.execute("DELETE FROM movies WHERE folder_levels=?", (folder_levels,))
    await db.commit()
    logger.info(f"Deleted {count} movies from folder {folder_levels}")
    return {"ok": True, "deleted": count}
