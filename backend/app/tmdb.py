import httpx
import asyncio
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
    cache_key = f"tmdb_id:{media_type}:{source_id}"
    cache_data = await get_scraper_cache("tmdb", cache_key, settings.tmdb_cache_hours)
    if cache_data is not None:
        logger.info(f"TMDB cache hit: {cache_key}")
        return cache_data

    try:
        logger.info(f"TMDB detail endpoint: /{media_type}/{source_id}")
        resp = await _tmdb_get(
            f"/{media_type}/{source_id}",
            {"language": lang, "append_to_response": "credits,external_ids,keywords"}
        )
        data = resp.json()

        genres = [g["name"] for g in data.get("genres", [])]
        poster = f"{IMAGE_BASE}/w500{data['poster_path']}" if data.get("poster_path") else None
        backdrop = f"{IMAGE_BASE}/w1280{data['backdrop_path']}" if data.get("backdrop_path") else None

        cast = []
        for c in (data.get("credits", {}) or {}).get("cast", [])[:10]:
            cast.append({"name": c.get("name", ""), "character": c.get("character", ""),
                        "profile_path": f"{IMAGE_BASE}/w185{c['profile_path']}" if c.get("profile_path") else None})
        crew = []
        for c in (data.get("credits", {}) or {}).get("crew", [])[:5]:
            crew.append({"name": c.get("name", ""), "job": c.get("job", ""),
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
            "tagline": data.get("tagline"),
            "status": data.get("status"),
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

    cache_key = f"tmdb_id:{requested_type}:{tmdb_id}"
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
                               {"language": lang})
        data = resp.json()

        still = f"{IMAGE_BASE}/w300{data['still_path']}" if data.get("still_path") else None

        cast = []
        for c in (data.get("credits", {}) or {}).get("guest_stars", [])[:10]:
            cast.append({"name": c.get("name", ""), "character": c.get("character", ""),
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
        return 0

    db = await get_db()
    cur = await db.execute(
        "SELECT id, path, code FROM movies WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
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
                updated += 1
                break
    await db.commit()
    return updated
