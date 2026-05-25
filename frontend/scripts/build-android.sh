#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ANDROID_DIR="$SCRIPT_DIR/../android"

if [ -z "${JAVA_HOME:-}" ]; then
  for candidate in \
    /opt/homebrew/opt/openjdk \
    /opt/homebrew/opt/openjdk@25 \
    /opt/homebrew/opt/openjdk@21 \
    /usr/local/opt/openjdk \
    /usr/local/opt/openjdk@25 \
    /usr/local/opt/openjdk@21
  do
    if [ -x "$candidate/bin/java" ]; then
      export JAVA_HOME="$candidate"
      break
    fi
  done
fi

if [ -z "${JAVA_HOME:-}" ]; then
  echo "JAVA_HOME is required. Install JDK 21+ or set JAVA_HOME before building Android." >&2
  exit 1
fi

if [ -z "${ANDROID_HOME:-}" ]; then
  for candidate in \
    "$HOME/Library/Android/sdk" \
    /opt/homebrew/share/android-commandlinetools \
    /usr/local/share/android-commandlinetools
  do
    if [ -d "$candidate/platforms" ] || [ -d "$candidate/cmdline-tools" ]; then
      export ANDROID_HOME="$candidate"
      break
    fi
  done
fi

if [ -z "${ANDROID_HOME:-}" ]; then
  echo "ANDROID_HOME is required. Install Android SDK command line tools first." >&2
  exit 1
fi

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"

if [ ! -f "$ANDROID_DIR/local.properties" ]; then
  printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$ANDROID_DIR/local.properties"
fi

cd "$ANDROID_DIR"
exec ./gradlew assembleDebug
