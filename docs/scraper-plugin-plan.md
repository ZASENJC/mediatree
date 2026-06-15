# Scraper Pluginization Plan

## Summary

Implement trusted local scraper plugins that can be uploaded from the Settings page, installed into the runtime data directory, enabled explicitly, and selected per library. Plugins reuse the existing `BaseScraper`, `ScrapeCandidate`, and `ScrapeResult` backend contract.

This v1 treats uploaded plugins as trusted local code. It does not sandbox third-party code. Safety comes from authentication, archive validation, path isolation, manifest validation, explicit enablement, and reserved-name protection.

## Backend Changes

- Add persistent plugin state in SQLite via `scraper_plugins`:
  - `name`, `version`, `label`, `description`, `supported_media_types`, `entrypoint`, `class_name`, `installed_path`, `enabled`, `builtin`, `installed_at`, `updated_at`, `error`.
- Add a scraper plugin service responsible for:
  - validating `.zip` uploads by size, extension, file count, path traversal, symlinks, and required `plugin.json`;
  - validating manifest fields and reserved built-in name collisions;
  - installing files under `settings.data_dir/scraper_plugins/<name>/<version>/`;
  - loading enabled plugin classes that subclass `BaseScraper`;
  - returning plugin state without exposing local paths to the frontend.
- Extend `backend/app/scrapers/registry.py` so `list_scrapers()` and `get_scraper()` include enabled plugin scrapers after built-ins.
- Replace scraper-name hardcoded validation in `database.py` and `scanner.py` with registry-aware validation while preserving aliases like `tmdb -> tmdb_movie`.
- Add API routes:
  - `GET /api/scrapers`
  - `GET /api/scraper-plugins`
  - `POST /api/scraper-plugins/install`
  - `POST /api/scraper-plugins/{name}/enable`
  - `POST /api/scraper-plugins/{name}/disable`
  - `DELETE /api/scraper-plugins/{name}`

## Frontend Changes

- Add scraper/plugin types and API helpers.
- Load scraper options dynamically in Settings, manual scrape modals, movie cards, and folder manual scrape UI.
- Keep `Javdatabase` visibility restricted to libraries using `javdatabase` where current behavior requires it.
- Add a Settings scraper plugin management panel with upload, installed state, enable/disable, and uninstall controls.

## Security Rules

- Plugin installation requires normal app authentication through existing middleware.
- Accept only `.zip` uploads below the backend size limit.
- Reject archives containing absolute paths, `..`, symlinks, directories outside the plugin root, excessive file counts, or disallowed manifest names.
- Reject plugin names that collide with built-ins or aliases.
- Install plugins disabled by default.
- Do not expose `installed_path` through public API responses.
- Do not log plugin source code or secrets.

## Test Plan

- Unit tests for manifest validation, path traversal rejection, reserved-name rejection, and successful install.
- Registry tests proving disabled plugins are listed as installed but not selectable, enabled plugins become selectable and loadable.
- API integration tests for install/list/enable/disable/delete and auth protection.
- Existing scanner and scraper tests must continue passing.
- Frontend build must pass after dynamic scraper option typing updates.

