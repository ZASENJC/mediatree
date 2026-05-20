from __future__ import annotations

import json
import re

from ..config import settings
from ..database import get_scraper_cache, set_scraper_cache
from .base import BaseScraper, ScrapeCandidate, ScrapeResult, ScrapeStaff, parse_year


class JavdatabaseScraper(BaseScraper):
    name = "javdatabase"
    label = "Javdatabase"
    description = "Javdatabase code-based JAV scraper"
    supported_media_types = {"movie", "jav"}
    requires_api_key = False

    async def search(
        self,
        query: str,
        *,
        media_type: str | None = None,
        limit: int = 10,
    ) -> list[ScrapeCandidate]:
        async def _run() -> list[ScrapeCandidate]:
            raw = await self._fetch_raw(query)
            if not raw or not raw.get("title"):
                return []
            result = self.normalize_result(raw)
            return [
                ScrapeCandidate(
                    source=self.name,
                    source_id=result.source_id,
                    title=result.title,
                    original_title=result.original_title,
                    year=result.year,
                    media_type="movie",
                    poster_url=result.poster_url,
                    overview=result.overview,
                    raw=raw,
                )
            ][:limit]

        return await self.cached_task(("search", query, limit), _run)

    async def get_detail(
        self,
        source_id: str,
        *,
        media_type: str | None = None,
    ) -> ScrapeResult | None:
        async def _run() -> ScrapeResult | None:
            raw = await self._fetch_raw(source_id)
            if not raw or not raw.get("title"):
                return None
            return self.normalize_result(raw)

        return await self.cached_task(("detail", str(source_id)), _run)

    def normalize_result(self, raw: dict) -> ScrapeResult:
        source_id = str(raw.get("dvd_id") or raw.get("source_id") or "")
        cover = raw.get("cover_remote")
        thumbs = _load_thumbnails(raw.get("javdb_thumbnails"))
        comments = raw.get("javdb_comments") or []
        if isinstance(comments, str):
            comments = [comments]
        overview = raw.get("overview") or next((c for c in comments if c), "")
        cast = [
            ScrapeStaff(name=name.strip(), role="", source=self.name)
            for name in re.split(r"[,，、/]", raw.get("actress", "") or "")
            if name.strip()
        ]
        crew = []
        if raw.get("director"):
            crew.append(ScrapeStaff(name=raw["director"], job="Director", source=self.name))
        if raw.get("studio"):
            crew.append(ScrapeStaff(name=raw["studio"], job="Studio", source=self.name))
        genres = [g.strip() for g in str(raw.get("genre") or "").split(",") if g.strip()]
        return ScrapeResult(
            source=self.name,
            source_id=source_id,
            title=raw.get("title") or "",
            original_title=raw.get("original_title") or raw.get("title") or None,
            year=parse_year(raw.get("release_date")),
            media_type="movie",
            overview=overview or None,
            cover_url=cover,
            poster_url=cover,
            thumbnail_url=thumbs[0] if thumbs else cover,
            still_url=thumbs[0] if thumbs else None,
            cast=cast,
            crew=crew,
            studios=[raw["studio"]] if raw.get("studio") else [],
            genres=genres,
            javdb_id=source_id,
            raw=raw,
        )

    async def _fetch_raw(self, code: str) -> dict | None:
        code = (code or "").strip()
        if not code:
            return None
        cache_key = f"javdb_search:code:{code}"
        cached = await get_scraper_cache(self.name, cache_key, settings.javdb_cache_hours)
        if cached is not None:
            return cached or None

        from ..javdb import search_javdb

        data = await search_javdb(code)
        if data is not None:
            data.setdefault("source_id", code)
            data.setdefault("dvd_id", code)
        await set_scraper_cache(self.name, cache_key, data or {})
        return data


def _load_thumbnails(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(v) for v in data if v]
    except (json.JSONDecodeError, TypeError):
        return []
    return []
