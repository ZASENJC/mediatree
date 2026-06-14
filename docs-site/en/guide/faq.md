# FAQ

## Why are posters missing after scanning?

Check that the library uses the right scraper and that `TMDB_ACCESS_TOKEN` works. Without TMDB credentials, MediaTree can still scan and play files, but movie and TV metadata will be limited.

## Why is Javdatabase not in auto scraping?

Javdatabase is code-based and behaves differently from ordinary movie and TV matching. To avoid noisy results in normal libraries, select it explicitly for the relevant library.

## What is the `sp` folder?

An `sp` folder inside a movie directory is treated as specials or extras. MediaTree keeps those files out of normal listings, continue watching, and main episode queues unless you are working in a specials-specific view.

## Why do some versions require a full image update?

That means the runtime layer changed, such as Python, ffmpeg, fonts, or startup behavior. Replace the image from the host with `docker compose pull && docker compose up -d`.

## Do I need to mount the Docker socket?

No. Regular app-package updates do not need it. Only mount `/var/run/docker.sock` if you want Settings to perform full image updates, and only if you accept the host Docker control boundary.

## Can I disable authentication?

MediaTree supports first-run admin setup and environment-provided credentials. For real deployments, especially outside your LAN, enable authentication, use a strong password, and prefer HTTPS behind a reverse proxy.
