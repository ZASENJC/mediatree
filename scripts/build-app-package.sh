#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-$(head -n 1 VERSION | tr -d '[:space:]')}"
WORK_DIR="${APP_PACKAGE_WORK_DIR:-/tmp}"
PKG_DIR="$WORK_DIR/mediatree-app-$VERSION"
ARCHIVE="$WORK_DIR/mediatree-app-$VERSION.tar.gz"
MANIFEST="$WORK_DIR/mediatree-app-$VERSION.manifest.json"
SHA_FILE="$WORK_DIR/mediatree-app-$VERSION.sha256"
RELEASE_REQUIRES_IMAGE_UPDATE="${RELEASE_REQUIRES_IMAGE_UPDATE:-false}"
RELEASE_REQUIRES_WINDOWS_BASE_UPDATE="${RELEASE_REQUIRES_WINDOWS_BASE_UPDATE:-false}"
RELEASE_UPDATE_REASON="${RELEASE_UPDATE_REASON:-应用包级更新；不需要完整 Docker 镜像更新。}"
RELEASE_WINDOWS_UPDATE_REASON="${RELEASE_WINDOWS_UPDATE_REASON:-应用包级更新；不需要更新 Windows 桌面版基础运行时。}"

if [[ -z "$VERSION" ]]; then
  echo "VERSION is empty. Pass a version or update the VERSION file." >&2
  exit 1
fi

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

stat_size() {
  stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

write_manifest() {
  local target="$1"
  local sha="$2"
  local size="$3"
  VERSION="$VERSION" \
  RELEASE_REQUIRES_IMAGE_UPDATE="$RELEASE_REQUIRES_IMAGE_UPDATE" \
  RELEASE_REQUIRES_WINDOWS_BASE_UPDATE="$RELEASE_REQUIRES_WINDOWS_BASE_UPDATE" \
  RELEASE_UPDATE_REASON="$RELEASE_UPDATE_REASON" \
  RELEASE_WINDOWS_UPDATE_REASON="$RELEASE_WINDOWS_UPDATE_REASON" \
  ARCHIVE_NAME="mediatree-app-$VERSION.tar.gz" \
  SHA="$sha" \
  SIZE="$size" \
  python3 - <<'PY' > "$target"
import json
import os

manifest = {
    "version": os.environ["VERSION"],
    "base_api": 1,
    "requires_image_update": os.environ["RELEASE_REQUIRES_IMAGE_UPDATE"].lower() == "true",
    "requires_windows_base_update": os.environ["RELEASE_REQUIRES_WINDOWS_BASE_UPDATE"].lower() == "true",
    "reason": os.environ["RELEASE_UPDATE_REASON"],
    "windows_reason": os.environ["RELEASE_WINDOWS_UPDATE_REASON"],
    "archive": os.environ["ARCHIVE_NAME"],
    "sha256": os.environ["SHA"],
    "size": int(os.environ["SIZE"]),
    "notes": "",
}
print(json.dumps(manifest, ensure_ascii=False, indent=2))
PY
}

rm -rf "$PKG_DIR" "$ARCHIVE" "$MANIFEST" "$SHA_FILE"
mkdir -p "$PKG_DIR/frontend"
cp -R backend/app "$PKG_DIR/app"
cp backend/requirements.txt "$PKG_DIR/requirements.txt"
cp backend/constraints.txt "$PKG_DIR/constraints.txt"
cp -R frontend/dist "$PKG_DIR/frontend/dist"
cp VERSION "$PKG_DIR/VERSION"

find "$PKG_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$PKG_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.map" -o -name ".DS_Store" \) -exec rm -f {} +

write_manifest "$PKG_DIR/manifest.json" "" 0

PKG_DIR="$PKG_DIR" ARCHIVE="$ARCHIVE" python3 - <<'PY'
import gzip
import tarfile
from pathlib import Path
import os

pkg_dir = Path(os.environ["PKG_DIR"]).resolve()
archive = Path(os.environ["ARCHIVE"]).resolve()

with archive.open("wb") as raw:
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in sorted(pkg_dir.rglob("*"), key=lambda item: item.relative_to(pkg_dir).as_posix()):
                arcname = path.relative_to(pkg_dir).as_posix()
                info = tar.gettarinfo(str(path), arcname)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                if path.is_file() and not path.is_symlink():
                    with path.open("rb") as source:
                        tar.addfile(info, source)
                else:
                    tar.addfile(info)
PY

SHA="$(sha256_file "$ARCHIVE")"
SIZE="$(stat_size "$ARCHIVE")"
printf '%s  mediatree-app-%s.tar.gz\n' "$SHA" "$VERSION" > "$SHA_FILE"
write_manifest "$MANIFEST" "$SHA" "$SIZE"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "archive=$ARCHIVE" >> "$GITHUB_OUTPUT"
  echo "manifest=$MANIFEST" >> "$GITHUB_OUTPUT"
  echo "sha_file=$SHA_FILE" >> "$GITHUB_OUTPUT"
else
  echo "Archive: $ARCHIVE"
  echo "Manifest: $MANIFEST"
  echo "SHA256: $SHA"
  echo "Size: $SIZE"
fi
