import re
from html import unescape
import httpx
from .config import settings, logger
from .database import get_scraper_cache, set_scraper_cache

BANGUMI_BASE = "https://api.bgm.tv"

_TYPE_LABELS = {1: "书籍", 2: "动画", 3: "音乐", 4: "游戏", 6: "剧集"}


async def _get_bangumi_client() -> httpx.AsyncClient:
    headers = {
        "User-Agent": "MediaTree/1.5 (https://github.com/mediatree)",
        "Accept": "application/json",
    }
    return httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True)


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def search_bangumi(query: str, lang: str = "") -> list[dict]:
    bangumi_type = "2"
    cache_data = await get_scraper_cache("bangumi", f"search:{query}:{bangumi_type}", 168)
    if cache_data:
        return cache_data

    results = []
    try:
        client = await _get_bangumi_client()
        try:
            url = f"{BANGUMI_BASE}/search/subject/{query}"
            params = {"responseGroup": "large"}
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
                })
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning(f"Bangumi search error for '{query}': {e}")

    await set_scraper_cache("bangumi", f"search:{query}:{bangumi_type}", results)
    return results


async def fetch_bangumi_detail(source_id: str) -> dict | None:
    cache_data = await get_scraper_cache("bangumi", f"detail:{source_id}", 168)
    if cache_data:
        return cache_data

    try:
        client = await _get_bangumi_client()
        try:
            url = f"{BANGUMI_BASE}/v0/subjects/{source_id}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            images = data.get("images", {})
            poster = images.get("large") or images.get("common") or images.get("medium")
            rating = data.get("rating", {})
            collection = data.get("collection", {})

            tags = [t["name"] for t in data.get("tags", [])[:10]]

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
            }
            await set_scraper_cache("bangumi", f"detail:{source_id}", result)
            return result
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning(f"Bangumi detail error for {source_id}: {e}")
        return None
