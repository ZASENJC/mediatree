# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Push Workflow

- Before each push, sync `CLAUDE.md`, `CHANGELOG.md`, and `README.md` to reflect the current code state.
- Include documentation updates in the same commit; do not commit them separately.
- Version rule: use `0.0.00` three-level format without `v` prefix (e.g., `1.0.01`, `1.0.02`), increment sequentially, no more skipping major/minor version numbers. DockerHub tags must also use the same format without `v` prefix.

## Interaction Language Rules

- All user-facing explanations, plans, summaries, question inquiries, and change reports must use Chinese.
- Keep code identifiers (function names, variable names, class names), file names, paths, commands, config keys, and error logs in their original English.
- Do not translate English API names, function names, class names, or module names into Chinese.

## Commands

### Backend (Python 3.12 + FastAPI)

```bash
# Install dependencies
cd backend && pip install -r requirements.txt

# Run backend locally (port 80, proxy from frontend Vite dev server)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Run a single test
PYTHONPATH=backend python -m unittest backend.tests.test_anime_naming

# Run all backend tests
cd backend && PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py'
```

### Frontend (React 18 + TypeScript 5 + Vite)

```bash
# Install dependencies
cd frontend && npm install

# Dev server (hot reload, proxies /api to localhost:80)
cd frontend && npm run dev

# Production build
cd frontend && npm run build
```

### Docker

```bash
# Build and run locally
docker compose up -d --build

# Multi-arch build + push
docker buildx build --platform linux/amd64,linux/arm64 -t zasenjc/mediatree:1.0.00 --push .
```

## Architecture

### Two-process development
In production, the backend serves the built frontend at `/`. In development, run the backend on port 80 (`uvicorn --port 80`) and the Vite dev server on port 5173 — Vite proxies `/api/*` to `localhost:80` (configured in `vite.config.ts`).

### All backend logic lives in `backend/app/`
- `main.py` — FastAPI app, all 60+ route handlers, AuthMiddleware, lifespan hooks. This is a single large file (~1100 lines). No separate router modules.
- `scanner.py` — Core scanning and scraping engine (~1800 lines): `scan_media()` walks filesystem, `scrape_for_library()` runs the fallback chain, per-library lock prevents duplicate concurrent scans.
- `database.py` — All SQLite CRUD (~1000 lines): `init_db()` with schema migrations, movie/folder/tag/category ops, Jellyfin user_data/playback_sessions/tokens tables.
- `config.py` — `pydantic-settings` + JSON config persistence. `Settings` class reads `.env`, then `load_persisted_config()` overlays `data/config.json`. Runtime changes via `/api/config` POST write back to `config.json`.
- `updater.py` — Docker self-update system. `get_available_versions()` polls DockerHub tags for version list. `perform_update()` pulls target image (`docker pull zasenjc/mediatree:<tag>`) then restarts via `docker compose up -d`. `fetch_github_release_body()` fetches full GitHub release notes for the CHANGELOG modal.

### Scraper plugin system (`backend/app/scrapers/`)
- `base.py` — `BaseScraper` abstract class with `search() -> ScrapeCandidate` and `get_detail() -> ScrapeResult`. Dataclasses defined here.
- `registry.py` — Maps scraper names to instances. Built-in: `tmdb_movie`, `tmdb_tv`, `bangumi`, `javdatabase`, `auto`, `none`. Use `register_scraper()`/`get_scraper()`.
- `tmdb_scraper.py`, `bangumi_scraper.py`, `javdatabase_scraper.py` — Thin adapters wrapping `tmdb.py`, `bangumi.py`, `javdb.py`.
- To add a scraper: create new file here, subclass `BaseScraper`, register in `registry.py`.

### Jellyfin compatibility layer
- `jellyfin_compat.py` (~1300 lines) — 30+ endpoints under `/System/`, `/Users/`, `/Items/`, `/Videos/`, `/Sessions/`. These routes are whitelisted in `AuthMiddleware` and use PascalCase JSON.
- `jellyfin_mappers.py` — Converts MediaTree DB rows to Jellyfin JSON. Implements Series/Season/Episode hierarchy from folder structure (`ShowName/S01/E01.mkv`).
- `jellyfin_auth.py` — Handles MediaBrowser Token / X-Emby-Token / Bearer / api_key auth for Jellyfin clients.
- `jellyfin_models.py` — Pydantic models for incoming Jellyfin requests.

