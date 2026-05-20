# MediaTree — 技术文档

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn | 端口 27580，60+ API 端点 |
| 前端 | React 18 + TypeScript 5 + TailwindCSS 3 | Vite 构建 |
| 播放器 | ArtPlayer 5 + React 组件 | 触控手势、键盘快捷键、转码入口、本地播放器入口、VR canvas overlay |
| 字幕 | ArtPlayer subtitle + `@jellyfin/libass-wasm` | ASS/SSA 走 libass canvas，VTT/SRT 走 ArtPlayer 原生字幕层 |
| 数据库 | SQLite (aiosqlite) | WAL + busy_timeout 5s |
| 刮削 | TMDB API v3 / Bangumi API / Javdatabase | 统一 BaseScraper 模板，每库可选，auto 支持 TMDB ID movie/tv 推断 |
| 文件监控 | watchfiles | 只监听启用媒体库，15s 防抖自动增量扫描 |
| 字幕提取 | ffprobe/ffmpeg | 内嵌+外挂，ASS 原文输出，其他格式转 WebVTT |
| 视频流 | 直传 Range 206 / ffmpeg pipe 转码 | ?transcode=1 可选 |
| 封面 | Pillow | resize(max_w=500) → JPEG q=80 |
| 日志 | RotatingFileHandler | data/logs/mediatree.log (2MB×3) |
| 容器 | Docker multi-stage | amd64/arm64 |

## 后端模块

| 文件 | 职责 |
|---|---|
| `main.py` | FastAPI 入口、路由、AuthMiddleware、lifespan、备份恢复 |
| `config.py` | pydantic-settings + config.json + 日志 |
| `database.py` | SQLite CRUD、文件夹树构建、封面路径规范化 |
| `scanner.py` | 文件扫描、NFO 解析、并发刮削分发、封面缓存、文件夹级操作 |
| `scrapers/` | 统一刮削器模板、registry、TMDB/Bangumi/Javdatabase 适配器 |
| `anime_naming.py` | 动画/番剧发布组命名清洗、集数识别、display_title 生成 |
| `watcher.py` | watchfiles 文件监控自动扫描 |
| `jellyfin_compat.py` | Jellyfin 兼容 API 路由（30+ 端点，Series/Season/Episode 层级导航） |
| `jellyfin_auth.py` | 多源鉴权（MediaBrowser Token / X-Emby-Token / Bearer / api_key）+ token/user_data/playback_sessions 表 |
| `jellyfin_mappers.py` | MediaTree → Jellyfin PascalCase JSON 映射 + 电视剧分季分组 |
| `jellyfin_models.py` | Jellyfin 请求 Pydantic 模型 |
| `tmdb.py` | TMDB 搜索/详情/集信息 (Bearer Token + API Key) |
| `bangumi.py` | Bangumi 搜索/详情 (仅动画 type=2) |
| `javdb.py` | Javdatabase 搜索 (独立运行) |
| `covers.py` | 封面/剧照下载压缩缓存、本地单集图匹配、视频截图兜底 |
| `subtitles.py` | 字幕检测/提取、ASS 原文读取、WebVTT 转换、外挂字幕/外挂音轨匹配、字体管理、编码检测 |
| `stream.py` | 视频流 Range 直传 + ffmpeg pipe 转码 |
| `plugins/` | 插件系统 (接口 + 动态加载 + 管理) |

## 数据库表

| 表 | 用途 |
|---|---|
| `movies` | 影片元数据（含 tmdb_*, episode_*, clean_title, episode_number, display_title, external_audio_tracks, fanart_local, cast, crew, media_root） |
| `javdb_cache` | Javdatabase 缓存 |
| `scraper_cache` | TMDB/Bangumi/Javdatabase 通用缓存，key 区分来源和 movie/tv |
| `library_settings` | 每库配置（刮削器/Key/密码） |
| `tags` | 标签（收藏/想看/已看，含 created_at） |
| `categories` | 分类 |
| `config` | 配置持久化 (JSON) |
| `jellyfin_tokens` | Jellyfin 客户端鉴权 token |
| `user_data` | Jellyfin 用户播放进度/收藏/已看状态 |
| `playback_sessions` | Jellyfin 播放会话记录 |

