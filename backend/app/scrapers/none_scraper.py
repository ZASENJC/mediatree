from __future__ import annotations

from .base import BaseScraper


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
