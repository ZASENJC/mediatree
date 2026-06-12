# Configuration

MediaTree uses environment variables and runtime settings together. Environment variables are best for deployment-level settings; the Settings page is best for libraries, scrapers, and UI preferences.

## Authentication

| Variable | Default | Description |
| --- | --- | --- |
| `AUTH_USER` | `""` | Admin username. Leave empty to create an admin account on first launch. |
| `AUTH_PASS` | `""` | Admin password. Use a strong password when auth is enabled. |

Sensitive values are read from environment variables only and are not persisted to `data/config.json`.

## Media and Data

| Variable | Default | Description |
| --- | --- | --- |
| `MEDIA_ROOT` | `/media` | Container media root. |
| `DATA_DIR` | `../data` | Persistent data directory. |
| `SCAN_ON_STARTUP` | `true` | Scan when the container starts. |
| `FILE_WATCHER_ENABLED` | `true` | Enable filesystem watching and automatic scans. |

For multiple libraries, mount several folders under `/media/*`, then configure each library in Settings.

## Scraper Settings

| Variable | Default | Description |
| --- | --- | --- |
| `TMDB_API_KEY` | `""` | TMDB v3 API key. |
| `TMDB_ACCESS_TOKEN` | `""` | TMDB v4 Read Access Token, recommended. |
| `JAVDB_ENABLED` | `true` | Enable the Javdatabase scraper. |
| `SCRAPE_CONCURRENCY_PER_LIBRARY` | `8` | Max concurrent scrapes per library. |
| `SCRAPE_GLOBAL_CONCURRENCY` | `16` | Global max concurrent scrapes. |
| `SCRAPER_API_CONCURRENCY` | `8` | Max concurrent API requests. |
| `SCRAPER_HTTP_TIMEOUT` | `10.0` | External HTTP timeout in seconds. |

Cache TTLs and the Javdatabase request interval are internal policies, not exposed user settings. Manual scans, rescrapes, and manual apply actions bypass cache.

## Runtime Settings

These are managed from the Settings page and persisted to `data/config.json`:

- Library paths, scrapers, and passwords.
- TMDB API key or read access token.
- UI preferences, including hidden home title, ambient mode, and source filename display.
- Backup, restore, updates, and subtitle fonts.

## Getting a TMDB Read Access Token

1. Register or sign in to [TMDB](https://www.themoviedb.org/).
2. Open [API Settings](https://www.themoviedb.org/settings/api).
3. Generate a v4 Read Access Token.
4. Set `TMDB_ACCESS_TOKEN` in `.env` or Settings.

MediaTree can still scan and play files without TMDB credentials, but metadata and images will be limited.
