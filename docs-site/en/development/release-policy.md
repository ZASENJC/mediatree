# Release Policy

MediaTree distinguishes ordinary commits, app-package updates, and full Docker image updates.

## Ordinary Commits

Ordinary pushes must not publish releases. The current release workflow is manual-only with `workflow_dispatch`, so normal commits do not mutate tags, GitHub Releases, or DockerHub.

## App-package Updates

Use app-package updates when a change is limited to app code, built frontend assets, documentation, or behavior that does not require changing the base runtime layer.

An app-package release produces:

- `mediatree-app-<version>.tar.gz`
- `mediatree-app-<version>.manifest.json`
- `mediatree-app-<version>.sha256`

Maintainers also refresh DockerHub `zasenjc/mediatree:latest` locally so new installs start from the newest application baseline.

## Full Docker Image Updates

Use a full image update for:

- Dockerfile, system package, Python version, or dependency layer changes.
- ffmpeg, font, or runtime binary changes.
- Container user, permission, entrypoint, or bootstrap behavior changes.
- Any change that cannot be safely delivered by replacing only the app package.

Full image updates should publish both the version tag and `latest`.

## Docs Site Deployment

The docs site is deployed by `.github/workflows/docs-pages.yml` to GitHub Pages. It only builds `docs-site`; it does not create GitHub Releases, update DockerHub, or change app-package versions.

## Pre-release Checks

Before publishing, verify:

- Backend tests pass.
- Backend compiles.
- Frontend builds.
- Docs and README match current behavior.
- `git diff` only contains intended changes.