## 前端组件

| 组件 | 职责 |
|---|---|
| `VideoPlayer` | 核心播放器（ArtPlayer 初始化、字幕切换、触控 seek、转码、外部播放器、进度记忆） |
| `artplayerPluginAss` | `@jellyfin/libass-wasm` 集成，负责 ASS/SSA canvas 渲染、字体 fallback、轨道切换 |
| `VRVideoLayer` | Three.js 视频纹理 VR overlay，支持 360/180/SBS/TB 基础模式 |
| `MovieCard` | 统一影片卡片（封面/集标题/Sx·Ey/右键菜单） |
| `ContextMenu` | 右键菜单（inline styles，全局唯一） |
| `EditModal` | 影片/文件夹信息编辑弹窗 |
| `SortDropdown` | 排序下拉 |
| `WatchedBadge` | 已看标记 |
| `Lightbox` | 缩略图灯箱 |

## 关键数据流

### Jellyfin 兼容层 (v2.9)
```
客户端 (VidHub/Infuse/Kodi)
  → GET /System/Info/Public → 服务器发现
  → POST /Users/AuthenticateByName → 登录 → 返回 AccessToken
  → GET /Users/{uid}/Views → 获取媒体库列表
  → GET /Users/{uid}/Items?ParentId=library_xxx&IncludeItemTypes=Series,Movie
    → 返回 Series（多集目录）和 Movie（单文件）
  → GET /Users/{uid}/Items?ParentId=series_xxx
    → 返回 Season 列表
  → GET /Users/{uid}/Items?ParentId=season_xxx
    → 返回 Episode 列表（含 SxEy 索引）
  → POST /Items/{id}/PlaybackInfo → 返回 DirectStreamUrl
  → GET /Videos/{id}/stream.mkv → Range 206 原文件直传
  → POST /Sessions/Playing/Progress → 播放进度回传
```

### Series/Season/Episode 层级
```
文件系统结构                     →  Jellyfin 层级
/media/bgm/ShowName/S01/E01.mkv →  Series → Season 1 → Episode 1
/media/bgm/ShowName/S01/E02.mkv →  Series → Season 1 → Episode 2
/media/bgm/ShowName/S02/E01.mkv →  Series → Season 2 → Episode 1
/media/movie/MovieName.mkv      →  Movie
```

### 视频播放
```
默认直传：/api/stream/{id} → Range 206 → 原生 <video> → 进度条+seek 完整
转码播放：/api/stream/{id}?transcode=1 → ffmpeg pipe H.264+AAC MP4
```

### 字幕渲染
```
用户选字幕或自动选中字幕
→ fetch /api/subtitle/{id}/{n}
→ ASS/SSA: artplayerPluginAss → @jellyfin/libass-wasm canvas 渲染
  → OpenList-style 固定 fallbackFont: /fonts/SourceHanSansCN-Bold.woff2
  → /api/subtitle-fonts 提供 uploaded/system 字体给 availableFonts
  → 常见 ASS 字体名别名映射到 CJK fallback，避免缺字时落到 Latin-only default.woff2
→ VTT/SRT: ArtPlayer subtitle.switch() 原生字幕层
→ 转码播放时叠加 transcodeStart，字幕时间仍对齐原始媒体时间
→ 后端统一以 UTF-8 charset 返回字幕文本，外挂字幕读取支持 utf-8/gb18030/gbk/big5/shift_jis/euc-jp/cp949 等编码
```

### 动画发布组命名解析 (v3.0.1)
```
文件名
  [VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv
→ anime_naming.parse_anime_filename()
  → strip_release_group(): 去掉开头发布组
  → extract_episode_number(): 识别 [12] / [EP12] / S01E12 / 1x12 / 第12话
  → clean_anime_title(): 去掉集数、画质、来源、编码、音频、语言后缀
→ scan_media()
  → clean_title = Senpai wa Otokonoko
  → episode_number = 12
  → display_title = Senpai wa Otokonoko - EP12
  → 同 basename 图片写入 episode_still_local
  → find_external_audio_tracks() 记录外挂音轨 JSON
→ upsert_movie()
  → 只在 TMDB 字段为空时补本地分集字段，避免覆盖真实刮削结果
```

