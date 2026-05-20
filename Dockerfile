FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install 2>/dev/null || npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-wqy-microhei \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /build/dist /app/frontend/dist

RUN mkdir -p /app/data

ENV MEDIA_ROOT=/media
ENV DATA_DIR=/app/data
ENV JAVDB_ENABLED=true
ENV JAVDB_CACHE_HOURS=24
ENV JAVDB_REQUEST_INTERVAL=5
ENV SCAN_ON_STARTUP=true

EXPOSE 80

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "27580"]
