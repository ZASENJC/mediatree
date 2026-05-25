#!/bin/sh
set -u

BASE_DIR="${MEDIATREE_BASE_DIR:-/opt/mediatree/base}"
DATA_DIR="${DATA_DIR:-/app/data}"
RELEASES_DIR="$DATA_DIR/releases"
PORT="${PORT:-80}"
ORIGINAL_PYTHONPATH="${PYTHONPATH:-}"

mkdir -p "$RELEASES_DIR"

read_pointer() {
  pointer="$RELEASES_DIR/$1"
  if [ -f "$pointer" ]; then
    head -n 1 "$pointer" | tr -d '[:space:]'
  fi
}

valid_app_dir() {
  dir="$1"
  [ -f "$dir/app/main.py" ] && [ -f "$dir/frontend/dist/index.html" ] && [ -f "$dir/VERSION" ]
}

choose_app_dir() {
  current="$(read_pointer current)"
  if [ -n "$current" ] && valid_app_dir "$RELEASES_DIR/$current"; then
    printf '%s|app-package\n' "$RELEASES_DIR/$current"
    return
  fi

  previous="$(read_pointer previous)"
  if [ -n "$previous" ] && valid_app_dir "$RELEASES_DIR/$previous"; then
    printf '%s\n' "$previous" > "$RELEASES_DIR/current"
    printf '%s|app-package\n' "$RELEASES_DIR/$previous"
    return
  fi

  printf '%s|base\n' "$BASE_DIR"
}

child_pid=""

terminate() {
  if [ -n "$child_pid" ]; then
    kill "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 143
}

trap terminate TERM INT

while :; do
  choice="$(choose_app_dir)"
  APP_DIR="${choice%|*}"
  APP_SOURCE="${choice#*|}"

  if ! valid_app_dir "$APP_DIR"; then
    echo "Selected MediaTree app directory is invalid: $APP_DIR"
    exit 1
  fi

  export MEDIATREE_APP_DIR="$APP_DIR"
  export MEDIATREE_APP_SOURCE="$APP_SOURCE"
  if [ -n "$ORIGINAL_PYTHONPATH" ]; then
    export PYTHONPATH="$APP_DIR:$ORIGINAL_PYTHONPATH"
  else
    export PYTHONPATH="$APP_DIR"
  fi

  cd "$APP_DIR"
  version="$(head -n 1 "$APP_DIR/VERSION" | tr -d '[:space:]')"
  echo "Starting MediaTree $version from $APP_SOURCE ($APP_DIR)"

  python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
  child_pid="$!"
  wait "$child_pid"
  code="$?"
  child_pid=""

  if [ "$code" -eq 0 ]; then
    sleep 1
    continue
  fi

  if [ "$APP_SOURCE" = "app-package" ]; then
    echo "MediaTree app package exited with code $code; attempting fallback."
    current="$(read_pointer current)"
    previous="$(read_pointer previous)"
    if [ -n "$previous" ] && [ "$previous" != "$current" ] && valid_app_dir "$RELEASES_DIR/$previous"; then
      printf '%s\n' "$previous" > "$RELEASES_DIR/current"
      continue
    fi
    rm -f "$RELEASES_DIR/current"
    continue
  fi

  exit "$code"
done
