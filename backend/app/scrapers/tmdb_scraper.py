from __future__ import annotations

from typing import Literal

from .base import BaseScraper, ScrapeCandidate, ScrapeResult, compact_staff, parse_year
from .utils import scrape_result_to_legacy


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

    async def full_scrape(
        self,
        search_name: str,
        *,
        code: str = "",
        candidate_names: list[str] | None = None,
        movie: dict | None = None,
    ) -> dict | None:
        """TMDB scraper fallback chain: TMDB ID exact → Bangumi → TMDB title search."""
        from ..config import settings, logger
        from ..title_match import (
            clean_search_title, build_search_queries, candidate_title_matches,
            _first_tmdb_token, _is_specific_search_query,
        )
        from .registry import get_scraper

        media_type = self.media_type  # "movie" or "tv"
        scraper_name = self.name
        candidates = candidate_names or [search_name, code]
        token = _first_tmdb_token(candidates)
        clean_title = clean_search_title(search_name, candidates)
        existing_tmdb_id = str((movie or {}).get("tmdb_id") or "").strip()
        existing_tmdb_type = str((movie or {}).get("tmdb_type") or "").strip()

        if not token and existing_tmdb_id and (not existing_tmdb_type or existing_tmdb_type == media_type):
            try:
                # Import lazily to avoid circular deps
                from ..title_match import TmdbIdToken
                token = TmdbIdToken(int(existing_tmdb_id), media_type, existing_tmdb_id, f"{media_type}.tmdb_id", "explicit")
            except ValueError:
                logger.warning(f"  {scraper_name}: invalid stored tmdb_id='{existing_tmdb_id}', fallback to title search")

        logger.info(
            f"  {scraper_name}: raw_title='{search_name}' clean_title='{clean_title}' "
            f"tmdb_token={'yes' if token else 'no'}"
        )

        # Step 1: TMDB ID exact match
        if token:
            logger.info(
                f"  {scraper_name}: detected tmdbid={token.id} from {token.source_name}; "
                f"using /{media_type}/{token.id}"
            )
            if settings.tmdb_api_key or settings.tmdb_access_token:
                result = await self.get_detail(str(token.id))
                if result and result.title:
                    logger.info(f"  {scraper_name}: TMDB ID exact match success /{media_type}/{token.id}")
                    return scrape_result_to_legacy(result, exact=True)
                logger.warning("  TMDB ID 精确匹配失败，fallback 到标题搜索")
            else:
                logger.warning(f"  {scraper_name}: TMDB credentials not configured, fallback to title search")

        if not clean_title:
            logger.info(f"  {scraper_name}: no clean title after TMDB ID fallback, cannot run search APIs")
            return None

        # Step 2: Bangumi fallback
        logger.info(f"  {scraper_name}: sequential fallback to Bangumi for '{clean_title}'")
        try:
            bangumi_scraper = get_scraper("bangumi")
            data = await bangumi_scraper.full_scrape(clean_title, code=code)
            if data and data.get("title"):
                logger.info(f"  {scraper_name}: sequential fallback Bangumi success for '{clean_title}'")
                return data
        except Exception as e:
            logger.warning(f"  {scraper_name}: Bangumi fallback error: {e}")

        # Step 3: TMDB title search
        logger.info(f"  {scraper_name}: sequential fallback to TMDB {media_type} title search for '{clean_title}'")
        data = await tmdb_title_search(clean_title, search_name, code, media_type)
        if data and data.get("title"):
            logger.info(f"  {scraper_name}: sequential fallback TMDB title search success for '{clean_title}'")
            return data

        logger.info(f"  {scraper_name}: all sequential fallbacks failed for '{clean_title}'")
        return None

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


async def tmdb_title_search(
    clean_title: str,
    folder_name: str,
    code: str,
    media_type: Literal["movie", "tv"] | None = None,
) -> dict | None:
    """Shared TMDB title search logic (no cross-source fallback). Used by chain handlers."""
    from ..config import settings, logger
    from ..title_match import build_search_queries, candidate_title_matches, _is_specific_search_query
    from .registry import get_scraper
    from .utils import scrape_result_to_legacy

    scope = media_type or "movie+tv"
    if not settings.tmdb_api_key and not settings.tmdb_access_token:
        logger.warning(f"  TMDB {scope}: API key/access token missing, cannot search clean_title='{clean_title}'")
        return None

    queries = build_search_queries(clean_title, [folder_name, code])
    best: ScrapeCandidate | None = None
    scraper_names = ["tmdb_tv" if media_type == "tv" else "tmdb_movie"] if media_type else ["tmdb_movie", "tmdb_tv"]
    failures: list[str] = []
    primary_query = queries[0] if queries else clean_title

    for query in queries:
        if not query:
            continue
        for sname in scraper_names:
            endpoint_type = "tv" if sname == "tmdb_tv" else "movie"
            api_type = "tmdb_search_tv" if endpoint_type == "tv" else "tmdb_search_movie"
            logger.info(
                f"  fallback step={api_type} raw_title='{folder_name}' clean_title='{clean_title}' "
                f"query='{query}' cache_key='tmdb_search:{endpoint_type}:{query}'"
            )
            try:
                tmdb_scraper = get_scraper(sname)
                results = await tmdb_scraper.search(query, media_type=media_type, limit=5)
            except Exception as e:
                logger.warning(f"  {api_type}: search error for '{query}': {e}")
                failures.append(f"{sname}:{query}: error")
                continue
            logger.info(f"  {api_type}: candidates={len(results)} query='{query}'")
            if not results:
                failures.append(f"{sname}:{query}: no results")
                continue
            rejected = []
            for candidate in results[:3]:
                matched = candidate_title_matches(candidate, clean_title, query, code)
                if (
                    not matched
                    and query == primary_query
                    and len(results) <= 2
                    and _is_specific_search_query(query)
                ):
                    matched = True
                    logger.info(
                        f"  {api_type}: title_matches relaxed accept (candidates={len(results)}) "
                        f"query='{query}' source_id='{candidate.source_id}'"
                    )
                logger.info(
                    f"  {api_type}: title_matches={matched} source_id='{candidate.source_id}' "
                    f"title='{candidate.title}' original_title='{candidate.original_title or ''}'"
                )
                if matched:
                    best = candidate
                    break
                rejected.append(candidate.title)
            if not best:
                logger.info(
                    f"  {sname}: title_matches rejected query='{query}' "
                    f"candidates={rejected[:3]}"
                )
                failures.append(f"{sname}:{query}: title mismatch")
            if best:
                break
        if best:
            break

    if not best:
        logger.info(f"  TMDB {scope}: no match for clean_title='{clean_title}', failures={'; '.join(failures)}")
        return None

    logger.info(
        f"  TMDB {best.media_type}: selected source_id={best.source_id} "
        f"title='{best.title}' original_title='{best.original_title or ''}'"
    )

    try:
        detail_scraper = get_scraper("tmdb_tv" if best.media_type == "tv" else "tmdb_movie")
        result = await detail_scraper.get_detail(best.source_id, media_type=best.media_type)
    except Exception as e:
        logger.warning(f"  TMDB {scope}: detail error for {best.source_id}: {e}")
        return None

    if not result or not result.title:
        return None

    data = scrape_result_to_legacy(result, exact=False)
    data["_search_match_passed"] = True
    return data
