from __future__ import annotations

from .base import BaseScraper, ScrapeCandidate, ScrapeResult, compact_staff, parse_year
from .utils import scrape_result_to_legacy


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
        bangumi_type: str | None = None,
    ) -> list[ScrapeCandidate]:
        async def _run() -> list[ScrapeCandidate]:
            from ..bangumi import search_bangumi

            rows = await search_bangumi(query, bangumi_type=bangumi_type)
            return [self._candidate_from_dict(row) for row in rows[:limit]]

        return await self.cached_task(("search", bangumi_type or "all", query, limit), _run)

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

    async def full_scrape(
        self,
        search_name: str,
        *,
        code: str = "",
        candidate_names: list[str] | None = None,
        movie: dict | None = None,
    ) -> dict | None:
        """Bangumi scraper: search Bangumi, match candidates, return detail."""
        from ..config import logger
        from ..title_match import (
            clean_search_title, build_search_queries, candidate_title_matches,
            _is_specific_search_query,
        )

        raw_title = search_name
        clean_title = clean_search_title(search_name, [code])
        if not clean_title:
            logger.info(f"  Bangumi: no clean title for raw_title='{raw_title}', skipping search")
            return None

        queries = build_search_queries(clean_title, [raw_title, code])
        best: ScrapeCandidate | None = None
        failures: list[str] = []
        primary_query = queries[0] if queries else clean_title
        seen_original_titles: set[str] = set()

        for query in queries:
            if not query:
                continue
            logger.info(
                f"  fallback step=bangumi_search raw_title='{raw_title}' clean_title='{clean_title}' "
                f"query='{query}'"
            )
            results = await self.search(query, limit=5)
            logger.info(f"  bangumi_search: candidates={len(results)} query='{query}'")
            if not results:
                failures.append(f"{query}: no results")
                continue
            rejected = []
            for candidate in results[:3]:
                if candidate.original_title:
                    seen_original_titles.add(candidate.original_title)
                matched = candidate_title_matches(candidate, clean_title, query, code)
                if (
                    not matched
                    and query == primary_query
                    and len(results) <= 2
                    and _is_specific_search_query(query)
                ):
                    matched = True
                    logger.info(
                        f"  bangumi_search: title_matches relaxed accept (candidates={len(results)}) "
                        f"query='{query}' source_id='{candidate.source_id}'"
                    )
                logger.info(
                    f"  bangumi_search: title_matches={matched} source_id='{candidate.source_id}' "
                    f"title='{candidate.title}' original_title='{candidate.original_title or ''}'"
                )
                if matched:
                    best = candidate
                    break
                rejected.append(candidate.title)
            if not best:
                failures.append(f"{query}: title mismatch {rejected[:3]}")
            if best:
                break

        if not best:
            # Fallback to live-action TV (type=6) if anime/all-type search failed
            logger.info(f"  Bangumi: anime/all search no match for '{clean_title}', trying live-action type=6")
            for query in queries:
                if not query:
                    continue
                logger.info(
                    f"  fallback step=bangumi_search_type6 raw_title='{raw_title}' "
                    f"clean_title='{clean_title}' query='{query}'"
                )
                results_type6 = await self.search(query, limit=5, bangumi_type="6")
                logger.info(f"  bangumi_search type=6: candidates={len(results_type6)} query='{query}'")
                if not results_type6:
                    continue
                for candidate in results_type6[:3]:
                    matched = candidate_title_matches(candidate, clean_title, query, code)
                    if (
                        not matched
                        and query == primary_query
                        and len(results_type6) <= 2
                        and _is_specific_search_query(query)
                    ):
                        matched = True
                        logger.info(
                            f"  bangumi_search type=6: relaxed accept "
                            f"query='{query}' source_id='{candidate.source_id}'"
                        )
                    logger.info(
                        f"  bangumi_search type=6: title_matches={matched} "
                        f"source_id='{candidate.source_id}' title='{candidate.title}'"
                    )
                    if matched:
                        best = candidate
                        break
                if best:
                    break

        if not best:
            # Alias fallback: re-search with original titles from primary candidates
            existing_queries = set(q.lower() for q in queries)
            aliases = [
                t for t in seen_original_titles
                if t.strip() and t.strip().lower() not in existing_queries
            ][:5]
            if aliases:
                logger.info(
                    f"  Bangumi: all searches failed, trying alias fallback with "
                    f"aliases={aliases[:3]}"
                )
                alias_queries = build_search_queries(clean_title, [raw_title, code], extra_aliases=aliases)
                new_alias_queries = [q for q in alias_queries if q.lower() not in existing_queries]
                for query in new_alias_queries[:3]:
                    if not query:
                        continue
                    logger.info(
                        f"  fallback step=bangumi_search_alias clean_title='{clean_title}' "
                        f"query='{query}'"
                    )
                    try:
                        alias_results = await self.search(query, limit=5)
                    except Exception as e:
                        logger.warning(f"  Bangumi alias search error for '{query}': {e}")
                        continue
                    logger.info(f"  bangumi_search alias: candidates={len(alias_results)} query='{query}'")
                    if not alias_results:
                        continue
                    for candidate in alias_results[:3]:
                        matched = candidate_title_matches(candidate, clean_title, query, code)
                        if (
                            not matched
                            and query == (alias_queries[0] if alias_queries else "")
                            and len(alias_results) <= 2
                            and _is_specific_search_query(query)
                        ):
                            matched = True
                        logger.info(
                            f"  bangumi_search alias: title_matches={matched} "
                            f"source_id='{candidate.source_id}' title='{candidate.title}'"
                        )
                        if matched:
                            best = candidate
                            break
                    if best:
                        break

        if not best:
            logger.info(f"  Bangumi: no match for clean_title='{clean_title}', failures={'; '.join(failures)}")
            return None

        result = await self.get_detail(best.source_id)
        if not result or not result.title:
            return None

        data = scrape_result_to_legacy(result, exact=False)
        data["_search_match_passed"] = True
        return data

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
