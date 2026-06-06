**English** | [简体中文](../wiki_zh-CN/Installation)

# Installation

## Prerequisites

- Docker & Docker Compose installed
- A directory with your media files (videos, subtitles, covers)
- At least 1GB free disk space for database and cover cache

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Required — set your own credentials
AUTH_USER=your_username
AUTH_PASS=your_secure_password

# Media directories (format: /host/path:/container/mount:ro)
MEDIA_VOLUMES=/home/user/media/movies:/media/movies:ro \
             /home/user/media/shows:/media/shows:ro

# Optional — TMDB API for better metadata
TMDB_ACCESS_TOKEN=your_tmdb_read_access_token
```

### 3. Start the Container

```bash
docker compose up -d
```

### 4. Open in Browser

Visit `http://localhost:27580` and follow the setup wizard.

## Docker Hub

You can also pull the pre-built image directly:

```bash
docker pull zasenjc/mediatree:latest
```

See the [docker-compose.example.yml template](https://github.com/ZASENJC/mediatree/blob/main/docker-compose.example.yml) for a complete deployment example. Copy it to `docker-compose.yml` before editing local media paths.

## Volume Mounts

| Mount | Mode | Purpose |
|-------|------|---------|
| `/host/path:/media/name` | `:ro` | Media files (read-only) |
| `./data:/app/data` | `:rw` | Persistent data (database, covers, config, fonts) |

## Supported Platforms

- `linux/amd64` — Intel/AMD x86_64
- `linux/arm64` — Apple Silicon, Raspberry Pi 4/5, ARM servers

## Upgrading

Regular Web updates download the small app package from the GitHub Release and unpack it into `./data/releases`. These updates do not require mounting the Docker socket, and failed app-package updates can be rolled back from the matching version row in Settings.

To let Settings perform a full Docker image update, mount `/var/run/docker.sock:/var/run/docker.sock` so the container can use the host Docker engine to pull the new image and recreate itself. This gives the container Docker control on the host; leave it unmounted in untrusted environments and use the host-side commands below instead.

When a release is marked as requiring a full image update, the Python runtime, system packages, ffmpeg, fonts, or another base image layer changed. In that case, run:

```bash
# Full image upgrade
docker compose pull
docker compose up -d --force-recreate

# Or rebuild from source
docker compose build --no-cache
docker compose up -d
```

## Troubleshooting

### Permission Issues
The container runs as non-root user (uid 1000). Ensure your data directory is writable:
```bash
mkdir -p ./data
sudo chown -R 1000:1000 ./data
chmod 755 ./data
```

### Port Conflict
Change `HOST_PORT` in `.env` if port 27580 is already in use:
```env
HOST_PORT=3000
```

### Subtitle Fonts in Docker
System CJK fonts (Noto CJK, WenQuanYi Micro Hei) are installed automatically. Upload custom fonts via Settings → Subtitle Fonts.
