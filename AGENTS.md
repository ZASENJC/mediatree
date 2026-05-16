# AGENTS.md — MediaTree 项目开发指南

## 项目概述

基于 Docker 的本地影片 Web 浏览管理器。支持多媒体库、插件化刮削（TMDB/Bangumi/Javdatabase）、字幕、本地播放器调用、进度记忆。

**页面路由：**
- 引导页（SetupWizard）：首次部署弹出，逐库配置刮削源和密码
- 首页 (`/`)：文件夹卡片网格 + 最近观看 tab，右键菜单（重新/手动刮削、换封面/背景、编辑、删除）
- Folder 页 (`/folder?path=...`)：影片封面网格 + 季度选项卡 + hero 背景 + 右键菜单
- 浏览页 (`/browse`)：左侧树形筛选 + 右侧纵向影片网格 + 分页
- 详情页 (`/detail/:id`)：视频播放器 + 元数据面板 + 灯箱
- 收藏页 (`/favorites`)：收藏影片网格
- 设置页 (`/settings`)：全局配置 + 媒体库管理 + 备份恢复 + 插件/账号
- 登录页 (`/login`)

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn | 端口 27580 |
| 前端 | React 18 + TypeScript 5 + TailwindCSS 3 | Vite 构建 |
| 数据库 | SQLite (aiosqlite) | WAL + busy_timeout 5s |
| 刮削 | TMDB / Bangumi / Javdatabase | 插件化，Fallback 互备 |
| 字幕 | ffprobe/ffmpeg | 内嵌+外挂 → WebVTT |
| 封面 | Pillow resize → JPEG q=80 | data/covers/ + data/stills/ |
| 日志 | RotatingFileHandler | data/logs/mediatree.log (2MB×3) |
| 文件监控 | watchfiles | 自动增量扫描 |
| 容器 | Docker multi-stage | amd64/arm64 |

## 目录结构

```
mediatree/
├── docker-compose.yml / Dockerfile
├── backend/app/
│   ├── main.py              # 入口、路由、中间件、lifespan、备份恢复
│   ├── config.py            # pydantic-settings + 日志系统
│   ├── database.py          # SQLite CRUD + 文件夹树 + 封面路径
│   ├── scanner.py           # 扫描、刮削分发、fallback链、进度、封面缓存、文件夹操作
│   ├── watcher.py           # 文件监控自动扫描 (watchfiles)
│   ├── tmdb.py / bangumi.py / javdb.py
│   ├── covers.py / subtitles.py / stream.py / models.py
│   └── plugins/             # 插件系统
└── frontend/src/
    ├── api.ts               # API 封装
    ├── pages/ (Home, Folder, Browse, Detail, Favorites, Settings, Login, SetupWizard)
    └── components/ (MovieCard, ContextMenu, EditModal, SortDropdown, VideoPlayer, ...)
```

## 核心数据流

### 刮削器 Fallback 链
```
"javdatabase" → [javdatabase]          (独立)
"tmdb"        → [tmdb, bangumi]        (TMDB优先)
"bangumi"     → [bangumi, tmdb]        (Bangumi优先)
"none"        → 跳过
```

### 扫描 + 刮削
```
os.walk → JAV番号提取/目录标识 → NFO解析 → 本地封面递归查找
  → upsert movies → scrape_for_library()
  → fallback链 → title_matches 验证 → 封面缓存 → TV集匹配
```

### 封面路径
```
cover_local (cache key)  → /api/cached-cover/{key}
cover_remote (远程URL)   → 直接用作 <img src>
fanart_local              → Folder 页 hero 背景
```

### 文件监控自动扫描 (watcher.py)
```
watchfiles.awatch(media_roots, debounce=15s)
  → 检测文件变更 → scan_media(root) → upsert → cleanup_deleted → scrape
```

## API 路由

