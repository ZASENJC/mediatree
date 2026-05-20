from __future__ import annotations

from .base import BaseScraper, ScrapeCandidate, ScrapeResult, compact_staff, parse_year


class TMDBScraper(BaseScraper):
    requires_api_key = True

    def __init__(self, media_type: str):
        if media_type not in {"movie", "tv"}:
            raise ValueError("TMDB media_type must be movie or tv")
        self.media_type = media_type
        self.name = f"tmdb_{media_type}"
        self.label = "TMDB Movie" if media_type == "movie" else "TMDB TV"
        self.description = (
            "The Movie Database movie scraper"
            if media_type == "movie"
            else "The Movie Database TV scraper"
        )
        self.supported_media_types = {media_type}

    async def search(
        self,
        query: str,
        *,
        media_type: str | None = None,
        limit: int = 10,
    ) -> list[ScrapeCandidate]:
        target_type = self.media_type

        async def _run() -> list[ScrapeCandidate]:
            from ..tmdb import search_tmdb

            rows = await search_tmdb(query, media_type=target_type)
            return [self._candidate_from_dict(row) for row in rows[:limit]]

        return await self.cached_task(("search", target_type, query, limit), _run)

    async def get_detail(
        self,
        source_id: str,
        *,
        media_type: str | None = None,
    ) -> ScrapeResult | None:
        target_type = self.media_type

        async def _run() -> ScrapeResult | None:
            from ..tmdb import fetch_tmdb_detail

            detail = await fetch_tmdb_detail(str(source_id), target_type)
            if not detail:
                return None
            return self.normalize_result(detail)

        return await self.cached_task(("detail", target_type, str(source_id)), _run)

    def normalize_result(self, raw: dict) -> ScrapeResult:
        raw_media_type = raw.get("media_type") or self.media_type
        poster = raw.get("poster_url") or raw.get("cover_url")
        backdrop = raw.get("backdrop_url")
        genres = []
        if raw.get("genre"):
            genres = [g.strip() for g in str(raw["genre"]).split(",") if g.strip()]
        studios = raw.get("studios") if isinstance(raw.get("studios"), list) else []
        source_id = str(raw.get("source_id") or raw.get("tmdb_id") or "")
        return ScrapeResult(
            source="tmdb",
            source_id=source_id,
            title=raw.get("title") or "",
            original_title=raw.get("original_title") or None,
            year=parse_year(raw.get("release_date")),
            media_type=raw_media_type,
            overview=raw.get("overview") or None,
            cover_url=poster,
            poster_url=poster,
            backdrop_url=backdrop,
            thumbnail_url=backdrop or poster,
            cast=compact_staff(raw.get("cast") or [], source="tmdb"),
            crew=compact_staff(raw.get("crew") or [], source="tmdb"),
            studios=[str(s) for s in studios if s],
            genres=genres,
            tmdb_id=source_id,
            raw=raw,
        )

    @staticmethod
    def _candidate_from_dict(raw: dict) -> ScrapeCandidate:
        return ScrapeCandidate(
            source="tmdb",
            source_id=str(raw.get("source_id") or ""),
            title=raw.get("title") or "",
            original_title=raw.get("original_title") or None,
            year=parse_year(raw.get("release_date")),
            media_type=raw.get("media_type") or None,
            poster_url=raw.get("poster_url"),
            backdrop_url=raw.get("backdrop_url"),
            overview=raw.get("overview") or None,
            score=raw.get("score"),
            raw=raw,
        )
