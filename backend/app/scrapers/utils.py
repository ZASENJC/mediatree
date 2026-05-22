"""
Shared scraper utilities: conversion helpers between ScrapeResult and legacy dict format.

Used by both scraper implementations (to return dicts from full_scrape())
and by scrape_engine (for compatibility with _apply_scraped_data).
"""
from __future__ import annotations

import json

from .base import ScrapeCandidate, ScrapeResult, ScrapeStaff


def _staff_to_dict(staff: ScrapeStaff) -> dict:
    return {
        "name": staff.name,
        "role": staff.role or "",
        "job": staff.job or "",
        "department": staff.department or "",
        "person_id": staff.person_id or "",
        "source": staff.source or "",
    }


def _candidate_to_dict(candidate: ScrapeCandidate) -> dict:
    return {
        "source": candidate.source,
        "source_id": candidate.source_id,
        "media_type": candidate.media_type or "",
        "title": candidate.title,
        "original_title": candidate.original_title or "",
        "year": str(candidate.year or ""),
        "poster_url": candidate.poster_url,
        "backdrop_url": candidate.backdrop_url,
        "overview": candidate.overview or "",
        "score": candidate.score,
    }


def _thumbnail_json(result: ScrapeResult) -> str:
    raw = result.raw or {}
    existing = raw.get("javdb_thumbnails")
    if existing:
        return existing if isinstance(existing, str) else json.dumps(existing, ensure_ascii=False)
    thumbs = []
    for url in (result.thumbnail_url, result.still_url, result.episode_still_url):
        if url and url not in thumbs:
            thumbs.append(url)
    return json.dumps(thumbs, ensure_ascii=False) if thumbs else ""


def scrape_result_to_legacy(result: ScrapeResult, *, exact: bool = False) -> dict:
    """Convert a ScrapeResult dataclass to the legacy dict format for _apply_scraped_data()."""
    raw = result.raw or {}
    source = result.source
    cover = result.cover_url or result.poster_url or raw.get("cover_remote") or raw.get("poster_url") or ""
    media_type = result.media_type or raw.get("media_type") or ""
    source_id = str(result.source_id or raw.get("source_id") or "")
    release_date = raw.get("release_date") or raw.get("date") or (str(result.year) if result.year else "")
    duration = raw.get("runtime") or raw.get("duration")
    cast = [_staff_to_dict(item) for item in result.cast]
    crew = [_staff_to_dict(item) for item in result.crew]
    actress = raw.get("actress") or ""
    if not actress and source == "javdatabase" and cast:
        actress = ", ".join(item["name"] for item in cast if item.get("name"))

    data = {
        "source": source,
        "scraper_source": source,
        "source_id": source_id,
        "title": result.title or raw.get("title", ""),
        "original_title": result.original_title or raw.get("original_title") or "",
        "overview": result.overview or raw.get("overview") or "",
        "actress": actress,
        "release_date": release_date,
        "duration": duration,
        "cover_remote": cover,
        "backdrop_url": result.backdrop_url or raw.get("backdrop_url") or "",
        "javdb_url": raw.get("javdb_url") or raw.get("bgm_url") or "",
        "javdb_score": raw.get("score") or raw.get("javdb_score"),
        "javdb_likes": raw.get("votes") or raw.get("collection_total") or raw.get("javdb_likes"),
        "javdb_thumbnails": _thumbnail_json(result),
        "tmdb_id": int(result.tmdb_id) if result.tmdb_id and str(result.tmdb_id).isdigit() else raw.get("tmdb_id"),
        "tmdb_type": media_type if source == "tmdb" else "",
        "bangumi_id": result.bangumi_id,
        "javdb_id": result.javdb_id,
        "seasons": raw.get("seasons", []),
        "cast": cast,
        "crew": crew,
        "imdb_id": raw.get("imdb_id"),
        "episode_title": result.episode_title or raw.get("episode_title") or "",
        "episode_still": result.episode_still_url or raw.get("episode_still") or "",
        "genre": raw.get("genre") or "",
        "tagline": raw.get("tagline") or "",
        "status": raw.get("status") or "",
        "content_rating": raw.get("content_rating") or "",
        "studios": raw.get("studios") or [],
        "keywords": raw.get("keywords") or "",
        "_exact_match": exact,
        "_raw": raw,
        "scraper_raw": json.dumps(raw, ensure_ascii=False) if raw else "",
    }
    if result.season is not None:
        data["tmdb_season"] = result.season
    if result.episode is not None:
        data["tmdb_episode"] = result.episode
    return data
