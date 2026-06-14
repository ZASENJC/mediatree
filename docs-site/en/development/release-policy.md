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

App packages must be built with `scripts/build-app-package.sh`. Do not duplicate packaging logic in GitHub Actions or local release commands; the shared builder strips bytecode, `__pycache__`, source maps, and local metadata, then creates the archive with stable compression settings.

## Full Docker Image Updates

Use a full image update for:

- Dockerfile, system package, Python version, or dependency layer changes.
- ffmpeg, font, or runtime binary changes.
- Container user, permission, entrypoint, or bootstrap behavior changes.
- Any change that cannot be safely delivered by replacing only the app package.

Full image updates should publish both the version tag and `latest`.

Docker builds stay slim by default: do not include full `fonts-noto-cjk` or `fonts-noto-color-emoji` packages, and rely on `fonts-wqy-microhei` plus the bundled frontend subtitle fallback font. Set `INCLUDE_FULL_CJK_FONTS=true` or `INCLUDE_EMOJI_FONT=true` only when the release explicitly needs full Noto CJK or emoji fonts. Enabling those args or changing Dockerfile/runtime font policy requires a full Docker image update.

## Docs Site Deployment

The docs site is deployed by `.github/workflows/docs-pages.yml` to GitHub Pages. It only builds `docs-site`; it does not create GitHub Releases, update DockerHub, or change app-package versions.

## Pre-release Checks

Before publishing, verify:

- Backend tests pass.
- Backend compiles.
- Frontend builds.
- Docs and README match current behavior.
- App packages are produced by `scripts/build-app-package.sh`, and Docker images are built by `scripts/push-docker-release.sh` with slim default args unless the release explicitly needs full fonts.
- `git diff` only contains intended changes.
