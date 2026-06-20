# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Push Workflow

- Before each code change, read the current project guidance (`AGENTS.md`, `CLAUDE.md`, and any task-relevant docs).
- Before each push, sync `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, and `README.md` to reflect the current code state.
- Include documentation updates in the same commit; do not commit them separately.
- Include normative-document updates in the same commit whenever the implementation changes product behavior, architecture, workflows, release/update policy, or future agent instructions.
- Version rule: use `0.0.00` three-level format without `v` prefix (e.g., `1.0.01`, `1.0.02`), increment sequentially, no more skipping major/minor version numbers. When updating the version number, also create a corresponding GitHub Release (`gh release create 1.0.00`) synced with the CHANGELOG entry for that version.
- Default release decision rule: unless the user explicitly overrides it, automatically decide whether a change should ship as `app-package` or require a full Docker image update. Use `app-package` for pure application/frontend changes; require a full image update for Dockerfile/runtime/system-package/python/entrypoint/self-update capability changes or anything unsafe to deliver as an app package. Treat app-package and image releases as sharing one version baseline rather than two separate tracks. Ordinary pushes must not run the release workflow; manually trigger `.github/workflows/release-tag.yml` only when performing an app-package or full Docker image release. Every release refreshes DockerHub `zasenjc/mediatree:latest` from a local build/push (`scripts/push-docker-release.sh`), not GitHub Actions; only full Docker image updates also publish a versioned DockerHub tag such as `zasenjc/mediatree:1.0.10`.
- GitHub Release notes must stay user-facing: include concise functional changes and user upgrade guidance there; keep implementation details, configuration changes, test notes, and maintainer bookkeeping in `CHANGELOG.md` / `CHANGELOG_zh-CN.md`.

## Product Collaboration Rules

- Treat the user as a product manager with no programming background: translate natural-language requests into product goals, user workflows, and acceptance criteria before choosing the technical implementation.
- Do not require the user to provide technical terminology. When a request is vague, first infer the likely product intent from the repository context, state the interpretation in Chinese, and ask only the minimum necessary clarification if implementation would otherwise be risky.
- Build from the product outcome first, then map that outcome to code, tests, docs, and release steps.

## Interaction Language Rules

- All user-facing explanations, plans, summaries, question inquiries, and change reports must use Chinese.
- Keep code identifiers (function names, variable names, class names), file names, paths, commands, config keys, and error logs in their original English.
- Do not translate English API names, function names, class names, or module names into Chinese.

## Commands

### Backend (Python 3.12 + FastAPI)

```bash
# Install dependencies
cd backend && pip install -r requirements.txt -c constraints.txt

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

# Android native app (requires Capacitor + Android SDK)
cd frontend && npm run android:build
```

### Docker

```bash
# Build and run locally
docker compose up -d --build

