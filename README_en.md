<p align="center">
  <img src="docs/assets/logo.png" alt="MediaTree" width="112" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <strong>Turn local video folders into a polished private streaming library.</strong><br>
  Supports movies, anime, and JAV.
</p>

<p align="center">
  <strong>English</strong> · <a href="README.md">简体中文</a> · <a href="#quick-deploy">Quick Deploy</a> · <a href="https://github.com/ZASENJC/mediatree/wiki">Wiki</a> · <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0.14-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
  <a href="https://github.com/ZASENJC/mediatree-app"><img src="https://img.shields.io/badge/android-app-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android App"></a>
</p>

MediaTree is built for people who keep movies, TV shows, anime, and private niche libraries on their own disks. Point it at your folders, let it scan and enrich the files, then watch from the browser or Jellyfin-compatible apps without running a heavy media stack.

## Why MediaTree

- **Your files stay where they are** - mount existing folders read-only and keep the original directory structure.
- **Metadata without manual busywork** - scrape posters, titles, cast, seasons, episodes, and details from TMDB, Bangumi, and Javdatabase.
- **A player made for real libraries** - stream directly, seek with HTTP Range, transcode on demand, render ASS/SSA subtitles, show playback state in the browser tab, and open in IINA, mpv, VLC, or PiP.
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

Create `docker-compose.yml`, update the account, password, and media paths in the comments, then start the container:

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    restart: unless-stopped

    ports:
      # Left side is the host port. Open http://localhost:27580 after startup.
      - "27580:80"

    volumes:
      # Persistent data: database, covers, fonts, backups, and app-package updates.
      - ./data:/app/data

      # Mount your media folder as read-only. Change the left side to your real host path.
      - /path/to/your/movies:/media/movies:ro
      # Add more media folders if needed.
      # - /path/to/your/anime:/media/anime:ro

      # Optional: let Settings perform full Docker image updates.
      # This gives the container Docker control on the host; app-package updates do not need it.
      # - /var/run/docker.sock:/var/run/docker.sock

    environment:
      # Preset admin account. You can leave these empty and create the admin account on first launch.
      - AUTH_USER=admin
      - AUTH_PASS=change-me

      # Internal service port. Usually keep this unchanged.
      - PORT=80

      # Scan libraries when the container starts.
      - SCAN_ON_STARTUP=true

      # Enable or disable Javdatabase scraping.
      - JAVDB_ENABLED=true

    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:80/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

Start:

```bash
docker compose up -d
```

Open `http://localhost:27580`, sign in, scan your library, and start watching. If `AUTH_USER` / `AUTH_PASS` are not preset, the first launch asks you to create an admin account.

You can also clone the repo and use the example config:

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml

# Edit .env and docker-compose.yml, then start.
docker compose up -d
```

Docker Hub image: `zasenjc/mediatree:latest`

## Configuration You Usually Need

| Variable | What it does |
|---|---|
| `AUTH_USER` / `AUTH_PASS` | Presets the admin login; leave empty to create it on first launch |
| `MEDIA_VOLUMES` | Mounts your media folders, for example `/host/movies:/media/movies:ro` |
| `DATA_DIR` | Stores database, covers, fonts, backups, and app-package updates. Default: `./data` |
| `HOST_PORT` | Web port on the host. Default: `27580` |
| `TMDB_API_KEY` / `TMDB_ACCESS_TOKEN` | Optional, improves TMDB scraping |
| `JAVDB_ENABLED` | Enables or disables Javdatabase scraping |

Scraper cache TTLs and the Javdatabase request interval are managed internally instead of being tuned from Settings or environment variables. Manual scans, rescrapes, and manual apply actions bypass cache, and empty results are not cached, so stale empty responses do not block later metadata fixes.

See [.env.example](.env.example) for all options. Detailed setup, scraper behavior, client compatibility, and troubleshooting live in the [Wiki](https://github.com/ZASENJC/mediatree/wiki).

## Updates

Most updates can be installed directly from Settings. MediaTree downloads a small app package into `./data`, so you usually do not need to pull a new Docker image. After an app-package update restarts successfully, MediaTree keeps the current package and one rollback package, then removes older packages. New installs that use `zasenjc/mediatree:latest` also start from the newest version.

For app-package releases, maintainers now build and push `zasenjc/mediatree:latest` locally instead of syncing DockerHub through GitHub Actions. Existing installs keep using the Settings app-package path, while new installs still start from the latest application baseline.

Some releases show "full image update required". That usually means the runtime changed too, such as Python, ffmpeg, fonts, or startup behavior. The simplest path is to run the two host-side commands below. If you want Settings to perform full image updates automatically, mount `/var/run/docker.sock:/var/run/docker.sock` in `docker-compose.yml`; this gives the container control over Docker on the host, so leave it unmounted if you are unsure.

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

## Community / Channels

- Telegram group: [Join the discussion](https://t.me/mediatree_group)
- Telegram update channel: [Subscribe to updates](https://t.me/mediatreex)

## License

MIT © [ZASENJC](https://github.com/ZASENJC)
