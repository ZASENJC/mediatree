# Configuration

MediaTree is configured through environment variables (`.env` file) and runtime settings (Settings page).

## Environment Variables

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_USER` | `""` | Admin username. Leave empty to disable authentication |
| `AUTH_PASS` | `""` | Admin password. Use a strong password if auth is enabled |

### Media & Data

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIA_ROOT` | `/media` | Root directory containing media libraries |
| `DATA_DIR` | `../data` | Persistent data directory (DB, covers, config, fonts, logs) |
| `SCAN_ON_STARTUP` | `true` | Run full scan on container start |
| `FILE_WATCHER_ENABLED` | `true` | Enable file system watcher for auto-scanning |

### Scraper Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TMDB_API_KEY` | `""` | TMDB v3 API key |
| `TMDB_ACCESS_TOKEN` | `""` | TMDB v4 Read Access Token _(preferred)_ |
| `TMDB_CACHE_HOURS` | `168` | TMDB cache TTL in hours (1 week) |
| `BANGUMI_CACHE_HOURS` | `168` | Bangumi cache TTL in hours |
| `JAVDB_ENABLED` | `true` | Enable JavDatabase scraper |
| `JAVDB_CACHE_HOURS` | `24` | JavDB cache TTL in hours |
| `JAVDB_REQUEST_INTERVAL` | `1.0` | Minimum seconds between JavDB requests |

### Parallelism

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPE_CONCURRENCY_PER_LIBRARY` | `8` | Max concurrent scrapes per library |
| `SCRAPE_GLOBAL_CONCURRENCY` | `16` | Max total concurrent scrapes |
| `SCRAPER_API_CONCURRENCY` | `8` | Max concurrent API calls |
| `SCRAPER_HTTP_TIMEOUT` | `10.0` | HTTP request timeout in seconds |

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `80` | Server listen port inside container |

## docker-compose.yml

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    ports:
      - "${HOST_PORT:-27580}:27580"
    volumes:
      - ${MEDIA_VOLUMES}
      - ${DATA_DIR:-./data}:/app/data
    env_file:
      - .env
    environment:
      - PORT=${HOST_PORT:-27580}
    restart: unless-stopped
```

## Runtime Settings (via Settings Page)

The following settings are managed through the web UI and persisted in `data/config.json`:

- **Library configuration** — scraper selection, TMDB keys, library passwords
- **JavDB settings** — enabled/disabled, cache duration, request interval
- **UI preferences** — hide home title text, ambient mode, show source name

## Configuration Priority

1. Environment variables (`.env`)
2. Runtime settings (`data/config.json`)
3. Default values in `config.py`

**Key precedence rule**: Sensitive values (`AUTH_PASS`) are sourced ONLY from environment variables and never persisted to `config.json`.

## Getting a TMDB API Key

1. Create a [TMDB account](https://www.themoviedb.org/signup)
2. Go to [API Settings](https://www.themoviedb.org/settings/api)
3. Generate a "Read Access Token" for v4 auth (recommended)
4. Set `TMDB_ACCESS_TOKEN` in your `.env` file

> ℹ️ TMDB API is free for non-commercial use. Without it, MediaTree can still use filename-based organization without rich metadata.
