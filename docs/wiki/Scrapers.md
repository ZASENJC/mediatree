**English** | [简体中文](../wiki_zh-CN/Scrapers)

# Scrapers

MediaTree uses a plugin-based scraper system to fetch metadata from multiple sources. Each media library can use a different scraper configuration.

## Built-in Scrapers

### TMDB (`tmdb_movie` / `tmdb_tv`)

The most comprehensive scraper, supporting movies and TV shows.

- **Metadata**: Title, original title, overview, release date, genres, keywords, content rating
- **Cast & Crew**: Actors, directors, writers, with profile photos
- **Artwork**: Posters, backdrops, logos, season posters, episode stills
- **Reviews**: User reviews from TMDB
- **Videos**: Trailers and clips
- **Staff**: Full person profiles with filmography

**Requirements**: TMDB API key or Read Access Token (see [Configuration](Configuration))

### Bangumi (`bangumi`)

Specialized for anime and East Asian media.

- **Metadata**: Chinese, Japanese, and English titles
- **Staff**: Voice actors, directors, original creators
- **Artwork**: Cover images and character art
- **Subjects**: Anime, manga, games, novels, live-action

**No API key required** (uses public API).

### Javdatabase (`javdatabase`)

Code-based JAV metadata scraper.

- **Metadata**: Title, actress, director, studio, label, genre
- **Ratings**: Score, likes, view count
- **Thumbnails**: Cover and sample images
- **Details**: Runtime, release date, series

**Requirements**: Enabled by default. Configure via Settings page.

### Auto (`auto`)

Intelligent fallback chain that automatically chooses the best scraper:

1. Extract TMDB ID from filename (`[tmdbid=123]`, `[tmdb-movie=123]`, etc.)
2. If TMDB ID found → exact match with movie/TV type inference
3. If no ID → TMDB title search (both movie and TV)
4. If TMDB fails → Bangumi fallback
5. If all fail → no metadata applied

### None (`none`)

Disables network scraping. Use for libraries where you want to use local NFO/metadata only, or filename-based display.

## Fallback Chain

```
tmdb_movie ──→ Bangumi ──→ TMDB movie title search
tmdb_tv    ──→ Bangumi ──→ TMDB tv title search
bangumi    ──→ TMDB tv title search
javdatabase ── (independent, no fallback)
auto        ──→ Bangumi ──→ TMDB title search (both)
```

## Adding a Custom Scraper

Scrapers follow a plugin architecture. To add a new one:

```python
# backend/app/scrapers/my_scraper.py
from .base import BaseScraper, ScrapeResult, ScrapeCandidate

class MyScraper(BaseScraper):
    name = "my_scraper"
    label = "My Scraper"
    description = "Custom metadata source"

    async def search(self, query: str, **kwargs) -> list[ScrapeCandidate]:
        # Implement search logic
        ...

    async def get_detail(self, candidate: ScrapeCandidate) -> ScrapeResult:
        # Implement detail fetch
        ...

    def normalize_result(self, result: ScrapeResult) -> ScrapeResult:
        # Optional: normalize the result
        return result
```

Then register it:

```python
# backend/app/scrapers/registry.py
from .my_scraper import MyScraper
register_scraper(MyScraper())
```

## Scraper Cache

- HTTP responses are cached in SQLite (`scraper_cache` table)
- Configurable TTL per source (default: TMDB/Bangumi 168h, JavDB 24h)
- Concurrent requests to the same resource are deduplicated
- Right-click → "Re-scrape" bypasses cache and forces a fresh fetch

## Manual Scraping

1. Right-click a folder or movie → "Manual Scrape"
2. Search by title or TMDB ID
3. Select the correct match from search results
4. Click "Apply" to update metadata

## Season/Episode Handling

MediaTree automatically detects season folders (`S01`, `S02`, `Season 1`, etc.) and:
- Fetches per-season metadata from TMDB
- Maps local episode files to TMDB episode numbers
- Handles multi-season merges (when TMDB combines seasons)
- Displays episode titles, overviews, and stills

For anime, the [anime naming parser](#anime-naming) extracts episode numbers from various formats including `[01]`, `EP01`, `S01E01`.
