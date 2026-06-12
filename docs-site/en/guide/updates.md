# Updates and Rollback

MediaTree has two update paths: app-package updates and full Docker image updates. They share one version baseline but apply to different change types.

## App-package Updates

Most feature updates are app-package updates. Settings downloads `mediatree-app-<version>.tar.gz` from GitHub Release, unpacks it into `./data/releases`, and activates it after restart.

App-package updates:

- Do not require the Docker socket.
- Live in the data volume.
- Keep the current package and one rollback package after a successful restart.
- Can be rolled back from Settings.

## Full Image Updates

A full Docker image update is required when the runtime changes, such as:

- Dockerfile, system packages, Python version, or dependency layer changes.
- ffmpeg, fonts, or runtime binary changes.
- Container user, permissions, entrypoint, or bootstrap behavior changes.
- Any change that cannot be safely delivered by replacing only the app package.

Run on the host:

```bash
docker compose pull
docker compose up -d
```

To let Settings perform full image updates, mount the Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

This gives the container Docker control on the host. Leave it unmounted if you are unsure.

## New Installs

When maintainers publish an app-package update, they also refresh `zasenjc/mediatree:latest` locally. New installs using `latest` therefore start from the newest application baseline.

## Rollback

App-package updates can roll back to the previous app package or the built-in image version. Full image rollback must be managed from the host with Docker or image tags.
