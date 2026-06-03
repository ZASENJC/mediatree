<p align="center">
  <img src="https://raw.githubusercontent.com/ZASENJC/mediatree/main/docs/assets/logo.png" alt="MediaTree" width="96" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <strong>English</strong> | <a href="README_zh-CN.md">简体中文</a>
</p>

<p align="center">
  <em>Self-hosted media library — one command deploy.<br>Elegant UI, multi-source scraping, ASS subtitle rendering,<br>movies, TV, anime & JAV — all in one place.</em>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0.06-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
</p>

---

## Screenshots

![Home](https://img.qunq.de/file/1779640696711_home_no_text.png)
*Home — media library grid with glassmorphism cards*

![Player](https://img.qunq.de/file/1779640693184_movie.png)
*Player — streaming with ASS subtitle rendering*

![Browse](https://img.qunq.de/file/1779640700855_browser.png)
*Browse — folder tree navigation with seasonal tabs*

![Settings](https://img.qunq.de/file/1779640699625_settings.png)
*Settings — scraper config, library management, backup & updates*

---

## Features

### Media Library

- Multi-library with per-root scraper and access password
- Recursive scanning with file-change watcher auto-incremental update, including folder structure changes
- Folder tree browser with seasonal tab switching
- Source filename / scraped title display toggle
- Favorites, categories, and excluded folders

### Scrapers

- **TMDB** — Movie & TV metadata (cast, crew, stills, reviews, keywords)
- **Bangumi** — Anime metadata for Chinese & Japanese titles
- **Javdatabase** — JAV code-based metadata with fuzzy search fallback
- Plugin architecture with configurable intelligent fallback chain
- Manual scrape with search-and-select UI
- Batch folder-level scraping via right-click context menu
- Scraper cache with configurable TTL (24h–168h)

### Video Player

- ArtPlayer 5 with custom YouTube-style controls
- Direct streaming + HTTP Range support (byte-range seeking)
- On-demand ffmpeg H.264 transcoding
- Touch gestures — tap, double-tap, swipe for mobile control
- Keyboard shortcuts — Space/K, arrows, F, M
- VR/360° video via Three.js equirectangular rendering
- Picture-in-picture + external player (IINA, mpv, VLC)

### Subtitles

- ASS/SSA rendering via @jellyfin/libass-wasm (full effects, fonts, positioning)
- External subtitle auto-matching by basename + language suffix + episode
- CJK fallback font (Source Han Sans CN Bold) for anime subtitles
- SRT → WebVTT native conversion (pure Python, no ffmpeg dependency)
- Auto-encoding detection (16 encodings + charset-normalizer)
- User font upload and management

### Jellyfin Compatible

36 Jellyfin-compatible API endpoints — connect **VidHub**, **Infuse**, **Kodi**, **VLC**, **IINA**, and **mpv** directly. Series → Season → Episode hierarchy from folder structure, multi-client auth (MediaBrowser Token, X-Emby-Token, Bearer, api_key), Emby path compatibility, and playback progress tracking.

### UI Design

Glassmorphism + Apple-style design language with custom TailwindCSS palette. Liquid glass header with chromatic dispersion, aurora gradient backgrounds, theater mode ambient lighting, image lightbox with gesture navigation, and responsive mobile-first layout.

### Settings

Centralized control panel — per-library scraper & access password, cache TTL tuning (24h–168h), TMDB API key configuration, one-click database backup & restore, and lightweight app-package updates with changelog viewer.

---

## Quick Start

```bash
git clone https://github.com/ZASENJC/mediatree.git && cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# Edit .env — set AUTH_USER, AUTH_PASS, and MEDIA_VOLUMES
docker compose up -d
open http://localhost:27580
```

> **Docker Hub**: `docker pull zasenjc/mediatree:latest`

---

## Update Strategy

Regular Web updates from Settings download the small app package attached to the GitHub Release and install it into the `./data` volume. They do not require mounting `/var/run/docker.sock`. Releases are marked as requiring a full image update only when the base layer changes, such as the Python runtime, system packages, ffmpeg, fonts, entrypoint/bootstrap behavior, or Docker self-update prerequisites.

App-package releases and full image releases share one version baseline. If either side has already reached a version, MediaTree treats that version as installed for future update comparisons instead of maintaining separate image/package version tracks.

For full image updates, run:

```bash
docker compose pull
docker compose up -d
```

---

## Configuration

**`AUTH_USER`** — Admin username (auth enabled when set)

**`AUTH_PASS`** — Admin password

**`MEDIA_VOLUMES`** — Media directories: `/host/path:/media/alias:ro`

**`DATA_DIR`** — Persistent data (DB, covers, fonts) — default `./data`

**`HOST_PORT`** — Host port mapping — default `27580`

**`SCAN_ON_STARTUP`** — Auto-scan on container start — default `true`

**`TMDB_API_KEY`** — TMDB v3 API key *(optional)*

**`TMDB_ACCESS_TOKEN`** — TMDB v4 access token *(optional)*

**`JAVDB_ENABLED`** — Enable JavDatabase scraper — default `true`

See `.env.example` for all options.

---

## Tech Stack

**Backend** — Python 3.12 · FastAPI · Uvicorn · httpx · aiosqlite · Pydantic v2 · ffmpeg

**Frontend** — React 18 · TypeScript 5 · TailwindCSS 3 · Vite · ArtPlayer 5 · Three.js

**Subtitles** — @jellyfin/libass-wasm · fonttools · charset-normalizer

**Database** — SQLite (WAL mode, aiosqlite)

**Deploy** — Docker multi-stage (node:22-alpine + python:3.12-slim), non-root runtime user

**Platform** — linux/amd64 · linux/arm64

---

## Development

```bash
# Backend (port 80)
cd backend && pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Frontend (port 5173, proxies /api -> localhost:80)
cd frontend && npm install && npm run dev

# Tests
cd backend && python3.12 -m unittest discover -s tests -p 'test_*.py'
```

---

## Documentation

| Document | Description |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Version history & release notes |
| [CLAUDE.md](CLAUDE.md) | AI-assisted development guide |
| [Wiki](https://github.com/ZASENJC/mediatree/wiki) | Full documentation & guides |

---

## License

MIT © [ZASENJC](https://github.com/ZASENJC)
