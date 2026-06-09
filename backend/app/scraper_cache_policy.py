from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_bypass_scraper_cache: ContextVar[bool] = ContextVar("bypass_scraper_cache", default=False)


def should_bypass_scraper_cache() -> bool:
    return _bypass_scraper_cache.get()


@contextmanager
def bypass_scraper_cache() -> Iterator[None]:
    token = _bypass_scraper_cache.set(True)
    try:
        yield
    finally:
        _bypass_scraper_cache.reset(token)