### Subtitle rendering pipeline
1. Backend: `subtitles.py` detects embedded (ffprobe) + external subtitles (basename + lang suffix matching). ASS passthrough; SRT/other converted to WebVTT via ffmpeg.
2. Frontend: `artplayerPluginAss.ts` renders ASS/SSA via `@jellyfin/libass-wasm` canvas with CJK fallback font (`/fonts/SourceHanSansCN-Bold.woff2`). VTT/SRT use ArtPlayer's native subtitle layer.
3. Font management: System CJK fonts (Noto/WenQuanYi in Docker) + user uploads exposed via `/api/subtitle-fonts`.

### Database (SQLite via aiosqlite)
- WAL mode, `busy_timeout=5000ms`
- Schema migrations live in `database.py:init_db()` — ALTER TABLE statements after initial CREATE
- No `datetime('now')` defaults (SQLite limitation); timestamps set in application code
- Single-writer semaphore serializes SQLite writes across concurrent scrapers

### Auth system
- `AuthMiddleware` guards `/api/*` routes using Basic/Bearer auth
- Whitelisted paths bypass auth entirely — covers streaming, subtitles, covers, fonts, Jellyfin compat routes
- Jellyfin clients use separate `jellyfin_auth.py` token system (tokens stored in `jellyfin_tokens` table)
- Library-level passwords stored in `library_settings` table, verified via `/api/library-verify`

### File watcher (`watcher.py`)
- Uses `watchfiles.awatch()` with 15s debounce on enabled media roots
- Only processes video/subtitle/NFO/cover file extensions
- Merges batched changes by media_root, triggers `run_scan_for_root(trigger="watcher")`
- If a scan is already in progress for a root, marks "queued" and re-scans after current scan completes

### Update / self-upgrade system (`updater.py`)
- `GET /api/version` — return current version from VERSION file (public, no auth)
- `GET /api/update/check` — return DockerHub tag list (public, no auth), merged & sorted descending
- `POST /api/update/perform` — `docker pull zasenjc/mediatree:<tag>` + `docker compose up -d` restart
- `GET /api/update/changelog?version=v0.0.00` — fetch full GitHub release body for CHANGELOG modal
- Frontend auto-checks every 15 minutes in `App.tsx`, shows red dot on Settings nav when update available
- Settings page update panel: version list with "更新日志" (modal) and "更新到此版本" (docker pull) buttons
- CHANGELOG modal: full-screen darkened backdrop (`bg-black/60 backdrop-blur-sm`), centered `glass-modal` panel
- Requires `docker.sock` mount and `COMPOSE_FILE` env for self-upgrade to work

### Atomic scan flow
```
scan_media(root)
  → upsert_movie() for each file (fills local fields: path, code, clean_title, episode_number, display_title, cover_local)
  → cleanup_deleted_files() (removes DB entries for missing files)
  → scrape_for_library() (network metadata for unscraped movies, using configured scraper + fallback chain)
```

### Fallback chain (in `scanner.py`)
- `javdatabase` scraper: independent (only searches by JAV code, no fallback)
- `tmdb_movie` scraper: TMDB movie ID/title → Bangumi → TMDB movie title search
- `tmdb_tv` scraper: TMDB tv ID/title → Bangumi → TMDB tv title search
- `bangumi` scraper: Bangumi → TMDB tv title search
- `auto` scraper: TMDB ID exact match (with movie/tv inference) → Bangumi → TMDB title search

### Anime naming (`anime_naming.py`)
- `parse_anime_filename()` strips release groups (e.g., `[ANi]`, `[VCB-Studio]`) and technical tags (`[1080P]`, `[x265_flac]`)
- Extracts episode numbers from `[01]`, `[EP01]`, `S01E01`, `1x01`, `第1话` patterns
- Returns `clean_title`, `episode_number`, `display_title`
- Applied during `scan_media()` — local fields only, won't overwrite TMDB/Bangumi scraped data

