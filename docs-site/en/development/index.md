# Development Guide

## Project Structure

```text
mediatree/
├── backend/               # Python 3.12 + FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI app and route handlers
│   │   ├── scanner.py     # scanning and scraping engine
│   │   ├── database.py    # SQLite CRUD
│   │   ├── config.py      # pydantic-settings + JSON persistence
│   │   ├── stream.py      # video stream, Range, transcoding
│   │   ├── subtitles.py   # subtitle detection and conversion
│   │   └── scrapers/      # scraper plugin system
│   └── tests/
├── frontend/              # React 18 + TypeScript + Vite
├── docs-site/             # VitePress documentation site
└── Dockerfile
```

## Local Development

Production serves the built frontend from the backend. Development usually runs two processes:

```bash
# Backend
cd backend
pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Frontend
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `localhost:80`.

## Docs Site Development

```bash
cd docs-site
npm ci
npm run dev
```

Build:

```bash
cd docs-site
npm run build
```

The docs site deploys to GitHub Pages at `/mediatree/`. Keep the docs deployment workflow separate from app-package release publishing.

## Tests and Builds

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'
python3.11 -m compileall -q backend/app
cd frontend && npm run build
```

On macOS, local `python3` may point to an older version. Prefer Python 3.11+. The production image uses Python 3.12.

## Adding APIs

1. Add the route in `backend/app/main.py`.
2. Add CRUD in `backend/app/database.py` when persistence is needed.
3. Add a typed frontend client method in `frontend/src/api.ts`.
4. Use it from pages or components and add tests.

## Adding Scrapers

User-installable scrapers should be packaged as `.zip` plugins with `plugin.json` and a Python entry class that inherits `BaseScraper`. The full plugin package structure, manifest fields, install/enable flow, and test checklist are currently documented in the Chinese [Scraper Plugin Guide](/development/scraper-plugin-guide).

When maintaining built-in scrapers, use `backend/app/builtin_plugins/scrapers/<name>/plugin.json` and `plugin.py` to connect them to the manifest-driven registry. Shared core logic can still live under `backend/app/scrapers/`. Built-in scrapers also appear in Settings plugin management, where users can disable or hide them.
