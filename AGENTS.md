# AGENTS.md — MediaTree 项目开发指南

## 项目概述

基于 Docker 的本地影片 Web 浏览管理器。支持多媒体库、插件化刮削（TMDB/Bangumi/Javdatabase）、ArtPlayer 播放器（触控手势/键盘快捷键/移动端全屏适配）、ASS/SSA 特效字幕渲染、外挂字幕播放列表、本地播放器调用、进度记忆。

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
| Jellyfin 兼容层 | jellyfin_compat / _auth / _mappers / _models | 30+ Jellyfin API 端点，VidHub/Infuse 兼容 |
| 前端 | React 18 + TypeScript 5 + TailwindCSS 3 | Vite 构建，原生 `<video>` 播放 |
| 播放器 | ArtPlayer 5 + React wrapper | 自定义手势、键盘快捷键、外部播放器入口、转码入口 |
| 字幕渲染 | ArtPlayer subtitle + @jellyfin/libass-wasm | ASS/SSA 走 libass canvas（延迟初始化，支持 switch/clear/destroy），转码 VTT 客户端时间戳偏移，VTT/SRT 走 ArtPlayer 原生字幕 |
| 数据库 | SQLite (aiosqlite) | WAL + busy_timeout 5s |
| 刮削 | TMDB / Bangumi / Javdatabase | 插件化，Fallback 互备 |
| 字幕 | ffprobe/ffmpeg | 内嵌+外挂，ASS 原文输出，其他格式转 WebVTT |
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
│   ├── jellyfin_compat.py   # Jellyfin 兼容 API 路由 (30+ 端点)
│   ├── jellyfin_auth.py     # 多源鉴权 + token 表 + user_data/playback_sessions 表
│   ├── jellyfin_mappers.py  # MediaTree → Jellyfin 数据映射 + Series/Season/Episode 分组
│   ├── jellyfin_models.py   # Jellyfin 请求 Pydantic 模型
│   ├── tmdb.py / bangumi.py / javdb.py
│   ├── covers.py / subtitles.py / stream.py / models.py
│   └── plugins/             # 插件系统
└── frontend/src/
    ├── api.ts               # API 封装
    ├── pages/ (Home, Folder, Browse, Detail, Favorites, Settings, Login, SetupWizard)
    ├── components/ (VideoPlayer, artplayerPluginAss, MovieCard, ContextMenu,
    │                EditModal, SortDropdown, WatchedBadge, Lightbox)
    └── utils/ (vttParser.ts)
```

## 核心数据流

### 刮削器 Fallback 链
```
"javdatabase" → [javdatabase]          (独立)
"tmdb_movie"  → [TMDB movie ID/标题, bangumi, TMDB movie 标题]
"tmdb_tv"     → [TMDB tv ID/标题, bangumi, TMDB tv 标题]
"tmdb"        → tmdb_movie 兼容别名
"bangumi"     → [bangumi, TMDB tv 标题]
"auto"        → [TMDB ID精确匹配(含movie/tv推断), bangumi, tmdb]
"none"        → 跳过
```

### 扫描 + 刮削
```
os.walk → JAV番号提取/目录标识 → NFO解析 → 本地封面递归查找
  → upsert movies → scrape_for_library()
  → registry/BaseScraper → fallback链 → title_matches 验证 → 封面缓存 → TV集匹配
scraper="auto" 时，目录名/父目录名/文件名/候选标题中的 TMDB token 会作为扫描时自动精确匹配入口。
显式 [tmdb-movie=123] / [tmdb-tv=123] 只请求对应端点；无类型 tmdbid=123 先用本地集数/季目录/年份/NFO 快速推断 movie/tv，强明确只请求一个端点，不明确才并发查 movie/tv。
不同 media_root 可并发扫描/刮削；同一 media_root 由锁保护，不会被 watcher 和手动扫描重复并发执行。
```

### 视频流
```
默认：直传原文件（Range 206），浏览器本地解码 → 进度条+seek 正常
转码：?transcode=1 → ffmpeg pipe H.264+AAC MP4 → 浏览器解码
    转码流无 Content-Length → progress bar 不可用
