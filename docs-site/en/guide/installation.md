# Installation

## Prerequisites

- Docker and Docker Compose.
- A folder containing videos, subtitles, or covers.
- At least 1 GB of free disk space for the database, cover cache, fonts, and app-package updates.

## Quick Start

### 1. Prepare Config

Use the published image directly, or clone the repo and copy the example files:

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
```

Edit `.env` and `docker-compose.yml`. At minimum, set the admin account, data directory, and media mounts.

### 2. Minimal docker-compose.yml

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    restart: unless-stopped
    ports:
      - "27580:80"
    volumes:
      - ./data:/app/data
      - /path/to/your/movies:/media/movies:ro
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=change-me
      - PORT=80
      - SCAN_ON_STARTUP=true
      - JAVDB_ENABLED=true
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:80/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

Mount media folders read-only, for example `/host/movies:/media/movies:ro`. MediaTree stores its database, covers, config, fonts, backups, and app-package updates in `./data`.

### 3. Start

```bash
docker compose up -d
```

Open `http://localhost:27580`. If `AUTH_USER` / `AUTH_PASS` are not preset, the first launch asks you to create an admin account.

## Supported Platforms

- `linux/amd64`
- `linux/arm64`

## Common Startup Issues

### Data Directory Permissions

The container runs as a non-root user. If `./data` is not writable, adjust it on the host:

```bash
mkdir -p ./data
sudo chown -R 1000:1000 ./data
chmod 755 ./data
```

### Port Conflict

If `27580` is already in use, change the left side of the port mapping:

```yaml
ports:
  - "3000:80"
```

Then open `http://localhost:3000`.

### Subtitle Fonts

The default Docker image includes WenQuanYi Micro Hei and ships a Source Han Sans frontend fallback font to keep the image smaller. Use `INCLUDE_FULL_CJK_FONTS=true` or `INCLUDE_EMOJI_FONT=true` for custom builds that need full Noto CJK or emoji fonts, or upload subtitle fonts from Settings.
