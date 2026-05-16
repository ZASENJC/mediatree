import httpx
from .config import settings, logger
from .database import get_scraper_cache, set_scraper_cache

TMDB_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


def _get_tmdb_headers() -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if settings.tmdb_access_token:
        h["Authorization"] = f"Bearer {settings.tmdb_access_token}"
    return h


def _has_tmdb_auth() -> bool:
    return bool(settings.tmdb_access_token) or bool(settings.tmdb_api_key)


async def _tmdb_get(path: str, params: dict | None = None) -> httpx.Response:
    client = httpx.AsyncClient(timeout=20, follow_redirects=True)
    try:
        url = f"{TMDB_BASE}{path}"
        headers = _get_tmdb_headers()
        if params is None:
            params = {}
        if not headers.get("Authorization") and settings.tmdb_api_key:
            params["api_key"] = settings.tmdb_api_key
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp
    finally:
        await client.aclose()


async def search_tmdb(query: str, lang: str = "zh-CN") -> list[dict]:
    if not _has_tmdb_auth():
        return []
    cache_data = await get_scraper_cache("tmdb", f"search:{query}", 168)
    if cache_data is not None:
        return cache_data

    results = []
    try:
        for mtype in ("movie", "tv"):
            resp = await _tmdb_get(f"/search/{mtype}", {"query": query, "language": lang})
            data = resp.json()
            for item in data.get("results", [])[:5]:
                poster = None
                if item.get("poster_path"):
                    poster = f"{IMAGE_BASE}/w500{item['poster_path']}"
                results.append({
                    "source": "tmdb",
                    "source_id": str(item["id"]),
                    "media_type": mtype,
                    "title": item.get("title") or item.get("name") or query,
                    "original_title": item.get("original_title") or item.get("original_name", ""),
                    "overview": item.get("overview", ""),
                    "poster_url": poster,
                    "release_date": item.get("release_date") or item.get("first_air_date"),
                    "score": item.get("vote_average"),
                    "votes": item.get("vote_count"),
                    "genre_ids": item.get("genre_ids", []),
                })
    except Exception as e:
        logger.warning(f"TMDB search error for '{query}': {e}")

    await set_scraper_cache("tmdb", f"search:{query}", results)
    return results


async def fetch_tmdb_detail(source_id: str, media_type: str, lang: str = "zh-CN") -> dict | None:
    if not _has_tmdb_auth():
        return None
    cache_data = await get_scraper_cache("tmdb", f"detail:{source_id}", 168)
    if cache_data is not None:
        return cache_data

    try:
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
            "imdb_id": external.get("imdb_id"),
            "seasons": seasons,
            "number_of_seasons": data.get("number_of_seasons", 0),
            "number_of_episodes": data.get("number_of_episodes", 0),
        }
        await set_scraper_cache("tmdb", f"detail:{source_id}", result)
        return result
    except Exception as e:
        logger.warning(f"TMDB detail error for {source_id}: {e}")
        return None


async def fetch_tv_season(series_id: str, season_number: int, lang: str = "zh-CN") -> dict | None:
    if not _has_tmdb_auth():
        return None
    cache_key = f"season:{series_id}:{season_number}"
    cache_data = await get_scraper_cache("tmdb", cache_key, 168)
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
    cache_data = await get_scraper_cache("tmdb", cache_key, 168)
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
    from pathlib import Path
    import re

    season_data = await fetch_tv_season(series_id, season_number, lang)
    if not season_data or not season_data.get("episodes"):
        return 0

    db = await get_db()
    cur = await db.execute(
        "SELECT id, path, code FROM movies WHERE folder_levels=? AND media_root=?",
        (folder_levels, media_root)
    )
    movies = await cur.fetchall()

    updated = 0
    ep_pattern = re.compile(
        r'[eE][pP]?\s*(\d{1,4})'           # E01, Ep01, EP 01
        r'|[-_. ](\d{1,3})(?:[\.\-_\s]|$)'  # -01, _01, .01,  01
        r'|第\s*(\d{1,4})\s*[集話话]'        # 第01集, 第01话
        r'|^(\d{1,4})[\s._-]'               # 01.mkv (number at start)
        r'|[#＃](\d{1,4})'                   # #01, ＃01
        r'|[Nn]o\.?\s*(\d{1,4})'            # No.01, no01
    )

    for m in movies:
        filename = Path(m["path"]).stem
        ep_num = None
        match = ep_pattern.search(filename)
        if match:
            ep_num = int(match.group(1) or match.group(2) or match.group(3) or match.group(4) or match.group(5) or match.group(6))

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
                       title=COALESCE(NULLIF(?, ''), title),
                       updated_at=datetime('now')
                       WHERE id=?""",
                    (int(series_id), season_number, ep_num,
                     ep.get("name", ""), ep.get("overview", ""),
                     ep.get("still_path", ""), still_local or "",
                     ep.get("name", ""), m["id"])
                )
                updated += 1
                break
    await db.commit()
    return updated
