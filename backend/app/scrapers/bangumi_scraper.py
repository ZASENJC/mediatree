from __future__ import annotations

from .base import BaseScraper, ScrapeCandidate, ScrapeResult, compact_staff, parse_year


class BangumiScraper(BaseScraper):
    name = "bangumi"
    label = "Bangumi"
    description = "Bangumi anime and TV scraper"
    supported_media_types = {"anime", "tv"}
    requires_api_key = False

    async def search(
        self,
        query: str,
        *,
        media_type: str | None = None,
        limit: int = 10,
    ) -> list[ScrapeCandidate]:
        async def _run() -> list[ScrapeCandidate]:
            from ..bangumi import search_bangumi

            rows = await search_bangumi(query)
            return [self._candidate_from_dict(row) for row in rows[:limit]]

        return await self.cached_task(("search", query, limit), _run)

    async def get_detail(
        self,
        source_id: str,
        *,
        media_type: str | None = None,
    ) -> ScrapeResult | None:
        async def _run() -> ScrapeResult | None:
            from ..bangumi import fetch_bangumi_detail

            detail = await fetch_bangumi_detail(str(source_id))
            if not detail:
                return None
            return self.normalize_result(detail)

        return await self.cached_task(("detail", str(source_id)), _run)

    def normalize_result(self, raw: dict) -> ScrapeResult:
        poster = raw.get("poster_url")
        genres = []
        if raw.get("genre"):
            genres = [g.strip() for g in str(raw["genre"]).split(",") if g.strip()]
        source_id = str(raw.get("source_id") or raw.get("bangumi_id") or "")
        return ScrapeResult(
            source="bangumi",
            source_id=source_id,
            title=raw.get("title") or "",
            original_title=raw.get("original_title") or None,
            year=parse_year(raw.get("release_date")),
            media_type="tv",
            overview=raw.get("overview") or None,
            cover_url=poster,
            poster_url=poster,
            thumbnail_url=poster,
            cast=compact_staff(raw.get("cast") or [], source="bangumi"),
            crew=compact_staff(raw.get("crew") or [], source="bangumi"),
            genres=genres,
            tags=genres,
            bangumi_id=source_id,
            raw=raw,
        )

    @staticmethod
    def _candidate_from_dict(raw: dict) -> ScrapeCandidate:
        return ScrapeCandidate(
            source="bangumi",
            source_id=str(raw.get("source_id") or ""),
            title=raw.get("title") or "",
            original_title=raw.get("original_title") or None,
            year=parse_year(raw.get("release_date")),
            media_type="tv",
            poster_url=raw.get("poster_url"),
            overview=raw.get("overview") or None,
            score=raw.get("score"),
            raw=raw,
        )
