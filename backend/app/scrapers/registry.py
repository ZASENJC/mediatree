from __future__ import annotations

from .base import BaseScraper, ScraperInfo
from .bangumi_scraper import BangumiScraper
from .javdatabase_scraper import JavdatabaseScraper
from .tmdb_scraper import TMDBScraper, tmdb_title_search


_registry: dict[str, BaseScraper] = {}
_initialized = False


def register_scraper(scraper: BaseScraper):
    if not scraper.name:
        raise ValueError("Scraper must define a name")
    _registry[scraper.name] = scraper


def get_scraper(name: str) -> BaseScraper:
    ensure_builtin_scrapers()
    normalized = _normalize_name(name)
    scraper = _registry.get(normalized)
    if not scraper:
        raise KeyError(f"Unknown scraper: {name}")
    return scraper


def list_scrapers() -> list[ScraperInfo]:
    ensure_builtin_scrapers()
    return [scraper.info() for scraper in _registry.values()]


def ensure_builtin_scrapers():
    global _initialized
    if _initialized:
        return
    register_scraper(TMDBScraper("movie"))
    register_scraper(TMDBScraper("tv"))
    register_scraper(BangumiScraper())
    register_scraper(JavdatabaseScraper())
    register_scraper(AutoScraper())
    register_scraper(NoneScraper())
    _initialized = True


def _normalize_name(name: str | None) -> str:
    value = (name or "auto").strip().lower()
    if value == "tmdb":
        return "tmdb_movie"
    return value


class AutoScraper(BaseScraper):
    name = "auto"
    label = "Auto"
    description = "MediaTree fallback chain: IMDB/TMDB ID, TMDB title, then Bangumi"
    supported_media_types = {"movie", "tv", "anime", "jav"}
    requires_api_key = False

    async def search(self, query: str, *, media_type: str | None = None, limit: int = 10):
        return []

    async def get_detail(self, source_id: str, *, media_type: str | None = None):
        return None

    async def full_scrape(
        self,
        search_name: str,
        *,
        code: str = "",
        candidate_names: list[str] | None = None,
        movie: dict | None = None,
    ) -> dict | None:
        """Auto scraper fallback chain: IMDB/TMDB ID → TMDB title (movie+tv) → Bangumi."""
        from ..config import logger
        from ..title_match import (
            clean_search_title, build_search_queries, candidate_title_matches,
            _first_tmdb_token, _is_specific_search_query, TmdbIdToken,
            extract_imdb_id_from_name,
        )

        logger.info(f"  Auto scraper started for '{search_name}'")
        candidates = candidate_names or [search_name, code]

        # Step 0: IMDB ID exact match
        for name in candidates:
            imdb_id = extract_imdb_id_from_name(name)
            if imdb_id:
                logger.info(f"  Auto scraper detected IMDB ID {imdb_id} from '{name}'")
                from ..tmdb import fetch_tmdb_by_imdb_id
                imdb_detail = await fetch_tmdb_by_imdb_id(imdb_id)
                if imdb_detail and imdb_detail.get("title"):
                    media_type = imdb_detail.get("media_type", "movie")
                    source_id = imdb_detail.get("source_id", "")
                    logger.info(f"  Auto scraper IMDB ID success: {imdb_id} → TMDB {media_type}/{source_id}")
                    return _tmdb_scrape_data(imdb_detail, str(source_id), media_type, exact=True)
                break  # Only try first IMDB ID found

        token = None
        for idx, candidate in enumerate(candidates):
            label = ["folder", "parent", "filename", "title", "code", "search"][idx] if idx < 6 else "candidate"
            token = _first_tmdb_token([candidate])
            if token:
                break

        # Step 1: TMDB ID exact match
        if token:
            logger.info(f"  Auto scraper detected tmdbid={token.id} from {token.source_name} ({token.raw})")
            logger.info(f"  Auto scraper using TMDB ID exact match: tmdbid={token.id}")
            data = await _try_auto_tmdb_id(token, movie or {}, candidates)
            if data:
                logger.info(f"  Auto scraper TMDB ID success: tmdbid={token.id} type={data.get('tmdb_type')}")
                return data
            logger.warning("  TMDB ID 精确匹配失败，fallback 到标题搜索")

        clean_title = clean_search_title(search_name, candidates)
        logger.info(
            f"  Auto scraper fallback title search raw_title='{search_name}' "
            f"clean_title='{clean_title}' tmdb_token={'yes' if token else 'no'}"
        )
        if not clean_title:
            logger.info(f"  Auto scraper failed: no clean title for '{search_name}'")
            return None

        # Step 2: TMDB title search (both movie and tv)
        logger.info(f"  Auto scraper: sequential fallback to TMDB title search for '{clean_title}'")
        data = await tmdb_title_search(clean_title, search_name, code)
        if data and data.get("title"):
            logger.info(f"  Auto scraper: TMDB title search success for '{clean_title}'")
            return data

        # Step 3: Bangumi
        logger.info(f"  Auto scraper: sequential fallback to Bangumi for '{clean_title}'")
        bangumi = get_scraper("bangumi")
        data = await bangumi.full_scrape(clean_title, code=code)
        if data and data.get("title"):
            logger.info(f"  Auto scraper: Bangumi fallback success for '{clean_title}'")
            return data

        logger.info(f"  Auto scraper: all sequential fallbacks failed for '{clean_title}'")
        return None

    def normalize_result(self, raw: dict):
        raise NotImplementedError("Auto scraper is resolved by scanner fallback logic")