### 外挂字幕与音轨匹配 (v3.0.1)
```
视频 stem = basename
字幕/音轨候选目录 = 同目录 + subtitles/Subs/subs/字幕 子目录

匹配优先级:
1. 完全同 basename
2. basename + 语言后缀 (.zh/.chs/.cht/.ja/.en ...)
3. clean_title 相同且 episode 相同
4. 单视频目录中无 episode 的同片名资源

字幕格式: ass / ssa / srt / vtt
音轨格式: mka / aac / flac / opus / ac3 / eac3 / dts
防护: 候选文件识别出不同 episode 时直接拒绝，避免第 11 集字幕/音轨挂到第 12 集。
```

### Auto 刮削 (v3.0)
```
候选名称 = 目录名 / 父目录名 / 文件名 / 标题 / code
→ extract_tmdb_token_from_name()
  → 显式 [tmdb-movie=ID] 只请求 /movie/{id}
  → 显式 [tmdb-tv=ID]    只请求 /tv/{id}
  → 无类型 tmdbid=ID     本地 infer_tmdb_media_type()
      → S01E01 / Season 01 / 第01集 / 已有 tmdb_type=tv / tmdb_season / episode → tv 加权
      → 单文件 + 年份 / NFO movie / CD1-CD2 多段电影 → movie 加权
      → 强明确只请求一个端点
      → 不明确才并发请求 movie/tv；两边都存在且评分不明确时不应用，fallback
→ TMDB ID 失败或无 token：Bangumi 标题搜索 → TMDB 标题搜索
```

### 刮削器模板与并发 (v3.0)
```
registry: tmdb_movie / tmdb_tv / bangumi / javdatabase / auto / none
→ BaseScraper.search() 返回 ScrapeCandidate，用于手动候选
→ BaseScraper.get_detail() 返回 ScrapeResult，用于应用详情
→ scanner 只按统一结果写入 movies，保留旧逻辑兜底

并发：
  SCRAPE_CONCURRENCY_PER_LIBRARY=4
  SCRAPE_GLOBAL_CONCURRENCY=8
  SCRAPER_API_CONCURRENCY=4
  同一 media_root 用锁串行扫描；不同 media_root 可并发
  HTTP 请求并发，SQLite 写入用单写入信号量收束

缓存 key：
  tmdb_id:movie:123456 / tmdb_id:tv:123456
  tmdb_search:movie:title / tmdb_search:tv:title
  bangumi_search:anime:title / javdb_search:code:ABC-123
```

### 外部播放器字幕
```
VideoPlayer 检测外挂字幕
→ /api/external-play/{id}.m3u 生成本地播放列表
→ 播放列表写入 stream URL 和每条 /api/subtitle-file/{id}/{track}/{name}
→ IINA / MPV 读取播放列表后加载原视频流和外挂字幕
```

### 手动刮削 (文件夹)
```
首页右键 → 手动刮削 → searchScrape(query, scraper)
  → 搜索结果网格 (标题/封面/来源徽标/年份)
  → 点击海报 → applyFolderScrape(source_id, source, media_type)
  → fetch_tmdb_detail / fetch_bangumi_detail → _apply_scraped_data → clearCache() → load()
```

### 文件监控
```
watchfiles.awatch(enabled_media_roots, debounce=15s)
  → 仅处理 mkv/mp4/mov/avi/m2ts/ts/webm/nfo/srt/ass/ssa/vtt/jpg/png/webp
  → 合并同一批变更并按 media_root 触发 run_scan_for_root(trigger="watcher")
  → 同一 media_root 已在扫描时只标记 queued，结束后补跑一次
  → scan_media(root) → upsert_movie → cleanup_deleted_files → scrape_for_library
```

### 封面路径
```
cover_local (cache key) → _normalize_cover_path → /api/cached-cover/{key}
cover_remote (远程URL)  → 直接作为 <img src>
fanart_local             → Folder 页背景图
```

## 当前前端播放器模块

