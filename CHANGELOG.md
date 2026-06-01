**English** | [简体中文](CHANGELOG_zh-CN.md)

# Changelog

All notable changes to MediaTree are documented here.

---

## 1.0.05 (2026-06-02)

### Branding

- Replaced the website favicon with the new MediaTree logo asset
- Replaced the login page logo mark with the new transparent PNG logo
- Updated README logo references to use the new repository-hosted PNG asset

### Release Type

- App-package update; no Docker image update is required

---

## 1.0.04 (2026-05-28)

### Full Image Update Required

- Marked this release as requiring a full Docker image update because the base frontend image, pinned backend runtime dependencies, container user, healthcheck, and compose runtime behavior changed
- Release manifests now carry `requires_image_update: true` plus an explicit reason so Settings can route users to the Docker image update path instead of app-package installation
- Settings now treats the highest installed image/app-package version as the single current version shown to users, so image and app-package releases stay on one shared version line without exposing layer-specific version splits in the UI
- When Docker CLI or `docker.sock` is unavailable, Settings now shows explicit host-side guidance to use `docker compose pull && docker compose up -d` instead of exposing raw container errors
- Container startup now automatically prefers the newer base image version over an older persisted app-package, so full image updates are no longer masked by stale `data/releases/current` pointers
- Stale failed Docker update status is now cleared once the target version is already installed, preventing old Docker CLI errors from reappearing on the current-version card

### Security & Access Control

- Replaced static bearer auth with signed session tokens and added short-lived media tokens for streams, covers, thumbnails, subtitles, external playlists, and static media files
- Hardened remote image fetching and local image serving so only safe image URLs and expected local roots are served
- Tightened backup restore extraction to reject unsafe archive members, links, device files, and tar paths escaping `data_dir`
- Redacted sensitive environment values from Docker self-update command logs and status output
- Made Jellyfin name/password authentication fail closed when primary app auth is not configured

### Setup & Scraper Configuration

- Fixed first-run setup so TMDB access token/API configuration can be saved before an authenticated session exists
- Cleared the frontend config cache after Settings saves scraper/TMDB configuration, so manual scraping immediately sees the updated TMDB state

### Build & Release Pipeline

- Added project Codex/ECC initialization files under `.agents/` and `.codex/`, plus CI validation for backend tests, backend compilation, and frontend builds
- Pinned backend dependencies with `backend/constraints.txt` while keeping `uvicorn[standard]` extras in `backend/requirements.txt`
- Updated Docker builds to Node 22, Python 3.12 dependency constraints, a non-root runtime user, and an HTTP healthcheck

---

## 1.0.03 (2026-05-25)

### App-Package Updates

- **Lightweight app-package updates**: Settings now downloads `mediatree-app-<version>.tar.gz` into `/app/data/releases`, so routine releases no longer need a full Docker image pull
- **Docker socket is advanced-only**: the default compose example no longer mounts `/var/run/docker.sock`; full image replacement remains available for base-image changes
- **Rollback and status tracking**: added `/api/update/status` and `/api/update/rollback`; failed app-package updates can roll back to the previous app package or the built-in image version
- **Release artifacts**: GitHub Releases now include the app archive, manifest, and sha256 checksum for update type, size, and integrity checks

### Settings Update UX

- The update panel always shows only the latest 3 versions
- App-package progress now appears inside the matching version card, and completed status no longer appears as a separate bar
- Rollback moved into the matching version row beside the changelog action
- Full image updates show Docker pull/helper logs directly inside the version card

### Player

- Added immersive Theater Mode with a dedicated viewing route, ambient backdrop, and focused playback layout
- Improved Theater Mode routing, controls, and exit behavior

### Deployment & Mobile

- Docker image layout now separates `/opt/mediatree/base` from updateable app packages under `/app/data/releases`
- Added an entrypoint launcher that prefers the current data-volume app package and falls back to the previous package or built-in base app
- Added Capacitor/Android build configuration and native app server URL support

---

