from __future__ import annotations

from .base import BaseScraper, ScraperInfo
from .bangumi_scraper import BangumiScraper
from .javdatabase_scraper import JavdatabaseScraper
from .tmdb_scraper import TMDBScraper


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
    description = "MediaTree fallback chain: TMDB ID, Bangumi, then TMDB"
    supported_media_types = {"movie", "tv", "anime", "jav"}
    requires_api_key = False

    async def search(self, query: str, *, media_type: str | None = None, limit: int = 10):
        return []

    async def get_detail(self, source_id: str, *, media_type: str | None = None):
        return None

    def normalize_result(self, raw: dict):
        raise NotImplementedError("Auto scraper is resolved by scanner fallback logic")


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
