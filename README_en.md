<p align="center">
  <img src="docs/assets/logo.png" alt="MediaTree" width="112" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <strong>Turn local video folders into a polished private streaming library.</strong>
</p>

<p align="center">
  <strong>English</strong> · <a href="README.md">简体中文</a> · <a href="#quick-deploy">Quick Deploy</a> · <a href="https://github.com/ZASENJC/mediatree/wiki">Wiki</a> · <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0.07-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
</p>

MediaTree is built for people who keep movies, TV shows, anime, and private niche libraries on their own disks. Point it at your folders, let it scan and enrich the files, then watch from the browser or Jellyfin-compatible apps without running a heavy media stack.

## Why MediaTree

- **Your files stay where they are** - mount existing folders read-only and keep the original directory structure.
- **Metadata without manual busywork** - scrape posters, titles, cast, seasons, episodes, and details from TMDB, Bangumi, and Javdatabase.
- **A player made for real libraries** - stream directly, seek with HTTP Range, transcode on demand, render ASS/SSA subtitles, and open in IINA, mpv, VLC, or PiP.
- **Useful from day one** - browse by library, folder tree, favorites, categories, or seasons; scan on startup or let the file watcher pick up changes.
- **Works with more than the web UI** - Jellyfin-compatible APIs let VidHub, Infuse, Kodi, VLC, IINA, and mpv connect directly.
- **Simple to run at home** - Docker Compose, SQLite, persistent `./data`, linux/amd64 and linux/arm64 images.

For a mobile experience, pair it with the standalone Android client [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app). It supports MediaTree, Jellyfin, Emby, SMB, and WebDAV while this project remains the separately deployable server.

## Screenshots

| Library | Player |
|---|---|
| ![Home](https://img.qunq.de/file/1779640696711_home_no_text.png) | ![Player](https://img.qunq.de/file/1779640693184_movie.png) |
| Poster grid for scanned libraries | Streaming with rich details and subtitles |

| Browse | Settings |
|---|---|
| ![Browse](https://img.qunq.de/file/1779640700855_browser.png) | ![Settings](https://img.qunq.de/file/1779640699625_settings.png) |
| Folder tree and season navigation | Library, scraper, backup, and update controls |

## Quick Deploy

Clone the repo, copy the example config, mount at least one media folder, and start the container:

```bash
git clone https://github.com/ZASENJC/mediatree.git && cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml

# Edit .env first:
# AUTH_USER=admin
# AUTH_PASS=change-me
# MEDIA_VOLUMES=/path/to/movies:/media/movies:ro

docker compose up -d
```

Open `http://localhost:27580`, sign in, scan your library, and start watching.

Docker Hub image: `zasenjc/mediatree:latest`

## Configuration You Usually Need

| Variable | What it does |
|---|---|
| `AUTH_USER` / `AUTH_PASS` | Enables the admin login |
| `MEDIA_VOLUMES` | Mounts your media folders, for example `/host/movies:/media/movies:ro` |
| `DATA_DIR` | Stores database, covers, fonts, backups, and app-package updates. Default: `./data` |
| `HOST_PORT` | Web port on the host. Default: `27580` |
| `TMDB_API_KEY` / `TMDB_ACCESS_TOKEN` | Optional, improves TMDB scraping |
| `JAVDB_ENABLED` | Enables or disables Javdatabase scraping |

See [.env.example](.env.example) for all options. Detailed setup, scraper behavior, client compatibility, and troubleshooting live in the [Wiki](https://github.com/ZASENJC/mediatree/wiki).

## Updates

Routine updates can be installed from Settings as small app packages in `./data`. A full Docker image update is only needed when the runtime layer changes, such as Python, system packages, ffmpeg, fonts, or startup behavior.

For full image updates:

```bash
docker compose pull
docker compose up -d
```

## Documentation

| Document | Description |
|---|---|
| [Wiki](https://github.com/ZASENJC/mediatree/wiki) | Full user guides, advanced config, scraper notes, and troubleshooting |
| [README.md](README.md) | 简体中文 README |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |
| [CLAUDE.md](CLAUDE.md) | Development and AI-assisted maintenance notes |

## License

MIT © [ZASENJC](https://github.com/ZASENJC)