### Cover image handling
- `cover_local`: path-based cache key → served via `/api/cached-cover/{key}` (Pillow resized to max 500px, JPEG q=80)
- `cover_remote`: direct URL, used as `<img src>`
- `fanart_local`: folder hero background image
- Episode stills stored in `data/stills/`

### Frontend key patterns
- API client in `api.ts`: single `request()` function with 120s TTL cache, auth token management, all typed methods
- `cache.ts`: `clearCache()` called after mutations (rescrape, delete, edit)
- `store.ts`: excluded folders and UI preferences (e.g. `hideHomeTitleText`) persisted in localStorage
- `scroll.ts`: scroll position save/restore in sessionStorage
- All pages are in `src/pages/`, components in `src/components/`, utilities in `src/utils/`
- `App.tsx`: root component with glassmorphism nav bar, route definitions (`/`, `/folder`, `/browse`, `/detail/:id`, `/favorites`, `/settings`, `/login`, `/setup`), search overlay (desktop dropdown + mobile standalone bar), library modal. All modal/overlay backdrops use `bg-black/40 backdrop-blur-2xl z-[60]` to sit above sticky header (`z-50`).
- `ContextMenu.tsx`: singleton right-click menu with glassmorphism inline styles (backdrop blur, rounded-2xl, semi-transparent background)

### UI Design System (Glassmorphism + Apple style)
- `tailwind.config.js` defines custom color palettes: `apple-*` (blue/purple/pink/mint/yellow), `glass-*` (surface/elevated/border/muted), `dark-*` (retained for legacy), plus custom shadows (`glass`, `glow`, `card`) and `aurora` background.
- `index.css` defines reusable `@layer components` classes — use these instead of raw Tailwind classes for consistency:
  - `glass-panel` — large container (rounded-3xl, heavy blur, shadow-glass)
  - `glass-card` — card element (rounded-2xl, medium blur, shadow-card)
  - `glass-button` / `glass-button-primary` — pill buttons (rounded-full, glass or apple-blue tinted)
  - `glass-input` — form input (rounded-2xl, glass surface, apple-blue focus ring)
  - `glass-popover` — dropdown/popover (rounded-2xl, white-based translucent glass, heavy blur)
  - `glass-modal` — modal dialog (rounded-3xl, white-based translucent glass, heavy blur)
  - `glass-chip` — inline tag/pill (rounded-full, translucent)
  - `apple-focus` — card hover animation (translate-y -1, scale 1.02, glow shadow)
- Navigation header: two separate glass capsules (brand+nav left, actions right). On mobile (<380px), "MediaTree" abbreviates to "MT". Favorites/Settings hidden in "..." dropdown on mobile.
- Search: desktop inline search in actions capsule; mobile standalone search bar triggered by magnifying glass icon. Both share same results panel (`glass-popover`).

### Where to modify for common tasks
- Style changes: `index.css` (`@layer components` for global glass-* / apple-focus classes) + `tailwind.config.js` (color palette, shadows, backgrounds) + `pages/*.tsx` / `components/*.tsx` (use predefined component classes)
- Glass component class reference: `glass-panel` (large container), `glass-card` (card), `glass-button` (default button), `glass-button-primary` (primary button), `glass-input` (input field), `glass-popover` (popover), `glass-modal` (dialog), `glass-chip` (tag), `apple-focus` (hover animation)
- New API: `main.py` (route) + `database.py` (CRUD) + `api.ts` (frontend client)
- New scraper: create in `backend/app/scrapers/`, subclass `BaseScraper`, register in `registry.py`
- Scan logic: `scanner.py` `scan_media()` / `scrape_for_library()`
- Cover handling: `scanner.py:_apply_scraped_data()` + `database.py:_normalize_cover_path()`
- Player/subtitles: `VideoPlayer.tsx` + `artplayerPluginAss.ts`
- Jellyfin compat: `jellyfin_compat.py` (routes) + `jellyfin_mappers.py` (data mapping)
- File watching: `watcher.py`
- Update / self-upgrade: `updater.py` + `main.py` (`/api/update/*` routes) + `Settings.tsx` (update panel)
