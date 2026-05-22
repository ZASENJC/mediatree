from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ScrapeCandidate:
    source: str
    source_id: str
    title: str
    original_title: str | None = None
    year: int | None = None
    media_type: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    overview: str | None = None
    score: float | None = None
    raw: dict | None = None


@dataclass
class ScrapeStaff:
    name: str
    role: str | None = None
    job: str | None = None
    department: str | None = None
    person_id: str | None = None
    profile_path: str | None = None
    source: str | None = None


@dataclass
class ScrapeResult:
    source: str
    source_id: str
    title: str
    original_title: str | None = None
    sort_title: str | None = None
    year: int | None = None
    media_type: str | None = None
    overview: str | None = None

    cover_url: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    thumbnail_url: str | None = None
    still_url: str | None = None

    cast: list[ScrapeStaff] = field(default_factory=list)
    crew: list[ScrapeStaff] = field(default_factory=list)
    studios: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    tmdb_id: str | None = None
    bangumi_id: str | None = None
    javdb_id: str | None = None

    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None
    episode_still_url: str | None = None

    raw: dict | None = None


@dataclass
class ScraperInfo:
    name: str
    label: str
    description: str
    supported_media_types: list[str]
    requires_api_key: bool
    enabled: bool


_task_cache: dict[tuple[Any, ...], asyncio.Task] = {}
_task_cache_lock = asyncio.Lock()
_MAX_TASK_CACHE_SIZE = 256


class BaseScraper:
    name: str = ""
    label: str = ""
    description: str = ""
    supported_media_types: set[str] = set()
    requires_api_key: bool = False
    enabled: bool = True

    async def search(
        self,
        query: str,
        *,
        media_type: str | None = None,
        limit: int = 10,
    ) -> list[ScrapeCandidate]:
        raise NotImplementedError

    async def get_detail(
        self,
        source_id: str,
        *,
        media_type: str | None = None,
    ) -> ScrapeResult | None:
        raise NotImplementedError

    async def scrape(
        self,
        query: str,
        *,
        media_type: str | None = None,
    ) -> ScrapeResult | None:
        candidates = await self.search(query, media_type=media_type, limit=1)
        if not candidates:
            return None
        candidate = candidates[0]
        return await self.get_detail(
            candidate.source_id,
            media_type=candidate.media_type or media_type,
        )

    async def full_scrape(
        self,
        search_name: str,
        *,
        code: str = "",
        candidate_names: list[str] | None = None,
        movie: dict | None = None,
    ) -> dict | None:
        """Full scrape with context-aware fallback logic.

        Subclasses override this to implement their complete fallback chain.
        Returns a legacy dict for compatibility with _apply_scraped_data().

        Default: simple search-and-match via scrape(), no cross-source fallback.
        """
        from ..title_match import build_search_queries, candidate_title_matches
        from .utils import scrape_result_to_legacy

        queries = build_search_queries(search_name, candidate_names or [search_name, code])
        for query in queries:
            if not query:
                continue
            result = await self.scrape(query)
            if result and result.title:
                return scrape_result_to_legacy(result)
        return None

    def normalize_result(self, raw: dict) -> ScrapeResult:
        raise NotImplementedError

    async def cached_task(
        self,
        key_parts: tuple[Any, ...],
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        key = (self.name, *key_parts)
        async with _task_cache_lock:
            task = _task_cache.get(key)
            if task is None or task.done():
                task = asyncio.create_task(factory())
                _task_cache[key] = task
                if len(_task_cache) > _MAX_TASK_CACHE_SIZE:
                    done = [k for k, v in _task_cache.items() if v.done()]
                    for k in done:
                        del _task_cache[k]
        try:
            return await task
        finally:
            if task.done():
                async with _task_cache_lock:
                    if _task_cache.get(key) is task:
                        _task_cache.pop(key, None)

    def info(self) -> ScraperInfo:
        return ScraperInfo(
            name=self.name,
            label=self.label,
            description=self.description,
            supported_media_types=sorted(self.supported_media_types),
            requires_api_key=self.requires_api_key,
            enabled=self.enabled,
        )


def parse_year(value: Any) -> int | None:
    text = str(value or "")
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def staff_from_dict(data: dict, *, source: str) -> ScrapeStaff:
    return ScrapeStaff(
        name=str(data.get("name") or "").strip(),
        role=data.get("role") or data.get("character") or None,
        job=data.get("job") or None,
        department=data.get("department") or None,
        person_id=str(data.get("id") or data.get("person_id") or "") or None,
        profile_path=data.get("profile_path") or None,
        source=data.get("source") or source,
    )


def compact_staff(items: list[dict], *, source: str) -> list[ScrapeStaff]:
    staff = [staff_from_dict(item, source=source) for item in items if isinstance(item, dict)]
    return [item for item in staff if item.name]
