# Development

## Project Structure

```
mediatree/
├── backend/               # Python 3.12 + FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI app, 85+ route handlers
│   │   ├── scanner.py     # Core scan & scrape engine
│   │   ├── database.py    # SQLite CRUD operations
│   │   ├── config.py      # pydantic-settings + JSON persistence
│   │   ├── stream.py      # Video streaming (Range, transcode)
│   │   ├── subtitles.py   # Subtitle detection & conversion
│   │   ├── covers.py      # Cover image download & caching
│   │   ├── watcher.py     # File system watcher
│   │   ├── anime_naming.py # Anime filename parser
│   │   ├── tmdb.py        # TMDB API client
│   │   ├── bangumi.py     # Bangumi API client
│   │   ├── javdb.py       # JavDatabase scraper
│   │   ├── jellyfin_compat.py  # Jellyfin API routes
│   │   ├── jellyfin_mappers.py # Data mapping
│   │   ├── jellyfin_auth.py    # Jellyfin auth
│   │   └── scrapers/      # Scraper plugin system
│   └── tests/             # Unit tests
│
├── frontend/              # React 18 + TypeScript 5
│   ├── src/
│   │   ├── App.tsx        # Root component + routes + nav
│   │   ├── api.ts         # API client (120s TTL cache)
│   │   ├── cache.ts       # Response cache
│   │   ├── store.ts       # localStorage preferences
│   │   ├── pages/         # 8 page components
│   │   ├── components/    # 16 reusable components
│   │   ├── utils/         # Helpers (VTT parser, polling)
│   │   └── index.css      # Glassmorphism design system
│   └── public/fonts/      # Bundled fonts
│
├── data/                  # Runtime data (gitignored)
├── Dockerfile             # Multi-stage build
├── docker-compose.yml     # Docker deployment
└── .env.example           # Environment template
```

## Local Development

### Two-Process Development

In production, the backend serves the built frontend at `/`. For development, run them separately:

```bash
# Terminal 1 — Backend on port 80
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Terminal 2 — Frontend on port 5173
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` requests to `localhost:80` (configured in `vite.config.ts`).

### Running Tests

```bash
# All tests
cd backend
python -m unittest discover -s tests -p 'test_*.py'

# Single test file
python -m unittest tests.test_anime_naming

# Specific test
python -m unittest tests.test_scanner_tmdbid.TestSomething.test_method
```

### Building for Production

```bash
# Frontend build
cd frontend && npm run build

# Backend syntax check
python -m compileall backend/app

# Docker build (multi-arch)
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t mediatree:dev .
```

## Architecture Patterns

### Backend

- **Single-file router**: All API routes in `main.py` (~1580 lines). No separate router modules.
- **Auth middleware**: `AuthMiddleware` guards `/api/*` routes with Basic/Bearer auth. Whitelisted paths bypass auth.
- **Lifespan hooks**: DB init, Jellyfin startup, initial scan, and file watcher all managed in FastAPI lifespan.
- **SQLite WAL mode**: Enabled for better concurrent read performance.

### Frontend

- **API cache**: 120s TTL with automatic invalidation on mutations (re-scrape, delete, edit)
- **Glassmorphism components**: CSS utility classes in `index.css` layer — use `glass-panel`, `glass-card`, etc.
- **Portal rendering**: Modals and lightbox render to `document.body` to avoid z-index stacking issues.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite over PostgreSQL | Zero-config, single-file backup, WAL mode sufficient for single-user workloads |
| Single-file main.py | Simpler to maintain for this project scale; no circular import issues |
| Client-side subtitle rendering | Avoids server ffmpeg transcoding; enables ASS effects via libass-wasm |
| DirectPlay by default | Modern clients support most codecs; avoids server CPU load |
| File watcher over polling | Real-time updates with minimal overhead via `watchfiles` |

## Adding New Features

### New API Endpoint

1. Add route in `main.py`
2. Add CRUD function in `database.py` if needed
3. Add typed method in `frontend/src/api.ts`
4. Use in page/component

### New Scraper

1. Create `backend/app/scrapers/name_scraper.py`
2. Subclass `BaseScraper`, implement `search()` and `get_detail()`
3. Register in `registry.py`
4. The `auto` fallback chain handles the rest

### New Frontend Component

1. Create in `frontend/src/components/`
2. Use TailwindCSS utility classes with glassmorphism component classes
3. Use React Portal for modals/overlays
4. Add route in `App.tsx` if it's a new page

## Code Style

- **Backend**: Standard Python conventions. Type hints on function signatures.
- **Frontend**: Functional components with hooks. TypeScript strict mode.
- **CSS**: Tailwind utility classes. Custom components via `@layer components` in `index.css`.
- **Naming**: English identifiers (functions, variables, classes). Chinese documentation and comments.
