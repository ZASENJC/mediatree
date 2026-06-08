import httpx
import asyncio
import json
from httpx import HTTPStatusError
from typing import Literal
from .config import settings, logger
from .database import get_scraper_cache, set_scraper_cache

TMDB_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"
_tmdb_client: httpx.AsyncClient | None = None
_tmdb_semaphore = asyncio.Semaphore(max(1, settings.scraper_api_concurrency))
_tmdb_id_tasks: dict[tuple[int, str], asyncio.Task] = {}
_warned_missing_auth = False


def _get_tmdb_headers() -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if settings.tmdb_access_token:
        h["Authorization"] = f"Bearer {settings.tmdb_access_token}"
    return h


def _has_tmdb_auth() -> bool:
    return bool(settings.tmdb_access_token) or bool(settings.tmdb_api_key)


async def _tmdb_get(path: str, params: dict | None = None) -> httpx.Response:
    global _tmdb_client
    if _tmdb_client is None or _tmdb_client.is_closed:
        _tmdb_client = httpx.AsyncClient(timeout=settings.scraper_http_timeout, follow_redirects=True)
    async with _tmdb_semaphore:
        url = f"{TMDB_BASE}{path}"
        headers = _get_tmdb_headers()
        if params is None:
            params = {}
        if not headers.get("Authorization") and settings.tmdb_api_key:
            params["api_key"] = settings.tmdb_api_key
        resp = await _tmdb_client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp


async def search_tmdb(
    query: str,
    lang: str = "zh-CN",
    media_type: Literal["movie", "tv"] | None = None,
) -> list[dict]:
    if not _has_tmdb_auth():
        return []
    requested_type = media_type.lower() if media_type else None
    if requested_type and requested_type not in {"movie", "tv"}:
        logger.warning(f"Invalid TMDB media_type for search: {media_type}")
        return []
    query = (query or "").strip()
    if not query:
        return []
    cache_key = f"tmdb_search:{requested_type}:{query}" if requested_type else f"tmdb_search:multi:{query}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        logger.info(f"TMDB cache hit: {cache_key}")
        return cache_data

    results = []
    try:
        for mtype in ([requested_type] if requested_type else ["movie", "tv"]):
            logger.info(f"TMDB search endpoint: /search/{mtype} query='{query}'")
            resp = await _tmdb_get(f"/search/{mtype}", {"query": query, "language": lang})
            data = resp.json()
            for item in data.get("results", [])[:5]:
                poster = None
                if item.get("poster_path"):
                    poster = f"{IMAGE_BASE}/w500{item['poster_path']}"
                backdrop = None
                if item.get("backdrop_path"):
                    backdrop = f"{IMAGE_BASE}/w1280{item['backdrop_path']}"
                results.append({
                    "source": "tmdb",
                    "source_id": str(item["id"]),
                    "media_type": mtype,
                    "title": item.get("title") or item.get("name") or query,
                    "original_title": item.get("original_title") or item.get("original_name", ""),
                    "overview": item.get("overview", ""),
                    "poster_url": poster,
                    "backdrop_url": backdrop,
                    "release_date": item.get("release_date") or item.get("first_air_date"),
                    "score": item.get("vote_average"),
                    "votes": item.get("vote_count"),
                    "genre_ids": item.get("genre_ids", []),
                })
    except HTTPStatusError as e:
        scope = f"{requested_type} " if requested_type else ""
        logger.warning(f"TMDB {scope}search HTTP error for '{query}': status={e.response.status_code}")
    except Exception as e:
        scope = f"{requested_type} " if requested_type else ""
        logger.warning(f"TMDB {scope}search error for '{query}': {e}")

    await set_scraper_cache("tmdb", cache_key, results)
    return results


async def search_tmdb_movie_by_title(query: str, lang: str = "zh-CN") -> list[dict]:
    return await search_tmdb(query, lang=lang, media_type="movie")


async def search_tmdb_tv_by_title(query: str, lang: str = "zh-CN") -> list[dict]:
    return await search_tmdb(query, lang=lang, media_type="tv")