```

### 播放器 + 字幕渲染 (ArtPlayer + libass-wasm)
```
用户选字幕或自动选中字幕 → fetch /api/subtitle/{id}/{n}
→ ASS/SSA: artplayerPluginAss → @jellyfin/libass-wasm canvas，保留特效/定位
  → fallbackFont 固定使用 /fonts/SourceHanSansCN-Bold.woff2（OpenList-style CJK fallback）
  → 通过 /api/subtitle-fonts 提供 uploaded/system 字体给 availableFonts
  → 常见 ASS 字体名（Source Han/Noto/WenQuanYi/YaHei/SimSun/SimHei/宋体/黑体/微软雅黑等）映射到 CJK fallback
→ VTT/SRT: ArtPlayer 原生 subtitle.switch()
→ 转码播放时通过 transcodeStart/timeOffset 对齐原始媒体时间
→ Docker 内置 Noto CJK / WenQuanYi 字体，前端内置 SourceHanSansCN-Bold.woff2，用户也可通过 /api/subtitle-fonts 上传字体
```

### 外部播放器字幕
```
VideoPlayer 检测外挂字幕 → /api/external-play/{id}.m3u
→ 播放列表写入 /api/stream/{id}
→ 写入每条 /api/subtitle-file/{id}/{track}/{filename}
→ IINA / MPV 读取播放列表并加载外挂字幕
```

### 封面路径
```
cover_local (cache key)  → /api/cached-cover/{key}
cover_remote (远程URL)   → 直接用作 <img src>
fanart_local              → Folder 页 hero 背景
```

### 文件监控自动扫描 (watcher.py)
```
watchfiles.awatch(enabled_media_roots, debounce=15s)
  → 只处理视频/字幕/NFO/封面扩展名
  → 合并变更并按 media_root 触发 run_scan_for_root(trigger="watcher")
  → 同一 media_root 已在扫描时只排队补扫，不并发重复扫描
  → scan_media(root) → upsert → cleanup_deleted → scrape_for_library
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
| `/api/stream/:id` | GET | 视频流(Range + ?transcode=1) |
| `/api/media-info/:id` | GET | 视频时长/封装/音视频编码 |
| `/api/cover/:id` | GET | 封面 |
| `/api/cached-cover/:key` | GET | 压缩封面缓存 |
| `/api/episode-still/:id` | GET | 集剧照 |
| `/api/thumbnail/:id/:n` | GET | 缩略图 |
| `/api/subtitle-tracks/:id` | GET | 字幕轨列表 |
| `/api/subtitle/:id/:n` | GET | ASS 原文或 WebVTT 字幕 |
| `/api/subtitle-content/:id/:n` | GET | 原始字幕内容 |
| `/api/subtitle-file/:id/:n/:filename` | GET | 外部播放器读取的原始外挂字幕 |
| `/api/external-play/:id.m3u` | GET | 带外挂字幕的本地播放列表 |
| `/api/subtitle-fonts` | GET/POST/DELETE | 字幕字体管理 |
| `/api/subtitle-fonts/default` | GET/HEAD | 首选系统 CJK 字体 |
| `/fonts/SourceHanSansCN-Bold.woff2` | GET/HEAD | 前端内置 CJK fallback 字体 |
| `/api/config` | GET/POST | 全局配置 |
| `/api/library-settings` | GET/POST | 每库刮削配置 |
| `/api/media-roots` | GET | 媒体库列表 |
| `/api/library-passwords` | GET/POST | 库密码 |
| `/api/library-verify` | POST | 验证库密码 |
| `/api/categories` | CRUD | 分类 |
| `/api/movies/:id/tags` | POST/DELETE | 标签 |
| `/api/movies/:id` | DELETE/PUT | 删除/编辑影片 |
| `/api/movies/:id/rescrape` | POST | 重新刮削单部 |
| `/api/movies/:id/manual-scrape` | POST | 手动刮削单部(支持source_id) |
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
/api/thumbnail/, /api/subtitle-tracks/, /api/subtitle/, /api/subtitle-content/,
/api/subtitle-file/, /api/external-play/, /api/subtitle-fonts (GET/HEAD), /fonts/, /api/media/,
/System, /Users, /Items, /Videos, /Sessions, /Shows, /Library, /DisplayPreferences, /Genres, /emby
```

### Jellyfin 兼容 API 路由

| 路由 | 方法 | 说明 |
|---|---|---|
| `/System/Info/Public` | GET | 公开系统信息（无需鉴权） |
| `/System/Info` | GET | 完整系统信息 |
| `/Users/AuthenticateByName` | POST | Jellyfin 风格登录 |
| `/Users/Me` | GET | 当前用户信息 |
| `/Users/{userId}/Views` | GET | 媒体库列表 |
| `/Items` / `/Users/{userId}/Items` | GET | 影片列表（Series/Season/Episode 分组） |
| `/Items/{itemId}` | GET | 影片详情 |
| `/Items/{itemId}/PlaybackInfo` | GET/POST | 播放信息 |
| `/Videos/{itemId}/stream` | HEAD/GET | 原文件直传 (Range 206) |
| `/Items/{itemId}/Images/Primary` | GET | 封面图片 |
| `/Videos/{id}/{mid}/Subtitles/{n}/Stream.{fmt}` | GET | 字幕流 |
| `/Sessions/Playing[/Progress/Stopped]` | POST | 播放进度回传 |
| `/Users/{uid}/PlayedItems/{id}` | POST/DELETE | 已看标记 |
| `/Users/{uid}/FavoriteItems/{id}` | POST/DELETE | 收藏标记 |
| `/Shows/NextUp` | GET | 接下来播放 |
| `/Library/MediaFolders` | GET | 媒体文件夹 |
| `/DisplayPreferences/{uid}` | GET/POST | 显示偏好 |

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
| jellyfin_tokens | token, user_name, user_id, client, device, device_id, version |
| user_data | user_id, item_id, playback_position_ticks, play_count, is_favorite, played |
| playback_sessions | play_session_id, user_id, item_id, client, device, position_ticks |

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
| 加刮削器 | 新建 `backend/app/scrapers/xxx_scraper.py` + `registry.py` 注册；必要时补 `scanner.py` fallback |
| 改扫描 | `scanner.py` scan_media / scrape_for_library |
| 改封面 | `scanner.py:_apply_scraped_data` + `database.py:_normalize_cover_path` |
| 改右键菜单 | `ContextMenu.tsx`(inline styles) + `MovieCard.tsx` + `Home.tsx` |
| 改文件夹操作 | `scanner.py` 文件夹级函数 + `main.py` 端点 + `Home.tsx` handler |
| 改文件监控 | `watcher.py` |
| 改播放器 | `VideoPlayer.tsx` + `artplayerPluginAss.ts` + `index.css` |
| 改字幕 | `artplayerPluginAss.ts` + `subtitles.py` + `/api/subtitle-fonts` |
| 改视频流 | `stream.py` |
| 改 Jellyfin 兼容 | `jellyfin_compat.py` (路由) + `jellyfin_mappers.py` (映射) + `jellyfin_auth.py` (鉴权) |
| 改部署 | `docker-compose.yml` + `Dockerfile` |


### Docker 注意事项
| 问题 | 说明 |
|---|---|
| macOS 端口 | `127.0.0.1` / `localhost` 可能连接重置（Docker Desktop IPv6 兼容），用 `0.0.0.0:27580` |
| SQLite | 不支持 `datetime('now')` 默认值，应用层设置时间 |
| 缓存构建 | Docker Hub 偶有连接问题，用 `docker compose build`（不加 `--no-cache`）避免重拉基础镜像 |
