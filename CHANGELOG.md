**English** | [简体中文](CHANGELOG_zh-CN.md)

# Changelog

All notable changes to MediaTree are documented here.

---

## v1.0.0 (2026-05-23) — Initial Public Release

### Core Architecture

- **Backend**: Python 3.12 + FastAPI + Uvicorn, 85+ RESTful API endpoints
- **Frontend**: React 18 + TypeScript 5 + TailwindCSS 3 + Vite
- **Database**: SQLite via aiosqlite (WAL mode, busy_timeout=5s)
- **Deployment**: Docker multi-stage build, linux/amd64 + linux/arm64 multi-arch

### Media Management

- Multi-library support with per-library scraper configuration and access passwords
- Recursive filesystem scanner with atomic upsert + cleanup of deleted files
- Folder tree browser with nested directory navigation and seasonal tab switching
- Source filename vs scraped title display toggle on home page
- File watcher (`watchfiles`) with 15s debounce for automatic incremental scanning
- Database-driven folder browsing (10-50x faster than filesystem traversal)

### Scraper System

- Plugin-based architecture with abstract `BaseScraper` class
- **TMDB** — Movie & TV metadata (title, cast/crew, cover, backdrop, reviews, keywords)
- **Bangumi** — Anime metadata for Chinese/Japanese titles
- **Javdatabase** — JAV code-based metadata
- Auto scraper with TMDB ID extraction from filenames and intelligent fallback chain
- Season/episode merge for TMDB multi-season compilations
- Manual scrape with search-and-select UI
- Right-click context menu for folder-level batch scraping
- Scraper cache with configurable TTL (24h - 168h)
- Concurrent scraping with configurable parallelism limits (up to 16 tasks)

### Video Player

- ArtPlayer 5 embed with custom UI and YouTube-style controls
- Direct streaming with HTTP Range support (byte-range seeking)
- On-demand ffmpeg transcoding (H.264 + AAC MP4)
- Touch gesture system — tap/double-tap/swipe for mobile control
- Keyboard shortcuts — Space/K (play), ←→ (seek), ↑↓ (volume), F (fullscreen), M (mute)
- Picture-in-picture support
- VR/360° video support via Three.js equirectangular rendering
- External player support (IINA/mpv/VLC M3U playlist generation)
- Playback progress tracking with resume capability

### Subtitle System

- Embedded subtitle detection via ffprobe (ASS, SSA, SRT, VTT, MOV_TEXT)
- External subtitle auto-matching by basename + language suffix + episode number
- **ASS/SSA rendering** via @jellyfin/libass-wasm with full effects, fonts, and positioning
- CJK fallback font (Source Han Sans CN Bold) for anime subtitles
- SRT → WebVTT conversion (pure Python, no ffmpeg dependency)
- Subtitle encoding auto-detection (16 encodings + charset-normalizer fallback)
- User font upload/management for custom subtitle fonts
- Subtitle track selection with language priority ordering
- External audio track detection (.mka, .aac, .flac, .opus, .ac3, .eac3, .dts)

### Jellyfin Compatibility

- 36 Jellyfin-compatible API endpoints for direct client integration
- Compatible with VidHub, Infuse, Kodi, VLC, IINA, mpv as Jellyfin servers
- Multi-client auth — MediaBrowser Token, X-Emby-Token, Bearer, api_key
- Series → Season → Episode hierarchy from folder structure
- Emby path compatibility via rewrite middleware
- Direct-play by default with full subtitle track delivery
- Playback session tracking with progress reporting

### UI Design System

- **Glassmorphism + Apple-style** design language
- Custom TailwindCSS palette — `apple-*` (blue/purple/pink/mint/yellow), `glass-*` (surface/elevated/border/muted)
- Reusable CSS component classes — `glass-panel`, `glass-card`, `glass-button`, `glass-input`, `glass-modal`, `glass-popover`, `glass-chip`
- Liquid glass header with chromatic dispersion effects
- Aurora gradient backgrounds with theater mode ambient lighting
- Responsive navigation — dual glass capsules (brand+nav left, actions right)
- Full mobile adaptation with abbreviated branding on small screens
- Image lightbox with gesture-based swipe navigation
- Toast notification system replacing browser `alert()`

### Cover & Image Handling

- Local cover caching with Pillow resizing (max 500px, JPEG q=80)
- Remote cover URL fallback from TMDB/Bangumi/Javdatabase
- Fanart/backdrop support with cross-fade carousel
- Episode still generation from video via ffmpeg
- Alternative cover picker with TMDB poster/backdrop browsing
- Folder-level cover and backdrop management
- Safe image proxy restricted to trusted CDN domains (TMDB, Bangumi, JavDB)

### Advanced Features

- **Anime naming parser** — strips release groups and technical tags, extracts episode numbers from `[01]`, `[EP01]`, `S01E01`, `第1话` etc.
- **Sort options** — by date added, release date, name, and random
- **Search** — real-time search across titles, codes, and actors with debounce
- **Favorites** — tag-based favorite system with dedicated page
- **Categories** — user-defined collections with custom grouping
- **Excluded folders** — persistent hide mechanism stored in localStorage
- **Scroll position recovery** — sessionStorage-based restoration on navigation
- **API response caching** — 120s TTL client-side cache with smart invalidation
- **Database backup/restore** — core (SQLite) and full (covers + stills) backup options
- **Review queue** — pending review items for unscraped media

### Security

- PBKDF2-SHA256 password hashing (100,000 iterations) with per-password salt
- Non-root Docker user (uid 1000)
- SSRF prevention — image proxy restricted to allowed CDN domains
- Config endpoint masks sensitive values (TMDB keys/tokens) in API responses
- Password not persisted to config.json; sourced from environment variables only
- Path traversal prevention on font file operations
- CORS properly configured (credentials disabled with wildcard origins)
- NFO XML parsing with external entity resolution disabled

### Documentation

- Comprehensive CLAUDE.md for AI-assisted development
- Startup wizard for first-time configuration
- ENV-based configuration with `.env.example` template

### Auto-Update System

- Docker-based self-upgrade with DockerHub tag polling
- One-click update/rollback to any DockerHub tag version
- CHANGELOG viewer with full-screen darkened modal (fetches GitHub release notes)
- Update notification red dot on Settings nav (15-minute auto-check interval)
- `docker pull` + `docker compose up -d` restart flow
- `/api/version`, `/api/update/check`, `/api/update/perform`, `/api/update/changelog` endpoints
- Docker socket mount + `COMPOSE_FILE` env for container self-upgrade capability
