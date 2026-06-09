FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /opt/mediatree/base

ARG MEDIATREE_VERSION=unknown
LABEL org.opencontainers.image.title="MediaTree" \
      org.opencontainers.image.source="https://github.com/ZASENJC/mediatree" \
      org.opencontainers.image.version=$MEDIATREE_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-wqy-microhei \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

ARG INCLUDE_DOCKER_CLI=false
RUN if [ "$INCLUDE_DOCKER_CLI" = "true" ]; then \
      install -m 0755 -d /etc/apt/keyrings && \
      curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
      chmod a+r /etc/apt/keyrings/docker.asc && \
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
      apt-get update && \
      apt-get install -y --no-install-recommends docker-ce-cli && \
      rm -rf /var/lib/apt/lists/*; \
    fi

COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY backend/ ./
COPY --from=frontend-build /build/dist /opt/mediatree/base/frontend/dist

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin mediatree \
    && mkdir -p /app/data \
    && chown -R mediatree:mediatree /app/data /opt/mediatree

COPY VERSION /opt/mediatree/base/VERSION
COPY docker/entrypoint.sh /usr/local/bin/mediatree-entrypoint
RUN chmod +x /usr/local/bin/mediatree-entrypoint

ENV MEDIA_ROOT=/media
ENV DATA_DIR=/app/data
ENV MEDIATREE_BASE_DIR=/opt/mediatree/base
ENV JAVDB_ENABLED=true
ENV JAVDB_CACHE_HOURS=24
ENV JAVDB_REQUEST_INTERVAL=5
ENV SCAN_ON_STARTUP=true

ARG PORT=80
ENV PORT=$PORT

EXPOSE $PORT

USER mediatree

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["/usr/local/bin/mediatree-entrypoint"]
