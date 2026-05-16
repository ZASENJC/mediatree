# MediaTree — 技术文档

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn | 端口 27580，60+ API 端点 |
| 前端 | React 18 + TypeScript 5 + TailwindCSS 3 | Vite 构建 |
| 数据库 | SQLite (aiosqlite) | WAL + busy_timeout 5s |
| 刮削 | TMDB API v3 / Bangumi API / Javdatabase | 插件化，每库可选 |
| 文件监控 | watchfiles | 15s 防抖自动增量扫描 |
| 字幕 | ffprobe/ffmpeg | 内嵌+外挂 → WebVTT |
| 封面 | Pillow | resize(max_w=500) → JPEG q=80 |
| 日志 | RotatingFileHandler | data/logs/mediatree.log (2MB×3) |
| 容器 | Docker multi-stage | amd64/arm64 |

## 后端模块

| 文件 | 职责 |
|---|---|
| `main.py` | FastAPI 入口、路由、AuthMiddleware、lifespan、备份恢复 |
| `config.py` | pydantic-settings + config.json + 日志 |
| `database.py` | SQLite CRUD、文件夹树构建、封面路径规范化 |
| `scanner.py` | 文件扫描、NFO 解析、刮削器分发、封面缓存、文件夹级操作 |
| `watcher.py` | watchfiles 文件监控自动扫描 |
| `tmdb.py` | TMDB 搜索/详情/集信息 (Bearer Token + API Key) |
| `bangumi.py` | Bangumi 搜索/详情 (仅动画 type=2) |
| `javdb.py` | Javdatabase 搜索 (独立运行) |
| `covers.py` | 封面/剧照下载压缩缓存 |
| `subtitles.py` | 字幕检测/提取/WebVTT 转换 |
| `stream.py` | 视频流 Range + MKV 编码检测 |
| `plugins/` | 插件系统 (接口 + 动态加载 + 管理) |

## 数据库表

| 表 | 用途 |
|---|---|
| `movies` | 影片元数据（含 tmdb_*, episode_*, fanart_local, cast, crew, media_root） |
| `javdb_cache` | Javdatabase 缓存 |
| `scraper_cache` | TMDB/Bangumi 通用缓存 |
| `library_settings` | 每库配置（刮削器/Key/密码） |
| `tags` | 标签（收藏/想看/已看，含 created_at） |
| `categories` | 分类 |
| `config` | 配置持久化 (JSON) |

## 前端组件

| 组件 | 职责 |
|---|---|
| `MovieCard` | 统一影片卡片（封面/集标题/Sx·Ey/右键菜单） |
| `ContextMenu` | 右键菜单（inline styles，全局唯一） |
| `EditModal` | 影片/文件夹信息编辑弹窗 |
| `SortDropdown` | 排序下拉 |
| `VideoPlayer` | 播放器（进度记忆/字幕轨） |
| `WatchedBadge` | 已看标记 |
| `Lightbox` | 缩略图灯箱 |

## 关键数据流

### 手动刮削 (文件夹)
```
首页右键 → 手动刮削 → searchScrape(query, scraper)
  → 搜索结果网格 (标题/封面/来源徽标/年份)
  → 点击海报 → applyFolderScrape(source_id, source, media_type)
  → fetch_tmdb_detail / fetch_bangumi_detail → _apply_scraped_data → clearCache() → load()
```

### 文件监控
```
watchfiles.awatch(media_roots, debounce=15s)
  → 检测变更 → scan_media(root) → upsert_movie → cleanup_deleted → scrape_for_library
```

### 封面路径
```
cover_local (cache key) → _normalize_cover_path → /api/cached-cover/{key}
cover_remote (远程URL)  → 直接作为 <img src>
fanart_local             → Folder 页背景图
```

## 新增 API（v2.4）

| 路由 | 方法 | 说明 |
|---|---|---|
| `/api/search-scrape` | POST | 搜索刮削候选（含 source_id） |
| `/api/search-backdrops` | POST | 批量获取背景图 URL |
| `/api/rescrape-folder` | POST | 文件夹重新刮削 |
| `/api/rescrape-folder-manual` | POST | 文件夹手动刮削 |
| `/api/apply-folder-scrape` | POST | 文件夹直接应用刮削结果 |
| `/api/folder/cover` | POST | 更换文件夹封面 |
| `/api/folder/backdrop` | POST | 更换文件夹背景图 |
| `/api/folder/edit` | PUT | 编辑文件夹元数据 |
| `/api/folder/delete` | POST | 删除文件夹 |

## Docker 构建

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t zasenjc/mediatree:latest --push .
```

## 版本

| 版本 | 里程碑 |
|---|---|
| v2.4 | 文件监控自动扫描、文件夹级批量操作、右键菜单增强、封面+背景分别管理 |
| v2.3 | 代码清洗 & 稳定版 |
| v2.2 | 集数/封面/进度重大修复 |
| v2.1 | 本地刮削优先 & Jellyfin 兼容 |
| v2.0 | 插件化刮削系统 |