| 文件 | 职责 |
|---|---|
| `components/VideoPlayer.tsx` | ArtPlayer 实例、字幕选择、触控手势、进度保存、转码、外部播放器、VR 设置 |
| `components/artplayerPluginAss.ts` | libass-wasm worker/wasm 加载、ASS/SSA canvas、fallbackFont、availableFonts |
| `components/VRVideoLayer.tsx` | Three.js VideoTexture VR 渲染层 |
| `utils/vttParser.ts` | 保留的 WebVTT/SRT/ASS 文本解析工具 |

## 新增 API（v2.8）

| 路由 | 方法 | 说明 |
|---|---|---|
| `/api/media-info/{id}` | GET | 视频时长、封装、音视频编码信息，包含 `external_audio_tracks` |
| `/api/subtitle-tracks/{id}` | GET | 内嵌 + 外挂字幕轨列表，外挂轨包含 `format` / `is_external` |
| `/api/subtitle-content/{id}/{n}` | GET | 原始字幕内容 |
| `/api/subtitle-file/{id}/{n}/{filename}` | GET | 外部播放器读取的原始外挂字幕文件 |
| `/api/external-play/{id}.m3u` | GET | IINA / MPV 使用的带外挂字幕播放列表 |
| `/api/subtitle-fonts` | GET | 列出上传字体和系统 CJK 字体 |
| `/api/subtitle-fonts/default` | GET/HEAD | 返回首选系统 CJK 字体，便于调试/外部字体消费 |
| `/api/subtitle-fonts/upload` | POST | 上传字体文件 |
| `/api/subtitle-fonts/{name}` | GET/HEAD | 服务字体文件 |
| `/api/subtitle-fonts/{name}` | DELETE | 删除字体 |

## v2.8 UI 规范

- 页面卡片、弹窗、按钮统一使用 8px 为主的圆角。
- 主导航、搜索、封面网格、播放器按钮和设置页表单均适配手机宽度。
- 搜索浮层不再卸载当前路由内容，避免打开页面或聚焦搜索后出现空白界面。
- 可见 UI 不使用 emoji；必要状态用文字、SVG 图标或加载圆环表达。

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
  -t zasenjc/mediatree:3.0 --push .
```

Docker 镜像安装 `fonts-noto-cjk`、`fonts-noto-color-emoji`、`fonts-wqy-microhei`，并在构建阶段执行 `fc-cache -f -v`。这些系统字体会通过 `/api/subtitle-fonts` 暴露给前端 libass。

前端同时内置 `frontend/public/fonts/SourceHanSansCN-Bold.woff2`，构建后由 `/fonts/SourceHanSansCN-Bold.woff2` 提供。ASS/SSA 渲染不等待字体列表接口才显示字幕；它会先用这个 WOFF2 作为稳定 CJK fallback，再用运行时字体列表补充 `availableFonts`。这样字幕可立即显示，同时避免缺失中文/日文/韩文字形时出现方块字。

## 版本

| 版本 | 里程碑 |
|---|---|
| v3.0 | auto 刮削重做、TMDB ID movie/tv 本地推断、统一刮削器模板、并发刮削、按 media_root 安全重刮、watcher 自动增量扫描与刮削 |
| v2.9 | Jellyfin 兼容 API 层（VidHub/Infuse/Kodi 客户端）、Series/Season/Episode 分组、Emby 路径兼容、多源鉴权、播放进度回传 |
| v2.8 | ASS/SSA 特效字幕渲染、外挂字幕播放列表、转码字幕时间修正、手动刮削应用提示、首次引导扫描、移动端与统一圆角 UI |
| v2.5 | 播放器重构(Jellyfin UI+触控)、字幕重写(客户端VTT解析)、流优化(直传优先)、本地播放器调用、手动刮削修复 |
| v2.4 | 文件监控自动扫描、文件夹级批量操作、右键菜单增强、封面+背景分别管理 |
| v2.3 | 代码清洗 & 稳定版 |
| v2.2 | 集数/封面/进度重大修复 |
| v2.1 | 本地刮削优先 & Jellyfin 兼容 |
| v2.0 | 插件化刮削系统 |