## 1.0.02 (2026-05-25)

### UI Improvements

- **Toast z-index fix**: toast notifications and scan progress now render via `createPortal` to `document.body`, fixing an issue where they were hidden behind modal backdrops due to `#root` stacking context
- **Manual scrape progress toast**: after applying a manual scrape result, a progress indicator appears in the bottom-right with indeterminate animation, then auto-dismisses on completion
- **TMDB config warning**: toast reminder to configure TMDB API Key in Settings when performing scrape operations without TMDB credentials

### Backend

- `/api/config` now returns `tmdb_configured` field for frontend TMDB config detection

---

## 1.0.01 (2026-05-24)

### Performance

- **Scroll optimization**: `content-visibility: auto` on all media grid cards — browser skips rendering off-screen cards entirely
- **CSS containment**: `contain: layout style` on grid containers prevents layout thrashing during scroll
- Reduced `glass-card` backdrop-blur from 12px to 6px — negligible visual difference, 50% less GPU blur computation
- Narrowed `apple-focus` transition from `transition-all` to only `transform`, `box-shadow`, `border-color`
- Body noise texture (`feTurbulence` SVG) promoted to GPU compositing layer with `translateZ(0)`
- All 5 grid pages (Home, Folder, Browse, Favorites, MovieCard) now use `media-grid` and `media-grid-card` classes

### Self-Update Rewrite

- **docker inspect driven**: no longer depends on compose file mounts or `COMPOSE_FILE` env var — extracts container runtime configuration via `docker inspect`
- **Dual-path support**: compose-managed containers auto-reconstruct compose YAML + `compose up -d`, bare `docker run` containers auto-replay run commands
- **Version detection**: `get_current_version()` prefers Docker image tag via inspect, VERSION file as fallback; normalization supports `-test` suffix
- **Removed dependency**: no longer needs `docker-compose-plugin`; Dockerfile and compose template cleaned up
- **Version format**: `v` prefix removed, unified `1.0.01` format

### Fixes

- Scraper: switching to "none" immediately stops scraping and clears previously scraped content
- Browse page: removed JavDB score/likes badges, display filename as title, folder tree now follows sort order
- Fixed 10 CodeQL security alerts + subtitle test assertions
- CHANGELOG modal now renders via `createPortal` with proper Markdown rendering
- Removed `docker-compose.yml` from git tracking, replaced with `.example` template
- Logout fix: no longer clears active library on logout; `?logout=1` query param distinguishes explicit logout from fresh visit
- Settings page auto-polls version after update; button renamed to "切换到此版本"

---

## 1.0.00 (2026-05-23) — Initial Public Release

### Core Architecture

- **Backend**: Python 3.12 + FastAPI + Uvicorn, 87 RESTful API endpoints
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
- **Javdatabase** — JAV code-based metadata with fuzzy search fallback (strip dashes, prefix matching)
- Auto scraper with TMDB ID extraction from filenames and intelligent fallback chain
- Season/episode merge for TMDB multi-season compilations
- TMDB data pipeline fixes — genre, keywords, studios, tagline, status now persisted to DB
- 10 new API endpoints: person detail/filmography/photos, media images/videos/release dates/reviews, season posters, episode stills
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
- Container runs as root with Docker socket access for self-update capability
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

- Docker-based self-upgrade polling DockerHub tags for available versions
- One-click update or rollback to any published DockerHub tag version
- Helper-container architecture — isolates `docker compose up -d` in a separate `docker:cli` container to survive the main container restart (cgroup isolation)
- Full-screen darkened CHANGELOG modal fetching GitHub release notes on demand
- Update notification red dot on Settings navigation (15-minute auto-check interval)
- 4 dedicated API endpoints: `/api/version`, `/api/update/check`, `/api/update/perform`, `/api/update/changelog`
- Requires Docker socket mount (`/var/run/docker.sock`) and `COMPOSE_FILE` environment variable
- Configurable auto-check toggle and interval (`update_check_enabled`, `update_check_interval_hours`)