# Multi-arch build + push for the current VERSION
scripts/push-docker-release.sh
```

Default Docker builds are size-optimized. Keep `INCLUDE_FULL_CJK_FONTS=false` and `INCLUDE_EMOJI_FONT=false` unless a release explicitly needs full Noto CJK or emoji packages; the base image keeps `fonts-wqy-microhei` plus the frontend bundled subtitle fallback font. Enabling those build args or changing Dockerfile/runtime font policy requires the full Docker image update path.

Application update packages must be produced by `scripts/build-app-package.sh`. Keep GitHub Actions and local release work on that shared builder so archives strip bytecode, pycache, source maps, and local metadata consistently.

### Configuration

Copy `.env.example` to `.env` and configure:
- `AUTH_USER` / `AUTH_PASS` — optional preconfigured web UI credentials; leave blank for first-run admin setup
- `TMDB_ACCESS_TOKEN` (optional) — enables TMDB API; Settings exposes only the TMDB read access token. Keep legacy `TMDB_API_KEY` backend compatibility hidden from Settings unless a future migration explicitly removes or redesigns it.
- `MEDIA_DIR` / `MEDIA_ALIAS` — default Docker Compose media bind source and `/media/<alias>` target; add extra bind mounts in `docker-compose.yml` for additional libraries
- `DATA_DIR` — persistent data (DB, covers, config), default `./data`
- `HOST_PORT` — default `27580`
- `BIND_ADDRESS` — default `0.0.0.0`; use `127.0.0.1` for local-only access
- Javdatabase is provided as a built-in scraper plugin. Select `Javdatabase` per library in Settings; there is no separate environment/config toggle for it. Scraper cache TTLs and the Javdatabase request interval are internal runtime policy, not user-facing env/config knobs.

## Architecture

### Two-process development
In production, the backend serves the built frontend at `/`. In development, run the backend on port 80 (`uvicorn --port 80`) and the Vite dev server on port 5173 — Vite proxies `/api/*` to `localhost:80` (configured in `vite.config.ts`).

### All backend logic lives in `backend/app/`
- `main.py` — FastAPI app, all 80+ route handlers, AuthMiddleware, lifespan hooks. This is a single large file (~1700 lines). No separate router modules. Middleware stack: `CORSMiddleware` (all origins), `AuthMiddleware` (Basic/Bearer signed sessions for `/api/*`), `SPAFallbackMiddleware` (serves `index.html` for SPA routing).
- `scanner.py` — Core scanning and scraping engine (~1800 lines): `scan_media()` walks filesystem, `scrape_for_library()` runs the fallback chain, per-library lock prevents duplicate concurrent scans.
- `auto_scrape.py` — Automatic scrape scheduling and watcher path policy. Coalesces affected media roots, filters relevant file/folder changes, and centralizes container-safe watcher polling defaults.
- `database.py` — All SQLite CRUD (~1150 lines): `init_db()` with schema migrations, movie/folder/tag/category ops, and Web playback progress in `user_data`.
- `config.py` — `pydantic-settings` + JSON config persistence. `Settings` class reads `.env`, then `load_persisted_config()` overlays `data/config.json` except for internal scraper cache/request policy keys. Runtime changes via `/api/config` POST write back to `config.json`.
- `models.py` — Pydantic v2 models: `Movie`, `JavdbCache`, `Category`, `Tag`, `ScanResult`, `FolderNode`.
- `stream.py` — Video streaming with HTTP Range support (byte-range seeking), ffmpeg transcoding, media info extraction via ffprobe.
- `covers.py` — Cover image management: download, compress (Pillow, max 500px, JPEG q=80), episode still generation.
- `title_match.py` — Title matching utilities: code extraction, TMDB ID token parsing, CJK/romaji extraction, season inference, folder clean name generation.
- `updater.py` — Two-tier self-update system. App-package mode: downloads `mediatree-app-<version>.tar.gz` into `data/releases/`, supports rollback to previous version, and cleans older packages after successful restart. Docker mode: `get_available_versions()` polls DockerHub tags, `perform_update()` pulls target image then restarts via `docker compose up -d`. `fetch_github_release_body()` fetches full GitHub release notes for the CHANGELOG modal.

### Scraper plugin system
- `base.py` — `BaseScraper` abstract class with `search() -> ScrapeCandidate` and `get_detail() -> ScrapeResult`. Dataclasses defined here.
- `registry.py` — Maps scraper names to instances. Built-ins are loaded from `backend/app/builtin_plugins/scrapers/*/plugin.json` manifests. Built-in: `tmdb_movie`, `tmdb_tv`, `tmdb_collection`, `bangumi`, `javdatabase`, `auto` (IMDB/TMDB ID → TMDB title → Bangumi chain), `none` (no-op). Use `get_scraper()` and `list_scrapers()`.
- `scraper_plugins.py` — Scraper plugin management service. Installs trusted local `.zip` plugins into `settings.data_dir/scraper_plugins/<name>/<version>/`, validates archive boundaries and manifests, keeps uploaded plugins disabled until explicitly enabled, prevents names reserved by built-ins/aliases, and stores Settings control state for built-in scrapers. Built-ins can be disabled or hidden from Settings without deleting application-shipped code.
- `tmdb_scraper.py`, `bangumi_scraper.py`, `javdatabase_scraper.py` — Thin adapters wrapping `tmdb.py`, `bangumi.py`, `javdb.py`.
- `auto_scraper.py`, `none_scraper.py` — Core classes used by the built-in `auto` and `none` plugin entrypoints.
- `backend/app/builtin_plugins/scrapers/<name>/plugin.py` — Thin built-in plugin entrypoint that subclasses or configures the reusable scraper class.
- `utils.py` — Shared helper functions for scraper result processing.
- Scraper cache TTLs are internal defaults (TMDB/Bangumi 168h, Javdatabase 24h). Empty results are not cached; manual scans/rescrapes/manual apply bypass scraper cache. Javdatabase network requests are internally spaced at least 3s apart.
- To add an application-shipped scraper: add the reusable class under `backend/app/scrapers/`, then add `plugin.json` and `plugin.py` under `backend/app/builtin_plugins/scrapers/<name>/`. To add a user-installed scraper: upload a valid plugin zip from Settings and enable it.

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
- `AuthMiddleware` guards `/api/*` routes using Basic auth or signed Bearer session tokens from `/api/auth/login`
- Media delivery routes require app auth or a short-lived media token from `/api/media-token`; this covers streams, subtitles, covers, thumbnails, external playlists, and `/api/media/*`
- Public/limited bypasses remain intentionally narrow: SPA assets, fixed brand assets (`/login-logo.png`, `/site-logo.png`), `/api/auth/login`, `/api/auth/status`, `/api/setup/status`, `/api/health`, `/api/version`, cached covers, font reads, and `/api/update/check`
- First-run `POST /api/setup/save` is allowed without a session only while no library settings exist
- Library-level passwords stored in `library_settings` table, verified via `/api/library-verify`

### File watcher (`watcher.py`)
- Uses `watchfiles.awatch()` with 15s debounce on enabled media roots
- Defaults to watchfiles polling inside containers (`poll_delay_ms=1000`) so Docker Desktop bind-mounted libraries do not miss host-side file moves; override with `FILE_WATCHER_FORCE_POLLING` and `FILE_WATCHER_POLL_DELAY_MS`
- Treats file/folder added and deleted events as media-library structure changes; modified events are filtered to video/subtitle/NFO/cover paths and real directories
- Merges batched changes by media_root, triggers `run_scan_for_root(trigger="watcher")`
- If a scan is already in progress for a root, marks "queued" and re-scans after current scan completes

### Update / self-upgrade system (`updater.py`)
- Two-tier update strategy: lightweight app-package (default) and full Docker image (optional, requires Docker socket mount and a Docker-CLI-capable image)
- GitHub Actions publishes the app package for every release. DockerHub sync is local-only: run `scripts/push-docker-release.sh` after release validation to refresh `zasenjc/mediatree:latest`; full image releases additionally publish `zasenjc/mediatree:<version>`
- App-package archives must be built by `scripts/build-app-package.sh`; Docker image pushes use slim defaults unless full CJK or emoji fonts are required and documented for that release.
- App-package flow: `GET /api/update/check` → `POST /api/update/perform` downloads `mediatree-app-<version>.tar.gz` into `data/releases/` → `mark_update_success_after_restart()` on next startup marks success and cleans older packages → `POST /api/update/rollback` to revert to previous version
- Docker flow: `docker pull zasenjc/mediatree:<tag>` + `docker compose up -d` restart
- `GET /api/version` — return the user-visible current version (highest installed version), plus runtime/image details for internal update decisions (public, no auth)
- `GET /api/update/changelog?version=0.0.00` — fetch full GitHub release body for CHANGELOG modal
- `GET /api/update/status` — return current app-package update status
- Frontend auto-checks every 15 minutes in `App.tsx`, shows red dot on the Settings gear in the right action capsule when update available
- Settings page update panel: version list with "更新日志" (modal), app-package "下载并更新", old-version "回滚此版本", and full-image "完整镜像更新" actions
- CHANGELOG modal: full-screen darkened backdrop (`bg-black/60 backdrop-blur-sm`), centered `glass-modal` panel
- Docker self-upgrade requires `docker.sock` access and a Docker-CLI-capable image; app-package mode does not require Docker socket access
- Update comparisons must use the higher of the app-package version and image base version as the effective baseline, so image/package releases do not drift into separate version tracks

### Atomic scan flow
```
scan_media(root)
  → upsert_movie() for each file (fills local fields: path, code, clean_title, episode_number, display_title, cover_local)
  → mark files under `sp` directory segments as `content_role='special'` with `special_parent_levels`
  → cleanup_deleted_files() (removes DB entries for missing files)
  → scrape_for_library() (network metadata for unscraped non-special movies, using configured scraper + fallback chain)
```

- Root-level orphan `sp` folders are skipped; nested `sp` folders are treated as specials for their parent folder.
- Specials stay out of home/search/favorites/recent/episode lists by default and are loaded through the folder specials API when shown.

### Fallback chain (in `scanner.py`)
- `javdatabase` scraper: independent (only searches by JAV code, no fallback)
- `javdatabase` should not run for specials, and should require an explicit local code rather than scraping noisy titles.
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
- API client in `api.ts`: single `request()` function with 120s TTL cache, auth token management, all typed methods. Supports `VITE_API_BASE_URL` env override for Capacitor native app.
- `cache.ts`: `clearCache()` called after mutations (rescrape, delete, edit)
- `store.ts`: excluded folders and UI preferences (e.g. `hideHomeTitleText`, `ambientMode`, `showSourceName`) persisted in localStorage
- `scroll.ts`: scroll position save/restore in sessionStorage
- `theater.tsx`: theater/cinema mode state management for immersive playback
- `toast.ts`: toast notification system for transient messages
- `taskProgress.ts`: task progress tracking for scrape/scan operations
- All pages are in `src/pages/`, components in `src/components/`, utilities in `src/utils/`
- `src/pages/`: `Home.tsx` (media grid), `Folder.tsx` (folder tree), `Browse.tsx` (seasonal tabs), `Detail.tsx`, `Favorites.tsx`, `Settings.tsx`, `Login.tsx`, `SetupWizard.tsx`
- `src/components/`: `MovieCard.tsx`, `VideoPlayer.tsx`, `EditModal.tsx`, `ManualScrapeModal.tsx`, `CoverPickerModal.tsx`, `JavdbPanel.tsx`, `MovieInfoPanel.tsx`, `LibraryModal.tsx`, `PasswordModal.tsx`, `ContextMenu.tsx`, `Lightbox.tsx` (image lightbox with gesture navigation), `ScanToast.tsx`, `SortDropdown.tsx`, `WatchedBadge.tsx`, `ErrorBoundary.tsx`, `VRVideoLayer.tsx` (VR/360° video via Three.js)
- `src/utils/`: `polling.ts`, `vttParser.ts` (WebVTT subtitle parser)
- `src/hooks/`: `useSearch.ts`
- `src/constants/`: `sortOptions.ts`
- `App.tsx`: root component with glassmorphism nav bar, route definitions (`/`, `/folder`, `/browse`, `/detail/:id`, `/favorites`, `/settings`, `/login`, `/setup`), search overlay (desktop dropdown + mobile standalone bar), library modal. Modal/overlay backdrops generally use `bg-black/40 backdrop-blur-2xl z-[60]` to sit above sticky header (`z-50`); the Settings drawer is the exception and keeps a transparent click-capture backdrop so liquid glass applies only to the drawer panel.
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
  - `liquid-glass` — animated liquid glass background effect
- Also includes: theater/cinema mode styles (`.theater-active`), player customizations, scroll optimization (content-visibility, will-change), markdown changelog rendering styles
- Navigation header: two separate glass capsules (brand+nav left, actions right). Settings lives as a gear icon in the right action capsule next to search, with the update red dot anchored to that icon. On mobile (<380px), "MediaTree" abbreviates to "MT"; Favorites is hidden in the "..." dropdown on mobile.
- Search: desktop inline search in actions capsule; mobile standalone search bar triggered by magnifying glass icon. Both share same results panel (`glass-popover`).

### Android / Capacitor native app
- `capacitor.config.ts` — Capacitor 8 config: `appId: com.zasenjc.mediatree`, web dir is `dist/`
- `npm run android:sync` — build frontend + `cap sync android`
- `npm run android:build` — sync + `sh scripts/build-android.sh`
- `npm run android:open` — `cap open android`
- Native app uses `VITE_API_BASE_URL` env to point to backend server (see `api.ts`)

### Where to modify for common tasks
- Style changes: `index.css` (`@layer components` for global glass-* / apple-focus classes) + `tailwind.config.js` (color palette, shadows, backgrounds) + `pages/*.tsx` / `components/*.tsx` (use predefined component classes)
- Glass component class reference: `glass-panel` (large container), `glass-card` (card), `glass-button` (default button), `glass-button-primary` (primary button), `glass-input` (input field), `glass-popover` (popover), `glass-modal` (dialog), `glass-chip` (tag), `apple-focus` (hover animation)
- New API: `main.py` (route) + `database.py` (CRUD) + `api.ts` (frontend client)
- New built-in scraper: create the reusable class under `backend/app/scrapers/`, then add `plugin.json` and `plugin.py` under `backend/app/builtin_plugins/scrapers/<name>/`
- Scan logic: `scanner.py` `scan_media()` / `scrape_for_library()`
- Cover handling: `scanner.py:_apply_scraped_data()` + `database.py:_normalize_cover_path()`
- Player/subtitles: `VideoPlayer.tsx` + `artplayerPluginAss.ts`; playback pages update `document.title` with `▶` / `⏸` plus the current title until the user leaves the page
- File watching: `watcher.py`
- Update / self-upgrade: `updater.py` + `main.py` (`/api/update/*` routes) + `Settings.tsx` (update panel). App-package mode (default) does not require Docker socket; Docker image mode requires `docker.sock` mount.
