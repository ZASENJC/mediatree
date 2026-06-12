# Scrapers

MediaTree uses plugin-style scrapers to fetch titles, posters, cast, summaries, seasons, episodes, and images. Each library can use a different scraper.

## Built-in Scrapers

### TMDB

`tmdb_movie` and `tmdb_tv` are for movies and TV shows. They support titles, summaries, genres, cast, people, posters, backdrops, season posters, episode stills, trailers, reviews, and release information.

TMDB requires `TMDB_ACCESS_TOKEN` or `TMDB_API_KEY`.

### Bangumi

`bangumi` is useful for anime and East Asian media. It can provide multilingual titles, people, covers, and subject types. It uses a public API and does not require an API key.

### Javdatabase

`javdatabase` matches JAV metadata by code, including title, cast, director, maker, label, genres, score, thumbnails, and release details. It is not part of the `auto` chain and must be selected for the relevant library.

### Auto

`auto` is the default fallback chain:

1. Extract a TMDB ID from the filename when present.
2. Use exact TMDB matching when an ID is found.
3. Search TMDB movie and TV when no ID is found.
4. Try Bangumi if TMDB fails.
5. Keep local filenames if all sources fail.

### None

`none` disables network scraping for libraries that should use filenames or local information only.

## Cache and Refresh Policy

- Search and detail responses are cached in SQLite to reduce duplicate background requests.
- TMDB/Bangumi cache for 168 hours, Javdatabase caches for 24 hours.
- Empty results are not written to cache, and old empty cache entries are removed when read.
- Startup scans and filesystem watcher scans use cache.
- Manual full scans, rescrapes, manual scraping, and manual apply actions bypass cache.

## Manual Scraping

1. Open the action menu on a folder or movie.
2. Choose manual scraping or rescrape.
3. Search by title, code, or TMDB ID.
4. Pick the correct candidate.
5. Apply it to update the local database and cover cache.

## Custom Scrapers

Developers can add scrapers under `backend/app/scrapers/`, inherit `BaseScraper`, implement `search()` and `get_detail()`, then register the scraper in `registry.py`. See the [development guide](/en/development/) for engineering details.