async def fetch_tmdb_detail(source_id: str, media_type: str, lang: str = "zh-CN") -> dict | None:
    if not _has_tmdb_auth():
        return None
    cache_key = f"tmdb_id:v3:{media_type}:{source_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        logger.info(f"TMDB cache hit: {cache_key}")
        return cache_data

    try:
        logger.info(f"TMDB detail endpoint: /{media_type}/{source_id}")
        resp = await _tmdb_get(
            f"/{media_type}/{source_id}",
            {"language": lang, "append_to_response": "credits,external_ids,keywords,release_dates,content_ratings"}
        )
        data = resp.json()

        genres = [g["name"] for g in data.get("genres", [])]
        kw_raw = data.get("keywords", {}) or {}
        kw_list = kw_raw.get("keywords") or kw_raw.get("results") or []
        keywords = ", ".join(k["name"] for k in kw_list if k.get("name")) if kw_list else None
        poster = f"{IMAGE_BASE}/w500{data['poster_path']}" if data.get("poster_path") else None
        backdrop = f"{IMAGE_BASE}/w1280{data['backdrop_path']}" if data.get("backdrop_path") else None

        cast = []
        for c in (data.get("credits", {}) or {}).get("cast", []):
            cast.append({"name": c.get("name", ""), "character": c.get("character", ""),
                        "id": c.get("id"), "person_id": str(c.get("id", "")),
                        "profile_path": f"{IMAGE_BASE}/w185{c['profile_path']}" if c.get("profile_path") else None})
        crew = []
        for c in (data.get("credits", {}) or {}).get("crew", []):
            crew.append({"name": c.get("name", ""), "job": c.get("job", ""),
                        "id": c.get("id"), "person_id": str(c.get("id", "")),
                        "profile_path": f"{IMAGE_BASE}/w185{c['profile_path']}" if c.get("profile_path") else None})

        external = data.get("external_ids", {}) or {}
        studios = [c.get("name") for c in data.get("production_companies", []) if c.get("name")]
        seasons = []
        for s in data.get("seasons", []):
            sp = f"{IMAGE_BASE}/w500{s['poster_path']}" if s.get("poster_path") else None
            seasons.append({
                "season_number": s.get("season_number"),
                "name": s.get("name", ""),
                "episode_count": s.get("episode_count", 0),
                "poster_path": sp,
                "overview": s.get("overview", ""),
            })

        runtime = data.get("runtime") or (
            data.get("episode_run_time", [0])[0]
            if isinstance(data.get("episode_run_time"), list) and data.get("episode_run_time")
            else 0
        )

        # Extract content rating / certification
        content_rating = ""
        if media_type == "movie":
            rd = data.get("release_dates", {}) or {}
            for r in rd.get("results", []):
                if r.get("iso_3166_1") == "US":
                    for d in r.get("release_dates", []):
                        if d.get("certification"):
                            content_rating = d["certification"]
                            break
                    break
        else:
            cr = data.get("content_ratings", {}) or {}
            for r in cr.get("results", []):
                if r.get("iso_3166_1") == "US":
                    content_rating = r.get("rating") or ""
                    break

        result = {
            "source": "tmdb",
            "source_id": source_id,
            "media_type": media_type,
            "title": data.get("title") or data.get("name", ""),
            "original_title": data.get("original_title") or data.get("original_name", ""),
            "overview": data.get("overview", ""),
            "poster_url": poster,
            "backdrop_url": backdrop,
            "release_date": data.get("release_date") or data.get("first_air_date"),
            "score": data.get("vote_average"),
            "votes": data.get("vote_count"),
            "runtime": runtime,
            "genre": ", ".join(genres) if genres else None,
            "keywords": keywords,
            "tagline": data.get("tagline"),
            "status": data.get("status"),
            "content_rating": content_rating,
            "cast": cast,
            "crew": crew,
            "studios": studios,
            "imdb_id": external.get("imdb_id"),
            "seasons": seasons,
            "number_of_seasons": data.get("number_of_seasons", 0),
            "number_of_episodes": data.get("number_of_episodes", 0),
            "raw": data,
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB detail HTTP error for {media_type}/{source_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB detail error for {source_id}: {e}")
        return None


async def fetch_tmdb_by_id(tmdb_id: int, media_type: Literal["movie", "tv"], lang: str = "zh-CN") -> dict | None:
    global _warned_missing_auth
    if not _has_tmdb_auth():
        if not _warned_missing_auth:
            logger.warning("TMDB credentials not configured, skipping TMDB ID exact match")
            _warned_missing_auth = True
        return None

    requested_type = media_type.lower()
    if requested_type not in {"movie", "tv"}:
        logger.warning(f"Invalid TMDB media_type for ID lookup: {media_type}")
        return None

    cache_key = f"tmdb_id:v3:{requested_type}:{tmdb_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data

    try:
        detail = await fetch_tmdb_detail(str(tmdb_id), requested_type, lang)
        if detail and detail.get("title"):
            detail["media_type"] = requested_type
            await set_scraper_cache("tmdb", cache_key, detail)
            return detail
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB ID detail error for {requested_type}/{tmdb_id}: {e}")
    except Exception as e:
        logger.warning(f"TMDB ID detail error for {requested_type}/{tmdb_id}: {e}")
    return None


async def fetch_tmdb_movie_by_id(tmdb_id: int, lang: str = "zh-CN") -> dict | None:
    return await fetch_tmdb_by_id(tmdb_id, "movie", lang=lang)


async def fetch_tmdb_tv_by_id(tmdb_id: int, lang: str = "zh-CN") -> dict | None:
    return await fetch_tmdb_by_id(tmdb_id, "tv", lang=lang)


async def fetch_tmdb_by_imdb_id(imdb_id: str, lang: str = "zh-CN") -> dict | None:
    """Look up TMDB entry via /find/ endpoint with IMDB external ID.

    Uses TMDB's /find/{imdb_id}?external_source=imdb_id. Prefers movie results,
    falls back to TV if no movie found.
    """
    global _warned_missing_auth
    if not _has_tmdb_auth():
        if not _warned_missing_auth:
            logger.warning("TMDB credentials not configured, skipping IMDB ID lookup")
            _warned_missing_auth = True
        return None

    imdb_id = (imdb_id or "").strip().lower()
    if not imdb_id.startswith("tt") or not imdb_id[2:].isdigit():
        return None

    cache_key = f"tmdb_imdb:{imdb_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        logger.info(f"TMDB cache hit: {cache_key}")
        return cache_data

    try:
        resp = await _tmdb_get(f"/find/{imdb_id}", {"external_source": "imdb_id", "language": lang})
        data = resp.json()

        results: list[tuple[str, str]] = []
        for r in data.get("movie_results", []):
            results.append(("movie", str(r["id"])))
        for r in data.get("tv_results", []):
            results.append(("tv", str(r["id"])))

        if not results:
            logger.info(f"TMDB /find/{imdb_id}: no results")
            await set_scraper_cache("tmdb", cache_key, None)
            return None

        media_type, source_id = results[0]
        detail = await fetch_tmdb_detail(source_id, media_type, lang)
        if detail and detail.get("title"):
            detail["media_type"] = media_type
            await set_scraper_cache("tmdb", cache_key, detail)
            return detail

        await set_scraper_cache("tmdb", cache_key, None)
        return None
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB /find/ HTTP error for imdb_id={imdb_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB /find/ error for imdb_id={imdb_id}: {e}")
        return None


async def _fetch_tmdb_by_id_task(tmdb_id: int, media_type: Literal["movie", "tv"], lang: str) -> dict | None:
    key = (tmdb_id, media_type)
    task = _tmdb_id_tasks.get(key)
    if task is None or task.done():
        task = asyncio.create_task(fetch_tmdb_by_id(tmdb_id, media_type, lang))
        _tmdb_id_tasks[key] = task
    try:
        return await task
    finally:
        if task.done():
            _tmdb_id_tasks.pop(key, None)


async def fetch_tmdb_candidates_by_id(tmdb_id: int, lang: str = "zh-CN") -> dict:
    movie_task = _fetch_tmdb_by_id_task(tmdb_id, "movie", lang)
    tv_task = _fetch_tmdb_by_id_task(tmdb_id, "tv", lang)
    movie, tv = await asyncio.gather(movie_task, tv_task, return_exceptions=True)
    if isinstance(movie, Exception):
        logger.warning(f"TMDB movie candidate error for {tmdb_id}: {movie}")
        movie = None
    if isinstance(tv, Exception):
        logger.warning(f"TMDB tv candidate error for {tmdb_id}: {tv}")
        tv = None
    return {"movie": movie, "tv": tv}


async def fetch_tv_season(series_id: str, season_number: int, lang: str = "zh-CN") -> dict | None:
    if not _has_tmdb_auth():
        return None
    cache_key = f"season:{series_id}:{season_number}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data

    try:
        resp = await _tmdb_get(f"/tv/{series_id}/season/{season_number}", {"language": lang})
        data = resp.json()

        episodes = []
        for ep in data.get("episodes", []):
            still = f"{IMAGE_BASE}/w300{ep['still_path']}" if ep.get("still_path") else None
            episodes.append({
                "episode_number": ep.get("episode_number"),
                "name": ep.get("name", ""),
                "overview": ep.get("overview", ""),
                "still_path": still,
                "air_date": ep.get("air_date"),
                "vote_average": ep.get("vote_average"),
                "vote_count": ep.get("vote_count"),
                "runtime": ep.get("runtime"),
            })

        poster = f"{IMAGE_BASE}/w500{data['poster_path']}" if data.get("poster_path") else None

        result = {
            "season_number": data.get("season_number"),
            "name": data.get("name", ""),
            "overview": data.get("overview", ""),
            "poster_path": poster,
            "air_date": data.get("air_date"),
            "episode_count": len(episodes),
            "episodes": episodes,
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except Exception as e:
        logger.warning(f"TMDB season error for {series_id}/S{season_number}: {e}")
        return None


async def fetch_tv_episode(series_id: str, season_number: int, episode_number: int, lang: str = "zh-CN") -> dict | None:
    if not _has_tmdb_auth():
        return None
    cache_key = f"episode:{series_id}:{season_number}:{episode_number}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data

    try:
        resp = await _tmdb_get(f"/tv/{series_id}/season/{season_number}/episode/{episode_number}",
                               {"language": lang, "append_to_response": "credits"})
        data = resp.json()

        still = f"{IMAGE_BASE}/w300{data['still_path']}" if data.get("still_path") else None

        credits = data.get("credits", {}) or {}
        cast = []
        seen_names = set()
        for section in [credits.get("cast", []), credits.get("guest_stars", [])]:
            for c in section:
                name = c.get("name", "")
                if name and name not in seen_names:
                    seen_names.add(name)
                    cast.append({"name": name, "character": c.get("character", ""),
                                "id": c.get("id"), "person_id": str(c.get("id", "")),
                                "profile_path": f"{IMAGE_BASE}/w185{c['profile_path']}" if c.get("profile_path") else None})
        crew = []
        for c in credits.get("crew", []):
            crew.append({"name": c.get("name", ""), "job": c.get("job", ""),
                        "id": c.get("id"), "person_id": str(c.get("id", "")),
                        "profile_path": f"{IMAGE_BASE}/w185{c['profile_path']}" if c.get("profile_path") else None})

        result = {
            "episode_number": data.get("episode_number"),
            "name": data.get("name", ""),
            "overview": data.get("overview", ""),
            "still_path": still,
            "air_date": data.get("air_date"),
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "runtime": data.get("runtime"),
            "season_number": data.get("season_number"),
            "guest_stars": cast,
            "cast": cast,
            "crew": crew,
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except Exception as e:
        logger.warning(f"TMDB episode error for {series_id}/S{season_number}E{episode_number}: {e}")
        return None


async def match_episodes_in_folder(
    series_id: str, season_number: int, folder_levels: str,
    media_root: str, lang: str = "zh-CN",
) -> int:
    from .database import get_db
    from .anime_naming import extract_episode_number
    from pathlib import Path
    import re

    season_data = await fetch_tv_season(series_id, season_number, lang)
    if not season_data or not season_data.get("episodes"):
        # Auto season-merge: when TMDB has no episodes for this season,
        # try offset-mapping into an existing TMDB season via sibling folders
        if season_number > 0:
            try:
                merged = await _try_season_merge_auto(
                    series_id, season_number, folder_levels, media_root, lang
                )
                if merged:
                    return merged
            except Exception as e:
                from .config import logger
                logger.warning(f"TMDB auto season-merge failed for '{folder_levels}': {e}")
        return 0

    db = await get_db()
    cur = await db.execute(
        """SELECT id, path, code FROM movies
           WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?
           AND COALESCE(content_role, 'main') != 'special'""",
        (folder_levels, f"{folder_levels}/%", media_root)
    )
    movies = await cur.fetchall()

    updated = 0
    ep_pattern = re.compile(
        r'\[(\d{1,4})\](?=\[[^\]]+\])'      # [01][Ma10p_1080p][x265_flac]
        r'|[eE][pP]?\s*(\d{1,4})'           # E01, Ep01, EP 01
        r'|[-_. ](\d{1,4})(?:[\.\-_\s]|$)'  # -01, _01, .01,  01
        r'|第\s*(\d{1,4})\s*[集話话]'        # 第01集, 第01话
        r'|^(\d{1,4})[\s._-]'               # 01.mkv (number at start)
        r'|[#＃](\d{1,4})'                   # #01, ＃01
        r'|[Nn]o\.?\s*(\d{1,4})'            # No.01, no01
    )

    for m in movies:
        filename = Path(m["path"]).stem
        ep_num = extract_episode_number(filename)
        match = ep_pattern.search(filename)
        if ep_num is None and match:
            ep_num = int(next(g for g in match.groups() if g))

        if ep_num is None:
            continue

        for ep in season_data["episodes"]:
            if ep["episode_number"] == ep_num:
                still_local = None
                if ep.get("still_path"):
                    try:
                        from .covers import download_and_cache_still
                        import hashlib
                        sk = hashlib.md5(ep["still_path"].encode()).hexdigest()[:16]
                        still_local = await download_and_cache_still(ep["still_path"], sk)
                    except Exception:
                        pass

                await db.execute(
                    """UPDATE movies SET
                       tmdb_id=?, tmdb_type='tv', tmdb_season=?, tmdb_episode=?,
                       episode_title=COALESCE(NULLIF(?, ''), episode_title),
                       episode_overview=COALESCE(NULLIF(?, ''), episode_overview),
                       episode_still=COALESCE(NULLIF(?, ''), episode_still),
                       episode_still_local=COALESCE(NULLIF(?, ''), episode_still_local),
                       updated_at=datetime('now')
                       WHERE id=?""",
                    (int(series_id), season_number, ep_num,
                     ep.get("name", ""), ep.get("overview", ""),
                     ep.get("still_path", ""), still_local or "",
                     m["id"])
                )
                # Update episode-specific credits
                try:
                    ep_detail = await fetch_tv_episode(series_id, season_number, ep_num)
                    if ep_detail and (ep_detail.get("cast") or ep_detail.get("crew")):
                        await db.execute(
                            """UPDATE movies SET "cast"=?, crew=? WHERE id=?""",
                            (json.dumps(ep_detail.get("cast") or [], ensure_ascii=False),
                             json.dumps(ep_detail.get("crew") or [], ensure_ascii=False),
                             m["id"])
                        )
                except Exception:
                    pass
                updated += 1
                break
    await db.commit()
    return updated


async def _try_season_merge_auto(
    series_id: str, season_number: int, folder_levels: str,
    media_root: str, lang: str = "zh-CN",
) -> int:
    """Auto-merge a local season folder into an existing TMDB season when
    TMDB has no separate season for the requested season_number.

    Algorithm:
    1. Parse parent path from folder_levels
    2. Find direct-child sibling season folders under the same parent
    3. Calculate cumulative offset from earlier (already matched) siblings
    4. Determine target TMDB season from a matched sibling
    5. Offset local episode numbers and match against TMDB season data
    """
    import re
    from pathlib import Path

    from .anime_naming import extract_episode_number
    from .config import logger
    from .database import get_db

    # 1. Parse parent path — only merge when folder is nested under a parent
    parent_levels = str(Path(folder_levels).parent)
    if parent_levels in (".", "", folder_levels):
        return 0

    db = await get_db()

    # 2. Find all distinct folder_levels under the same parent
    cur = await db.execute(
        "SELECT DISTINCT folder_levels FROM movies "
        "WHERE folder_levels LIKE ? AND media_root=? "
        "AND COALESCE(content_role, 'main') != 'special' "
        "ORDER BY folder_levels",
        (f"{parent_levels}/%", media_root),
    )
    rows = await cur.fetchall()

    # Filter to direct children only (exclude sub-subfolders like "Show/S01/Extras")
    expected_depth = parent_levels.count("/") + 1 if parent_levels else 1
    sibling_folders = [
        r["folder_levels"] for r in rows
        if r["folder_levels"].count("/") == expected_depth
    ]

    if len(sibling_folders) <= 1:
        # Only the current folder exists, nothing to merge against
        return 0

    # Sort by extracted numeric season number for reliable ordering
    def _folder_season_num(fl: str) -> int:
        name = Path(fl).name
        m = re.search(r"(\d+)", name)
        return int(m.group(1)) if m else 9999

    sibling_folders.sort(key=_folder_season_num)

    # 3. Calculate cumulative offset from earlier siblings
    cumulative_offset = 0
    target_season = None

    for sib in sibling_folders:
        sib_num = _folder_season_num(sib)
        if sib_num >= season_number:
            continue  # skip current and later siblings

        # Count already-matched episodes in this sibling
        cnt_cur = await db.execute(
            "SELECT COUNT(*) AS cnt FROM movies "
            "WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=? "
            "AND tmdb_episode IS NOT NULL "
            "AND COALESCE(content_role, 'main') != 'special'",
            (sib, f"{sib}/%", media_root),
        )
        cnt_row = await cnt_cur.fetchone()
        cnt = int(cnt_row["cnt"]) if cnt_row else 0

        if cnt > 0:
            cumulative_offset += cnt

            # 4. Pick target TMDB season from the first matched sibling
            if target_season is None:
                s_cur = await db.execute(
                    "SELECT tmdb_season FROM movies "
                    "WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=? "
                    "AND tmdb_season IS NOT NULL "
                    "AND COALESCE(content_role, 'main') != 'special' LIMIT 1",
                    (sib, f"{sib}/%", media_root),
                )
                s_row = await s_cur.fetchone()
                if s_row:
                    target_season = int(s_row["tmdb_season"])

    if target_season is None or cumulative_offset == 0:
        return 0

    # 5. Fetch the target season's TMDB episode list
    season_data = await fetch_tv_season(series_id, target_season, lang)
    if not season_data or not season_data.get("episodes"):
        return 0

    # 6. Get local movies in the current (unmatched) folder
    cur = await db.execute(
        "SELECT id, path, code FROM movies "
        "WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=? "
        "AND COALESCE(content_role, 'main') != 'special'",
        (folder_levels, f"{folder_levels}/%", media_root),
    )
    movies = await cur.fetchall()

    # 7. Match local episodes with offset against TMDB episodes
    ep_pattern = re.compile(
        r'\[(\d{1,4})\](?=\[[^\]]+\])'
        r'|[eE][pP]?\s*(\d{1,4})'
        r'|[-_. ](\d{1,4})(?:[\.\-_\s]|$)'
        r'|第\s*(\d{1,4})\s*[集話话]'
        r'|^(\d{1,4})[\s._-]'
        r'|[#＃](\d{1,4})'
        r'|[Nn]o\.?\s*(\d{1,4})'
    )

    updated = 0
    for m in movies:
        filename = Path(m["path"]).stem
        ep_num = extract_episode_number(filename)
        match = ep_pattern.search(filename)
        if ep_num is None and match:
            ep_num = int(next(g for g in match.groups() if g))

        if ep_num is None:
            continue

        adjusted_ep = ep_num + cumulative_offset

        for ep in season_data["episodes"]:
            if ep["episode_number"] == adjusted_ep:
                still_local = None
                if ep.get("still_path"):
                    try:
                        from .covers import download_and_cache_still
                        import hashlib
                        sk = hashlib.md5(ep["still_path"].encode()).hexdigest()[:16]
                        still_local = await download_and_cache_still(ep["still_path"], sk)
                    except Exception:
                        pass

                await db.execute(
                    """UPDATE movies SET
                       tmdb_id=?, tmdb_type='tv', tmdb_season=?, tmdb_episode=?,
                       episode_title=COALESCE(NULLIF(?, ''), episode_title),
                       episode_overview=COALESCE(NULLIF(?, ''), episode_overview),
                       episode_still=COALESCE(NULLIF(?, ''), episode_still),
                       episode_still_local=COALESCE(NULLIF(?, ''), episode_still_local),
                       updated_at=datetime('now')
                       WHERE id=?""",
                    (int(series_id), target_season, adjusted_ep,
                     ep.get("name", ""), ep.get("overview", ""),
                     ep.get("still_path", ""), still_local or "",
                     m["id"]),
                )
                updated += 1
                break

    if updated:
        await db.commit()
        logger.info(
            f"  TMDB: season-merge matched {updated} episodes in '{folder_levels}' "
            f"→ S{target_season} (offset {cumulative_offset})"
        )

    return updated


# ─── TMDB Extended API ───


async def fetch_tmdb_images(tmdb_id: int, media_type: str, lang: str = "zh,null") -> dict | None:
    """Fetch posters, backdrops, logos for a movie or TV series."""
    if not _has_tmdb_auth():
        return None
    mt = media_type.lower()
    if mt not in {"movie", "tv"}:
        return None
    cache_key = f"images:{mt}:{tmdb_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/{mt}/{tmdb_id}/images", {"include_image_language": lang})
        data = resp.json()
        result = {
            "posters": [
                {"url": f"{IMAGE_BASE}/w500{p['file_path']}", "width": p.get("width"), "height": p.get("height"),
                 "language": p.get("iso_639_1"), "vote_count": p.get("vote_count"), "vote_average": p.get("vote_average")}
                for p in data.get("posters", []) if p.get("file_path")
            ],
            "backdrops": [
                {"url": f"{IMAGE_BASE}/w1280{b['file_path']}", "width": b.get("width"), "height": b.get("height"),
                 "language": b.get("iso_639_1"), "vote_count": b.get("vote_count"), "vote_average": b.get("vote_average")}
                for b in data.get("backdrops", []) if b.get("file_path")
            ],
            "logos": [
                {"url": f"{IMAGE_BASE}/w500{l['file_path']}", "width": l.get("width"), "height": l.get("height"),
                 "language": l.get("iso_639_1")}
                for l in data.get("logos", []) if l.get("file_path")
            ],
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB images error for {mt}/{tmdb_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB images error for {mt}/{tmdb_id}: {e}")
        return None


async def fetch_tmdb_videos(tmdb_id: int, media_type: str, lang: str = "zh-CN") -> dict | None:
    """Fetch videos (trailers, clips, behind-the-scenes) for a movie or TV series."""
    if not _has_tmdb_auth():
        return None
    mt = media_type.lower()
    if mt not in {"movie", "tv"}:
        return None
    cache_key = f"videos:{mt}:{tmdb_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/{mt}/{tmdb_id}/videos", {"language": lang})
        data = resp.json()
        result = {
            "results": [
                {"key": v.get("key"), "name": v.get("name"), "site": v.get("site"),
                 "type": v.get("type"), "size": v.get("size"), "official": v.get("official"),
                 "published_at": v.get("published_at")}
                for v in data.get("results", []) if v.get("key")
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB videos error for {mt}/{tmdb_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB videos error for {mt}/{tmdb_id}: {e}")
        return None


async def fetch_person_detail(person_id: int, lang: str = "zh-CN") -> dict | None:
    """Fetch person details including biography, birthday, external IDs."""
    if not _has_tmdb_auth():
        return None
    cache_key = f"person:{person_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/person/{person_id}", {
            "language": lang, "append_to_response": "external_ids"
        })
        data = resp.json()
        external = data.get("external_ids", {}) or {}
        result = {
            "id": data.get("id"),
            "name": data.get("name", ""),
            "biography": data.get("biography", ""),
            "birthday": data.get("birthday"),
            "deathday": data.get("deathday"),
            "place_of_birth": data.get("place_of_birth"),
            "homepage": data.get("homepage"),
            "profile_path": f"{IMAGE_BASE}/w300{data['profile_path']}" if data.get("profile_path") else None,
            "known_for_department": data.get("known_for_department"),
            "imdb_id": external.get("imdb_id"),
            "facebook_id": external.get("facebook_id"),
            "instagram_id": external.get("instagram_id"),
            "twitter_id": external.get("twitter_id"),
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB person detail error for {person_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB person detail error for {person_id}: {e}")
        return None


async def fetch_person_credits(person_id: int, lang: str = "zh-CN") -> dict | None:
    """Fetch combined credits (movie + tv) for a person."""
    if not _has_tmdb_auth():
        return None
    cache_key = f"person_credits:{person_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/person/{person_id}/combined_credits", {"language": lang})
        data = resp.json()
        def _format_credit(item):
            poster = f"{IMAGE_BASE}/w300{item['poster_path']}" if item.get("poster_path") else None
            return {
                "id": item.get("id"),
                "title": item.get("title") or item.get("name", ""),
                "media_type": item.get("media_type"),
                "character": item.get("character"),
                "job": item.get("job"),
                "release_date": item.get("release_date") or item.get("first_air_date"),
                "poster_url": poster,
                "vote_average": item.get("vote_average"),
                "overview": item.get("overview", ""),
            }
        result = {
            "cast": [_format_credit(c) for c in data.get("cast", [])],
            "crew": [_format_credit(c) for c in data.get("crew", [])],
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB person credits error for {person_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB person credits error for {person_id}: {e}")
        return None


async def fetch_person_images(person_id: int) -> dict | None:
    """Fetch profile images for a person."""
    if not _has_tmdb_auth():
        return None
    cache_key = f"person_images:{person_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/person/{person_id}/images")
        data = resp.json()
        result = {
            "profiles": [
                {"url": f"{IMAGE_BASE}/w300{p['file_path']}", "width": p.get("width"),
                 "height": p.get("height"), "vote_count": p.get("vote_count")}
                for p in data.get("profiles", []) if p.get("file_path")
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB person images error for {person_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB person images error for {person_id}: {e}")
        return None


async def fetch_tmdb_reviews(tmdb_id: int, media_type: str, page: int = 1, lang: str = "en-US") -> dict | None:
    """Fetch user reviews for a movie or TV series."""
    if not _has_tmdb_auth():
        return None
    mt = media_type.lower()
    if mt not in {"movie", "tv"}:
        return None
    cache_key = f"reviews:{mt}:{tmdb_id}:{page}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/{mt}/{tmdb_id}/reviews", {"language": lang, "page": page})
        data = resp.json()
        result = {
            "page": data.get("page"),
            "total_pages": data.get("total_pages"),
            "total_results": data.get("total_results"),
            "results": [
                {
                    "id": r.get("id"),
                    "author": r.get("author"),
                    "author_details": r.get("author_details"),
                    "content": r.get("content"),
                    "created_at": r.get("created_at"),
                    "url": r.get("url"),
                }
                for r in data.get("results", [])
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB reviews error for {mt}/{tmdb_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB reviews error for {mt}/{tmdb_id}: {e}")
        return None


async def fetch_tmdb_keywords(tmdb_id: int, media_type: str) -> dict | None:
    """Fetch keyword list for a movie or TV series."""
    if not _has_tmdb_auth():
        return None
    mt = media_type.lower()
    if mt not in {"movie", "tv"}:
        return None
    cache_key = f"keywords:{mt}:{tmdb_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/{mt}/{tmdb_id}/keywords")
        data = resp.json()
        kw_list = data.get("keywords") or data.get("results") or []
        result = {
            "keywords": [
                {"id": k.get("id"), "name": k.get("name")}
                for k in kw_list if k.get("name")
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB keywords error for {mt}/{tmdb_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB keywords error for {mt}/{tmdb_id}: {e}")
        return None


async def fetch_release_dates(tmdb_id: int) -> dict | None:
    """Fetch release dates and certifications by country for a movie."""
    if not _has_tmdb_auth():
        return None
    cache_key = f"release_dates:{tmdb_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/movie/{tmdb_id}/release_dates")
        data = resp.json()
        result = {
            "results": [
                {
                    "iso_3166_1": r.get("iso_3166_1"),
                    "release_dates": [
                        {
                            "certification": d.get("certification"),
                            "release_date": d.get("release_date"),
                            "type": d.get("type"),
                            "note": d.get("note"),
                        }
                        for d in r.get("release_dates", [])
                    ]
                }
                for r in data.get("results", [])
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB release dates error for movie/{tmdb_id}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB release dates error for movie/{tmdb_id}: {e}")
        return None


async def fetch_season_images(series_id: int, season_num: int, lang: str = "zh,null") -> dict | None:
    """Fetch poster images for a TV season."""
    if not _has_tmdb_auth():
        return None
    cache_key = f"season_images:{series_id}:{season_num}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/tv/{series_id}/season/{season_num}/images", {"include_image_language": lang})
        data = resp.json()
        result = {
            "posters": [
                {"url": f"{IMAGE_BASE}/w500{p['file_path']}", "width": p.get("width"),
                 "height": p.get("height"), "language": p.get("iso_639_1"),
                 "vote_count": p.get("vote_count"), "vote_average": p.get("vote_average")}
                for p in data.get("posters", []) if p.get("file_path")
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB season images error for tv/{series_id}/season/{season_num}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB season images error for tv/{series_id}/season/{season_num}: {e}")
        return None


async def fetch_episode_images(series_id: int, season_num: int, ep_num: int, lang: str = "zh,null") -> dict | None:
    """Fetch still images for a TV episode."""
    if not _has_tmdb_auth():
        return None
    cache_key = f"episode_images:{series_id}:{season_num}:{ep_num}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        return cache_data
    try:
        resp = await _tmdb_get(f"/tv/{series_id}/season/{season_num}/episode/{ep_num}/images", {"include_image_language": lang})
        data = resp.json()
        result = {
            "stills": [
                {"url": f"{IMAGE_BASE}/w300{s['file_path']}", "width": s.get("width"),
                 "height": s.get("height"), "vote_count": s.get("vote_count"),
                 "vote_average": s.get("vote_average")}
                for s in data.get("stills", []) if s.get("file_path")
            ]
        }
        await set_scraper_cache("tmdb", cache_key, result)
        return result
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"TMDB episode images error for tv/{series_id}/S{season_num}E{ep_num}: status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"TMDB episode images error for tv/{series_id}/S{season_num}E{ep_num}: {e}")
        return None
