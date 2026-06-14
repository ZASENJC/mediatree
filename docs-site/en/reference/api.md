# API Reference

MediaTree's API primarily serves the Web frontend and external playback links. Except for health checks, login, and first-run setup endpoints, `/api/*` requires application authentication.

## Authentication

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/auth/login` | Sign in and receive a session token. |
| `POST` | `/api/auth/setup` | Create the first admin account. |
| `GET` | `/api/auth/status` | Read auth and setup status. |
| `POST` | `/api/auth/change-password` | Change the admin password. |
| `POST` | `/api/media-token` | Get a short-lived media access token. |

## Libraries and Scanning

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Health check. |
| `GET` | `/api/scan` | Start a scan. |
| `GET` | `/api/scan/status` | Read scan status. |
| `GET` | `/api/scan/log` | Read scan logs. |
| `GET` | `/api/media-roots` | List media roots. |
| `GET` | `/api/library-settings` | Read library settings. |
| `POST` | `/api/library-settings` | Save library settings. |
| `POST` | `/api/library/clear` | Clear library data. |

## Browsing and Details

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/folders` | Get folder tree and folder-level metadata. |
| `GET` | `/api/movies` | List movies. |
| `GET` | `/api/search` | Search movies. |
| `GET` | `/api/favorites` | List favorites. |
| `GET` | `/api/detail/{movie_id}` | Get movie details. |
| `GET` | `/api/recent-watched` | Get continue-watching items. |
| `GET` | `/api/categories` | List categories. |
| `POST` | `/api/categories` | Create a category. |
| `PUT` | `/api/categories/{cat_id}` | Update a category. |
| `DELETE` | `/api/categories/{cat_id}` | Delete a category. |

## Playback, Subtitles, and Media Files

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/stream/{movie_id}` | Stream video with Range and fallback transcoding. |
| `GET` | `/api/media-info/{movie_id}` | Read media information. |
| `GET` | `/api/external-play/{movie_id}.m3u` | Generate an external player playlist. |
| `GET` | `/api/subtitle-tracks/{movie_id}` | List subtitle tracks. |
| `GET` | `/api/subtitle/{movie_id}/{track_index}` | Read Web subtitles. |
| `GET` | `/api/subtitle-file/{movie_id}/{track_index}/{filename}` | Read subtitle files. |
| `GET` | `/api/media/{file_path}` | Read a media file path. |

## Covers and Images

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/cover/{movie_id}` | Get movie cover. |
| `GET` | `/api/cached-cover/{cache_key}` | Get cached cover. |
| `GET` | `/api/episode-still/{movie_id}` | Get episode still. |
| `GET` | `/api/thumbnail/{movie_id}/{index}` | Get thumbnail. |
| `POST` | `/api/movies/{movie_id}/cover` | Change movie cover. |
| `POST` | `/api/folder/cover` | Change folder cover. |
| `POST` | `/api/folder/backdrop` | Change folder backdrop. |

## Scraping and Metadata

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/movies/{movie_id}/rescrape` | Rescrape a movie. |
| `POST` | `/api/movies/{movie_id}/manual-scrape` | Apply manual movie scrape result. |
| `POST` | `/api/rescrape-folder` | Rescrape a folder. |
| `POST` | `/api/search-scrape` | Search scrape candidates. |
| `POST` | `/api/apply-folder-scrape` | Apply folder scrape result. |
| `POST` | `/api/javdb/fetch` | Fetch Javdatabase information by code. |

## Updates, Backup, and Settings

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/config` | Read runtime config. |
| `POST` | `/api/config` | Save runtime config. |
| `GET` | `/api/backup` | Download backup. |
| `POST` | `/api/restore` | Restore from backup. |
| `POST` | `/api/restore/upload` | Upload and restore a backup. |
| `GET` | `/api/version` | Read current version and runtime layer details. |
| `GET` | `/api/update/check` | Check available updates. |
| `POST` | `/api/update/perform` | Perform update. |
| `GET` | `/api/update/status` | Read update status. |
| `POST` | `/api/update/rollback` | Roll back an app-package update. |
| `GET` | `/api/update/changelog` | Fetch version changelog. |

## Guidance

Third-party clients should prefer stable browsing and playback capabilities, and should not depend on frontend-internal fields. Authentication, media tokens, restore, update, and file-path endpoints are high-risk surfaces; define clear permission boundaries before calling them.