async def _try_auto_tmdb_id(
    token: "TmdbIdToken",
    movie: dict,
    candidate_names: list[str],
) -> dict | None:
    """TMDB ID resolution for auto scraper: handle movie/tv type inference."""
    from ..tmdb import fetch_tmdb_by_id, fetch_tmdb_candidates_by_id
    from ..config import logger
    from ..title_match import infer_tmdb_media_type

    if token.media_type:
        logger.info(f"  TMDB ID explicit {token.media_type}: only requesting /{token.media_type}/{token.id}")
        data = await fetch_tmdb_by_id(token.id, token.media_type)
        if data and data.get("title"):
            return _tmdb_scrape_data(data, str(token.id), token.media_type, exact=True)
        return None

    inferred, scores = infer_tmdb_media_type(movie or {}, candidate_names)
    movie_score = scores["movie_score"]
    tv_score = scores["tv_score"]
    logger.info(
        f"  TMDB ID local type scores for {token.id}: "
        f"movie={movie_score}, tv={tv_score}, inferred={inferred}, reasons={','.join(scores['reasons'][:6])}"
    )

    if tv_score >= movie_score + 4:
        logger.info(f"  TMDB ID strong local inference: tv; only requesting /tv/{token.id}")
        data = await fetch_tmdb_by_id(token.id, "tv")
        if data and data.get("title"):
            return _tmdb_scrape_data(data, str(token.id), "tv", exact=True)
        return None

    if movie_score >= tv_score + 4:
        logger.info(f"  TMDB ID strong local inference: movie; only requesting /movie/{token.id}")
        data = await fetch_tmdb_by_id(token.id, "movie")
        if data and data.get("title"):
            return _tmdb_scrape_data(data, str(token.id), "movie", exact=True)
        return None

    logger.info(f"  TMDB ID type unclear: concurrently requesting movie/tv candidates for {token.id}")
    candidates_data = await fetch_tmdb_candidates_by_id(token.id)
    movie_detail = candidates_data.get("movie")
    tv_detail = candidates_data.get("tv")

    if movie_detail and not tv_detail:
        if tv_score >= movie_score + 4:
            logger.warning(f"  TMDB ID movie exists but local score strongly suggests tv; rejecting movie/{token.id}")
            return None
        return _tmdb_scrape_data(movie_detail, str(token.id), "movie", exact=True)
    if tv_detail and not movie_detail:
        if movie_score >= tv_score + 4:
            logger.warning(f"  TMDB ID tv exists but local score strongly suggests movie; rejecting tv/{token.id}")
            return None
        return _tmdb_scrape_data(tv_detail, str(token.id), "tv", exact=True)
    if movie_detail and tv_detail:
        if tv_score >= movie_score + 2:
            return _tmdb_scrape_data(tv_detail, str(token.id), "tv", exact=True)
        if movie_score >= tv_score + 2:
            return _tmdb_scrape_data(movie_detail, str(token.id), "movie", exact=True)
        logger.warning(f"  TMDB ID {token.id} exists as both movie and tv but local scores are unclear; fallback to title search")
    return None


def _tmdb_scrape_data(detail: dict, source_id: str, media_type: str, exact: bool = False) -> dict:
    import json
    return {
        "source": "tmdb", "scraper_source": "tmdb", "source_id": str(source_id),
        "title": detail.get("title", ""),
        "original_title": detail.get("original_title", ""),
        "overview": detail.get("overview", ""),
        "release_date": detail.get("release_date", ""),
        "duration": detail.get("runtime") or detail.get("duration", 0),
        "cover_remote": detail.get("poster_url", ""),
        "backdrop_url": detail.get("backdrop_url", ""),
        "javdb_score": detail.get("score"), "javdb_likes": detail.get("votes"),
        "tmdb_id": int(source_id), "tmdb_type": media_type,
        "seasons": detail.get("seasons", []), "cast": detail.get("cast", []),
        "crew": detail.get("crew", []), "imdb_id": detail.get("imdb_id"),
        "_raw": detail,
        "scraper_raw": json.dumps(detail, ensure_ascii=False) if detail else "",
        "_exact_match": exact,
    }


class NoneScraper(BaseScraper):
    name = "none"
    label = "None"
    description = "Disable network scraping"
    supported_media_types = set()
    requires_api_key = False
    enabled = False

    async def search(self, query: str, *, media_type: str | None = None, limit: int = 10):
        return []

    async def get_detail(self, source_id: str, *, media_type: str | None = None):
        return None

    def normalize_result(self, raw: dict):
        raise NotImplementedError("None scraper does not return results")


ensure_builtin_scrapers()
