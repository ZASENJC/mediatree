#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-$(head -n 1 VERSION | tr -d '[:space:]')}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
PORT="${PORT:-80}"
BUILDER="${DOCKER_BUILDX_BUILDER:-${BUILDER:-}}"
METADATA_FILE=".github/release-metadata.json"

if [[ -z "$VERSION" ]]; then
  echo "VERSION is empty. Pass a version or update the VERSION file." >&2
  exit 1
fi

read -r REQUIRES_IMAGE_UPDATE RELEASE_REASON < <(
  VERSION="$VERSION" METADATA_FILE="$METADATA_FILE" python3 - <<'PY'
import json
import os
from pathlib import Path

version = os.environ["VERSION"]
metadata_path = Path(os.environ["METADATA_FILE"])
fallback = {
    "requires_image_update": False,
    "reason": "应用包级更新；不需要完整 Docker 镜像更新。",
}
metadata = {}
if metadata_path.exists():
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
release = metadata.get("versions", {}).get(version, metadata.get("default", fallback))
requires = "true" if release.get("requires_image_update") else "false"
reason = (release.get("reason") or fallback["reason"]).replace("\n", " ")
print(requires, reason)
PY
)

cmd=(docker buildx build)
if [[ -n "$BUILDER" ]]; then
  cmd+=(--builder "$BUILDER")
fi
cmd+=(--platform "$PLATFORMS" --build-arg "PORT=$PORT" --build-arg "MEDIATREE_VERSION=$VERSION")

if [[ "$REQUIRES_IMAGE_UPDATE" == "true" ]]; then
  cmd+=(-t "zasenjc/mediatree:${VERSION}" -t "zasenjc/mediatree:latest")
else
  cmd+=(-t "zasenjc/mediatree:latest")
fi

cmd+=(--push .)

echo "Version: $VERSION"
echo "Release type: $([[ "$REQUIRES_IMAGE_UPDATE" == "true" ]] && echo "full Docker image" || echo "app-package")"
echo "Reason: $RELEASE_REASON"
printf 'Running:'
printf ' %q' "${cmd[@]}"
printf '\n'

"${cmd[@]}"
