from __future__ import annotations

from .base import BaseScraper, ScrapeCandidate, ScrapeResult, parse_year


class TMDBCollectionScraper(BaseScraper):
    name = "tmdb_collection"
    label = "TMDB Collection"
    description = "The Movie Database collection scraper"
    supported_media_types = {"collection"}
    requires_api_key = True

    async def search(
        self,
        query: str,
        *,
        media_type: str | None = None,
        limit: int = 10,
    ) -> list[ScrapeCandidate]:
        async def _run() -> list[ScrapeCandidate]:
            from ..tmdb import search_tmdb_collections

            rows = await search_tmdb_collections(query)
            return [self._candidate_from_dict(row) for row in rows[:limit]]

        return await self.cached_task(("search", "collection", query, limit), _run)

    async def get_detail(
        self,
        source_id: str,
        *,
        media_type: str | None = None,
    ) -> ScrapeResult | None:
        async def _run() -> ScrapeResult | None:
            from ..tmdb import fetch_tmdb_collection_detail

            detail = await fetch_tmdb_collection_detail(str(source_id))
            if not detail:
                return None
            return self.normalize_result(detail)

        return await self.cached_task(("detail", "collection", str(source_id)), _run)

    def normalize_result(self, raw: dict) -> ScrapeResult:
        poster = raw.get("poster_url") or raw.get("cover_url")
        backdrop = raw.get("backdrop_url")
        source_id = str(raw.get("source_id") or raw.get("id") or "")
        return ScrapeResult(
            source=self.name,
            source_id=source_id,
            title=raw.get("title") or raw.get("name") or "",
            original_title=raw.get("original_title") or raw.get("original_name") or None,
            year=parse_year(raw.get("release_date")),
            media_type="collection",
            overview=raw.get("overview") or None,
            cover_url=poster,
            poster_url=poster,
            backdrop_url=backdrop,
            thumbnail_url=backdrop or poster,
            raw=raw,
        )

    @staticmethod
    def _candidate_from_dict(raw: dict) -> ScrapeCandidate:
        return ScrapeCandidate(
            source="tmdb_collection",
            source_id=str(raw.get("source_id") or raw.get("id") or ""),
            title=raw.get("title") or raw.get("name") or "",
            original_title=raw.get("original_title") or raw.get("original_name") or None,
            year=parse_year(raw.get("release_date")),
            media_type="collection",
            poster_url=raw.get("poster_url"),
            backdrop_url=raw.get("backdrop_url"),
            overview=raw.get("overview") or None,
            score=raw.get("score"),
            raw=raw,
        )
