#!/usr/bin/env bash
set -euo pipefail

if [ -z "${TG_BOT_TOKEN:-}" ] || [ -z "${TG_CHAT_ID:-}" ]; then
  echo "TG_BOT_TOKEN or TG_CHAT_ID is missing; skip Telegram release notification."
  exit 0
fi

required_vars=(
  VERSION
  GITHUB_REPOSITORY
)

for var_name in "${required_vars[@]}"; do
  if [ -z "${!var_name:-}" ]; then
    echo "$var_name is required for Telegram release notifications." >&2
    exit 1
  fi
done

api_url="https://api.telegram.org/bot${TG_BOT_TOKEN}"
github_server_url="${GITHUB_SERVER_URL:-https://github.com}"
release_url="${github_server_url}/${GITHUB_REPOSITORY}/releases/tag/${VERSION}"
update_reason="${RELEASE_UPDATE_REASON:-应用包级更新；不需要完整 Docker 镜像更新。}"

if [ "${RELEASE_REQUIRES_IMAGE_UPDATE:-false}" = "true" ]; then
  update_type="完整 Docker 镜像更新"
  upgrade_hint="更新方式: docker compose pull && docker compose up -d"
else
  update_type="Web 应用包更新"
  upgrade_hint="更新方式: 设置页下载并更新；新安装用户使用 DockerHub latest。"
fi

message="$(cat <<EOF
MediaTree Web ${VERSION}
${update_type}已发布。

说明: ${update_reason}
${upgrade_hint}
Release: ${release_url}
EOF
)"

curl --fail --silent --show-error --retry 3 --retry-delay 2 \
  --request POST "$api_url/sendMessage" \
  --data-urlencode "chat_id=$TG_CHAT_ID" \
  --data-urlencode "text=$message" \
  --data-urlencode "disable_web_page_preview=true" \
  >/dev/null
