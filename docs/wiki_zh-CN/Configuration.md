[English](../wiki/Configuration) | **简体中文**

# 配置说明

MediaTree 通过环境变量（`.env` 文件）和运行时设置（设置页面）进行配置。

## 环境变量

### 认证设置

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `AUTH_USER` | `""` | 管理员用户名。留空则禁用认证 |
| `AUTH_PASS` | `""` | 管理员密码。如启用认证请使用强密码 |

### 媒体和数据

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `MEDIA_ROOT` | `/media` | 包含媒体库的根目录 |
| `DATA_DIR` | `../data` | 持久化数据目录（数据库、封面、配置、字体、日志）|
| `SCAN_ON_STARTUP` | `true` | 容器启动时执行全量扫描 |
| `FILE_WATCHER_ENABLED` | `true` | 启用文件系统监控自动扫描 |

### 刮削器配置

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `TMDB_API_KEY` | `""` | TMDB v3 API 密钥 |
| `TMDB_ACCESS_TOKEN` | `""` | TMDB v4 读取访问令牌（推荐）|
| `TMDB_CACHE_HOURS` | `168` | TMDB 缓存有效期（小时，1 周）|
| `BANGUMI_CACHE_HOURS` | `168` | Bangumi 缓存有效期（小时）|
| `JAVDB_ENABLED` | `true` | 启用 JavDatabase 刮削器 |
| `JAVDB_CACHE_HOURS` | `24` | JavDB 缓存有效期（小时）|
| `JAVDB_REQUEST_INTERVAL` | `1.0` | JavDB 请求最小间隔（秒）|

### 并行度设置

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `SCRAPE_CONCURRENCY_PER_LIBRARY` | `8` | 每个库最大并发刮削数 |
| `SCRAPE_GLOBAL_CONCURRENCY` | `16` | 全局最大并发刮削数 |
| `SCRAPER_API_CONCURRENCY` | `8` | 最大并发 API 请求数 |
| `SCRAPER_HTTP_TIMEOUT` | `10.0` | HTTP 请求超时（秒）|

### 服务器

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `PORT` | `80` | 容器内服务器监听端口 |

## docker-compose.yml

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    ports:
      - "${HOST_PORT:-27580}:27580"
    volumes:
      - ${MEDIA_VOLUMES}
      - ${DATA_DIR:-./data}:/app/data
    env_file:
      - .env
    environment:
      - PORT=${HOST_PORT:-27580}
    restart: unless-stopped
```

## 运行时设置（通过设置页面）

以下设置在 Web 界面中管理，并持久化到 `data/config.json`：

- **库配置** — 刮削器选择、TMDB 密钥、库密码
- **JavDB 设置** — 启用/禁用、缓存时长、请求间隔
- **界面偏好** — 隐藏首页标题文字、环境光模式、显示源文件名

## 配置优先级

1. 环境变量（`.env`）
2. 运行时设置（`data/config.json`）
3. 默认值（`config.py`）

**重要优先级规则**：敏感值（如 `AUTH_PASS`）仅从环境变量读取，不会持久化到 `config.json`。

## 获取 TMDB API 密钥

1. 注册 [TMDB 账号](https://www.themoviedb.org/signup)
2. 前往 [API 设置](https://www.themoviedb.org/settings/api)
3. 生成「读取访问令牌」（推荐使用 v4 认证方式）
4. 在 `.env` 文件中设置 `TMDB_ACCESS_TOKEN`

> ℹ️ TMDB API 非商业用途免费。没有它，MediaTree 仍可使用基于文件名的组织方式，但缺少丰富的元数据。
