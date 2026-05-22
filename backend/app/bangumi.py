import re
import asyncio
from html import unescape
import httpx
from .config import settings, logger
from .database import get_scraper_cache, set_scraper_cache

BANGUMI_BASE = "https://api.bgm.tv"
_bangumi_client: httpx.AsyncClient | None = None
_bangumi_semaphore = asyncio.Semaphore(max(1, settings.scraper_api_concurrency))

_TYPE_LABELS = {1: "书籍", 2: "动画", 3: "音乐", 4: "游戏", 6: "剧集"}


async def _get_bangumi_client() -> httpx.AsyncClient:
    global _bangumi_client
    if _bangumi_client is not None and not _bangumi_client.is_closed:
        return _bangumi_client
    headers = {
        "User-Agent": "MediaTree/1.5 (https://github.com/mediatree)",
        "Accept": "application/json",
    }
    _bangumi_client = httpx.AsyncClient(
        headers=headers,
        timeout=settings.scraper_http_timeout,
        follow_redirects=True,
    )
    return _bangumi_client


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _bangumi_staff_from_infobox(infobox) -> tuple[list[dict], list[dict]]:
    cast: list[dict] = []
    crew: list[dict] = []
    if not isinstance(infobox, list):
        return cast, crew
    cast_keys = {"声优", "主演", "演员", "Cast"}
    crew_map = {
        "导演": "Director",
        "监督": "Supervisor",
        "系列导演": "Series Director",
        "动画监督": "Animation Director",
        "脚本": "Writer",
        "编剧": "Writer",
        "原作": "Original Creator",
        "制作": "Studio",
        "动画制作": "Studio",
    }
    for item in infobox:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        val = item.get("value")
        values = val if isinstance(val, list) else [val]
        names: list[str] = []
        for v in values:
            if isinstance(v, dict):
                name = v.get("v") or v.get("name")
            else:
                name = v
            name = str(name or "").strip()
            if name:
                names.append(name)
        if key in cast_keys:
            cast.extend({"name": n, "role": "", "source": "bangumi"} for n in names)
        elif key in crew_map:
            crew.extend({"name": n, "job": crew_map[key], "department": key, "source": "bangumi"} for n in names)
    return cast[:30], crew[:30]


async def search_bangumi(query: str, lang: str = "", bangumi_type: str | None = None) -> list[dict]:
    type_label = bangumi_type if bangumi_type else "all"
    cache_key = f"bangumi_search:type{type_label}:{query}"
    cache_data = await get_scraper_cache("bangumi", cache_key, settings.bangumi_cache_hours)
    if cache_data is not None:
        logger.info(f"Bangumi cache hit: {cache_key}")
        return cache_data

    results = []
    try:
        client = await _get_bangumi_client()
        url = f"{BANGUMI_BASE}/search/subject/{query}"
        params = {"responseGroup": "large"}
        if bangumi_type is not None:
            params["type"] = bangumi_type
        logger.info(f"Bangumi search endpoint: /search/subject query='{query}' type={bangumi_type or 'all'}")
        async with _bangumi_semaphore:
            resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("list", [])[:5]:
            images = item.get("images", {})
            poster = images.get("large") or images.get("common") or images.get("medium")
            rating = item.get("rating", {})
            results.append({
                "source": "bangumi",
                "source_id": str(item["id"]),
                "media_type": str(item.get("type", 0)),
                "type_label": _TYPE_LABELS.get(item.get("type", 0), ""),
                "title": item.get("name_cn") or item.get("name", query),
                "original_title": item.get("name", ""),
                "overview": _clean_html(item.get("summary", "")),
                "poster_url": poster,
                "release_date": item.get("air_date"),
                "score": rating.get("score"),
                "votes": rating.get("total"),
                "eps": item.get("eps_count") or item.get("eps"),
                "bgm_url": item.get("url"),
                "raw": item,
            })
    except httpx.HTTPStatusError as e:
        logger.warning(f"Bangumi search HTTP error for '{query}': status={e.response.status_code}")
    except Exception as e:
        logger.warning(f"Bangumi search error for '{query}': {e}")

    await set_scraper_cache("bangumi", cache_key, results)
    return results


async def fetch_bangumi_detail(source_id: str) -> dict | None:
    cache_key = f"bangumi_detail:anime:{source_id}"
    cache_data = await get_scraper_cache("bangumi", cache_key, settings.bangumi_cache_hours)
    if cache_data is not None:
        logger.info(f"Bangumi cache hit: {cache_key}")
        return cache_data

    try:
        client = await _get_bangumi_client()
        url = f"{BANGUMI_BASE}/v0/subjects/{source_id}"
        logger.info(f"Bangumi detail endpoint: /v0/subjects/{source_id}")
        async with _bangumi_semaphore:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images", {})
        poster = images.get("large") or images.get("common") or images.get("medium")
        rating = data.get("rating", {})
        collection = data.get("collection", {})

        tags = [t["name"] for t in data.get("tags", [])[:10]]
        cast, crew = _bangumi_staff_from_infobox(data.get("infobox"))

        result = {
            "source": "bangumi",
            "source_id": source_id,
            "media_type": str(data.get("type", 0)),
            "type_label": _TYPE_LABELS.get(data.get("type", 0), ""),
            "title": data.get("name_cn") or data.get("name", ""),
            "original_title": data.get("name", ""),
            "overview": _clean_html(data.get("summary", "")),
            "poster_url": poster,
            "release_date": data.get("date"),
            "platform": data.get("platform"),
            "eps": data.get("total_episodes") or data.get("eps", 0),
            "score": rating.get("score"),
            "votes": rating.get("total"),
            "genre": ", ".join(tags) if tags else None,
            "bgm_url": f"https://bgm.tv/subject/{source_id}",
            "collection_total": collection.get("collect", 0),
            "cast": cast,
            "crew": crew,
            "raw": data,
        }
        await set_scraper_cache("bangumi", cache_key, result)
        return result
    except httpx.HTTPStatusError as e:
        logger.warning(f"Bangumi detail HTTP error for {source_id}: status={e.response.status_code}")
    except Exception as e:
        logger.warning(f"Bangumi detail error for {source_id}: {e}")
        return None
