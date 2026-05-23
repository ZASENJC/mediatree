**English** | [简体中文](../wiki_zh-CN/Home)

# MediaTree Wiki

Welcome to the MediaTree documentation. MediaTree is a self-hosted media library manager that combines elegant glassmorphism UI with Jellyfin-compatible API and a powerful plugin-based scraper system.

## Quick Navigation

| Guide | Description |
|-------|-------------|
| [Installation](Installation) | Docker setup and first-time deployment |
| [Configuration](Configuration) | Environment variables and runtime settings |
| [Media Libraries](Media-Libraries) | Setting up and managing media libraries |
| [Scrapers](Scrapers) | TMDB, Bangumi, Javdatabase scraper system |
| [Jellyfin Clients](Jellyfin-Clients) | Connecting Jellyfin-compatible clients |
| [Subtitles](Subtitles) | Subtitle detection, rendering, and font management |
| [API Reference](API-Reference) | Complete API endpoint documentation |
| [Development](Development) | Local development setup and architecture |

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│                 Docker Container              │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Frontend     │  │  Backend (FastAPI)   │ │
│  │  React 18     │  │  Python 3.12         │ │
│  │  TypeScript 5 │  │  SQLite (aiosqlite)  │ │
│  │  Vite         │  │  ffmpeg/ffprobe      │ │
│  └──────────────┘  └──────────────────────┘ │
│         ↕ proxy /api/*       ↕ filesystem   │
│  ┌────────────────────────────────────────┐  │
│  │  Media Volumes (read-only mount)        │  │
│  │  Data Volume (database, covers, fonts)  │  │
│  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## Key Features at a Glance

- **Glassmorphism UI** — Apple-style design with liquid glass header, aurora gradients, and theater mode
- **Multi-library** — Per-root scraper configuration, password protection, and folder tree browsing
- **Scraper plugins** — TMDB (movie/TV), Bangumi (anime), Javdatabase (JAV) with auto fallback chain
- **ArtPlayer 5** — Custom controls, touch gestures, keyboard shortcuts, PiP, and VR/360° support
- **ASS/SSA subtitles** — libass-wasm rendering with CJK fallback font and full effect support
- **Jellyfin API** — 36 endpoints for direct VidHub/Infuse/Kodi/VLC/IINA/mpv integration
- **File watcher** — Automatic incremental scanning on file changes with 15s debounce
- **Android TV** — Works with Android TV Jellyfin clients for big-screen browsing