| 路由 | 方法 | 说明 |
|---|---|---|
| `/api/auth/login` | POST | 登录 |
| `/api/auth/status` | GET | 认证状态 |
| `/api/auth/change-password` | POST | 修改用户名/密码 |
| `/api/setup/status` | GET | 首次引导检测 |
| `/api/setup/save` | POST | 批量保存库配置 |
| `/api/health` | GET | 健康检查 |
| `/api/scan` | GET | 手动扫描+刮削 (?media_root=xxx) |
| `/api/scan/status` | GET | 扫描进度 (?media_root=xxx) |
| `/api/scan/log` | GET | 刮削日志 |
| `/api/library/clear` | POST | 清除库刮削数据 |
| `/api/folders` | GET | 文件夹树 (?media_root=xxx) |
| `/api/search` | GET | 搜索 (q/code/title/actress) |
| `/api/movies` | GET | 影片列表(分页/排序/筛选) |
| `/api/recent-watched` | GET | 最近观看 |
| `/api/favorites` | GET | 收藏列表 |
| `/api/detail/:id` | GET | 影片详情 |
| `/api/stream/:id` | GET | 视频流(Range) |
| `/api/cover/:id` | GET | 封面 |
| `/api/cached-cover/:key` | GET | 压缩封面缓存 |
| `/api/episode-still/:id` | GET | 集剧照 |
| `/api/thumbnail/:id/:n` | GET | 缩略图 |
| `/api/subtitle-tracks/:id` | GET | 字幕轨列表 |
| `/api/subtitle/:id/:n` | GET | WebVTT 字幕 |
| `/api/config` | GET/POST | 全局配置 |
| `/api/library-settings` | GET/POST | 每库刮削配置 |
| `/api/media-roots` | GET | 媒体库列表 |
| `/api/library-passwords` | GET/POST | 库密码 |
| `/api/library-verify` | POST | 验证库密码 |
| `/api/categories` | CRUD | 分类 |
| `/api/movies/:id/tags` | POST/DELETE | 标签 |
| `/api/movies/:id` | DELETE/PUT | 删除/编辑影片 |
| `/api/movies/:id/rescrape` | POST | 重新刮削单部 |
| `/api/movies/:id/manual-scrape` | POST | 手动刮削单部 |
| `/api/movies/:id/alternative-covers` | GET | 备选封面 |
| `/api/movies/:id/cover` | POST | 更换封面(URL/上传) |
| `/api/media/:path` | GET | 静态媒体文件 |
| `/api/backup` | GET | 备份下载 |
| `/api/restore` | POST | 恢复(JSON) |
| `/api/restore/upload` | POST | 上传恢复 |
| `/api/plugins/*` | GET/POST/DELETE | 插件管理 |
| `/api/rescrape-folder` | POST | 文件夹重新刮削 |
| `/api/rescrape-folder-manual` | POST | 文件夹手动刮削 |
| `/api/apply-folder-scrape` | POST | 文件夹直接应用刮削结果 |
| `/api/search-scrape` | POST | 搜索刮削候选 |
| `/api/search-backdrops` | POST | 批量获取背景图 |
| `/api/folder/cover` | POST | 更换文件夹封面 |
| `/api/folder/backdrop` | POST | 更换文件夹背景 |
| `/api/folder/edit` | PUT | 编辑文件夹元数据 |
| `/api/folder/delete` | POST | 删除文件夹 |

### AuthMiddleware 白名单
```
/assets, /api/auth/login, /api/auth/status, /api/setup/status, /api/health,
/api/stream/, /api/cover/, /api/cached-cover/, /api/episode-still/,
/api/thumbnail/, /api/subtitle/, /api/media/
```

## 数据库表

| 表 | 关键字段 |
|---|---|
| movies | path, code, title, cover_local, cover_remote, fanart_local, tmdb_id, tmdb_type, tmdb_season, tmdb_episode, episode_*, cast, crew, javdb_*, folder_levels, media_root |
| javdb_cache | code, data, fetched_at |
| scraper_cache | source, query, data, fetched_at |
| library_settings | media_root, scraper, tmdb_key, password_hash, enabled |
| tags | movie_id, tag, created_at |
| categories | name, movie_ids |
| config | key, value |

## 环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| MEDIA_ROOT | /media | 媒体根目录 |
| SCAN_ON_STARTUP | true | 启动时扫描 |
| AUTH_USER | — | 登录账号 |
| AUTH_PASS | — | 登录密码 |

## 常见修改指引

| 需求 | 文件 |
|---|---|
| 改样式 | `pages/*.tsx` + `index.css` |
| 加 API | `main.py` + `database.py` + `api.ts` |
| 加刮削器 | 新建 `xxx.py` + `scanner.py` FALLBACK_HANDLERS |
| 改扫描 | `scanner.py` scan_media / scrape_for_library |
| 改封面 | `scanner.py:_apply_scraped_data` + `database.py:_normalize_cover_path` |
| 改右键菜单 | `ContextMenu.tsx`(inline styles) + `MovieCard.tsx` + `Home.tsx` |
| 改文件夹操作 | `scanner.py` 文件夹级函数 + `main.py` 端点 + `Home.tsx` handler |
| 改文件监控 | `watcher.py` |
| 改播放器/字幕 | `VideoPlayer.tsx` + `subtitles.py` |
| 改部署 | `docker-compose.yml` + `Dockerfile` |

## 已知问题

| 问题 | 状态 |
|---|---|
| 手动刮削结果选择后未更新 | **待修复** — 部分影片/Bangumi 库可搜到结果但 apply 后页面不刷新。根因与 `_apply_scraped_data` 封面缓存清除和 COALESCE 的 None 值处理有关，已修复一轮但仍有个别边缘情况 |

### Docker 注意事项
| 问题 | 说明 |
|---|---|
| macOS 端口 | `127.0.0.1` / `localhost` 可能连接重置（Docker Desktop IPv6 兼容），用 `0.0.0.0:27580` |
| SQLite | 不支持 `datetime('now')` 默认值，应用层设置时间 |
