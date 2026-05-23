<p align="center">
  <img src="https://raw.githubusercontent.com/ZASENJC/mediatree/main/frontend/public/icon.svg" alt="MediaTree" width="80" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <strong>English</strong> | <a href="README_zh-CN.md">简体中文</a>
  <br><br>
  <strong>Self-hosted media library — one command deploy.<br>Elegant UI, multi-source scraping, ASS subtitle rendering,<br>supporting movies, TV, anime & JAV.</strong>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
</p>

---

## Features

<table>
<tr>
<td width="50%">

### Media Library
- Multi-library with per-root scraper & password
- Recursive scanning with file watcher auto-update
- Folder tree browser with seasonal tab switching
- Source filename / scraped title display toggle
- Favorites, categories, and excluded folders

### Scrapers
- **TMDB** — Movie & TV with cast/crew/stills/reviews
- **Bangumi** — Anime metadata for CJK titles
- **Javdatabase** — Code-based JAV metadata
- Plugin architecture with intelligent fallback chain
- Manual scrape with search-and-select UI

</td>
<td width="50%">

### Video Player
- ArtPlayer 5 with custom YouTube-style UI
- Direct streaming + Range support (byte seeking)
- On-demand ffmpeg H.264 transcoding
- Touch gestures & keyboard shortcuts
- VR/360° video via Three.js
- Picture-in-picture & external player (IINA/mpv)

### Subtitles
- ASS/SSA rendering via libass-wasm (full effects)
- External subtitle auto-matching (basename + lang)
- CJK fallback font (Source Han Sans CN)
- SRT → WebVTT native conversion
- User font upload & management

</td>
</tr>
</table>

### Jellyfin Compatible

36 Jellyfin API endpoints — connect **VidHub**, **Infuse**, **Kodi**, **VLC**, **IINA**, and **mpv** directly. Series/Season/Episode hierarchy from folder structure, multi-client auth (MediaBrowser Token, X-Emby-Token, Bearer), Emby path compatibility, and playback progress tracking.

### UI Design

Glassmorphism + Apple-style design with custom TailwindCSS palette. Liquid glass header, aurora gradient backgrounds, theater mode ambient lighting, image lightbox, and responsive mobile-first layout.

---

## Quick Start

```bash
# Clone
git clone https://github.com/ZASENJC/mediatree.git && cd mediatree

# Configure
cp .env.example .env
# Edit .env — set AUTH_USER, AUTH_PASS, and MEDIA_VOLUMES

# Run
docker compose up -d

# Open
open http://localhost:27580
```

> **Docker Hub**: `docker pull zasenjc/mediatree:latest`

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_USER` | — | Admin username (auth enabled when set) |
| `AUTH_PASS` | — | Admin password |
| `MEDIA_VOLUMES` | — | Media directories: `/path:/media/alias:ro` |
| `DATA_DIR` | `./data` | Persistent data (DB, covers, fonts) |
| `HOST_PORT` | `27580` | Host port mapping |
| `SCAN_ON_STARTUP` | `true` | Auto-scan on container start |
| `JAVDB_ENABLED` | `true` | Enable JavDatabase scraper |
| `TMDB_API_KEY` | — | TMDB v3 API key _(optional)_ |
| `TMDB_ACCESS_TOKEN` | — | TMDB v4 access token _(optional)_ |

See `.env.example` for all options.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 · FastAPI · Uvicorn · httpx · aiosqlite · Pydantic v2 · ffmpeg |
| **Frontend** | React 18 · TypeScript 5 · TailwindCSS 3 · Vite · ArtPlayer 5 · Three.js |
| **Subtitle** | @jellyfin/libass-wasm · fonttools · charset-normalizer |
| **Database** | SQLite (WAL mode · aiosqlite) |
| **Deploy** | Docker multi-stage (node:20-alpine + python:3.12-slim) |
| **Platform** | linux/amd64 · linux/arm64 |

---

## Development

```bash
# Backend (port 80)
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Frontend (port 5173, proxies /api -> localhost:80)
cd frontend && npm install && npm run dev

# Tests
cd backend && python -m unittest discover -s tests -p 'test_*.py'
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Version history & release notes |
| [CLAUDE.md](CLAUDE.md) | AI-assisted development guide |
| [Wiki](https://github.com/ZASENJC/mediatree/wiki) | Full documentation & guides |

---

## License

MIT © [ZASENJC](https://github.com/ZASENJC)
