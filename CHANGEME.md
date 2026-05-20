# CHANGEME - MediaTree 版本更新记录

---

## v3.0.1 (2026-05-20) - 动画发布组命名与 VCB-Studio 兼容

### 扫描与标题清洗
- 新增 `anime_naming.py`，集中处理动画/番剧发布组命名解析。
- 扫描阶段写入 `clean_title`、`episode_number`、`display_title` 和 `external_audio_tracks`，用于刮削标题、列表排序、详情返回和后续扩展。
- 支持清洗 `[ANi]`、`[NC-Raws]`、`[Lilith-Raws]`、`[LoliHouse]`、`[VCB-Studio]`、`[喵萌奶茶屋]` 以及其他开头方括号发布组。
- 支持剔除 `[1080P]`、`[WEB-DL]`、`[Baha]`、`[Ma10p_1080p]`、`[x265_flac]`、`[AAC AVC]`、`[10bit]` 等画质、来源、编码和音频标签。
- 支持 `[01]`、`[001]`、`[EP01]`、`[E01]`、`[第01集]`、`[第1话]`、`S01E01`、`S1E1`、`1x01` 集数识别。
- 防误判 `[1080P]`、`[2160P]`、`[2024]`、`[10bit]`、`[Ma10p_1080p]` 为集数。

### 分集显示、排序与剧照
- 多集目录默认按 `tmdb_episode` 或本地 `episode_number` 数字升序排序，VCB-Studio `[05]`、`[09]`、`[12]` 可稳定显示为 EP05、EP09、EP12。
- 本地分集在未刮削出真实集标题时返回 `display_title = 作品标题 - EPxx`。
- 支持与视频完全同 basename 的单集图，以及 `.cover/.still/.thumb` 后缀图作为 `episode_still_local`。
- `/api/episode-still/{id}` 现在按本地剧照、远程剧照、同 basename 图片、视频截图的顺序兜底。

### 外挂字幕与外挂音轨
- 外挂字幕匹配优先级调整为：完全 basename → basename + 语言后缀 → 同片名同集数 → 单视频目录同片名无集数。
- 支持 VCB-Studio 常见字幕：`basename.zh.ass`、`basename.chs.ass`、`basename.cht.ass`、`basename.ja.ass`、`basename.en.ass`。
- 外挂字幕轨返回补充 `format` 和 `is_external=true`，便于播放器和外部播放器入口稳定识别。
- 新增外挂音轨检测，支持 `basename.mka` 和 `.zh/.ja/.en/.jpn/.eng/.chs/.cht` 语言后缀，格式包括 `mka/aac/flac/opus/ac3/eac3/dts`。
- `/api/media-info/{id}` 返回 `external_audio_tracks`，当前不改变视频流直传行为。

### 验证
- `PYTHONPATH=backend python3.11 -m unittest backend.tests.test_anime_naming backend.tests.test_subtitles backend.tests.test_covers backend.tests.test_scanner_tmdbid` 通过。
- `npm run build` 通过，生产构建仅保留 Vite chunk size 常规警告。

---

## v3.0.0 (2026-05-20) - Auto 刮削与 Watcher 增量扫描

### Auto 刮削
- 新增 `TmdbIdToken` 和 `extract_tmdb_token_from_name()`，支持 `[tmdb-movie=123]`、`[tmdb-tv=123]`、`[tmdbid=movie:123]`、`[tmdbid=tv:123]`、`tmdbid=123`、`tmdb-123` 等格式。
- `scraper="auto"` 检测到显式 movie/tv TMDB token 时只请求对应 TMDB 端点，不再默认 movie。
- 无类型 `tmdbid=123` 会先执行本地 `infer_tmdb_media_type()`，基于 SxxExx、Season、EP、第 X 集、已有 tmdb_type、tmdb_season/tmdb_episode、NFO 类型、单文件年份、CD/Disc 多段电影等信号评分。
- 本地评分强明确时只请求一个 TMDB ID 端点；评分不明确时才并发请求 movie/tv 候选。
- movie/tv 两边都存在且本地评分仍不明确时不自动应用，fallback 到 Bangumi → TMDB 标题搜索，避免错误覆盖元数据。
- TMDB ID 精确匹配失败会明确记录“TMDB ID 精确匹配失败，fallback 到标题搜索”。

### TMDB 查询性能
- `fetch_tmdb_by_id(tmdb_id, media_type)` 改为严格类型：`movie` 只请求 `/movie/{id}`，`tv` 只请求 `/tv/{id}`。
- 新增 `fetch_tmdb_candidates_by_id()`，仅在类型不明确时并发查询 movie/tv。
- TMDB ID 缓存 key 区分 `tmdb_id:movie:{id}` 和 `tmdb_id:tv:{id}`。
- TMDB HTTP 请求复用 AsyncClient，并通过 semaphore 限制并发。
- 同进程内相同 `tmdb_id + media_type` 请求复用 task，避免同一轮扫描重复打 TMDB。

### Watcher 自动增量扫描
- watcher 只监听 enabled=true 的媒体库，并周期性刷新监听目标。
- 只处理视频、字幕、NFO、封面扩展名，忽略无关文件。
- 15 秒 debounce 后按 media_root 合并变更，自动触发 `run_scan_for_root(trigger="watcher")`。
- 同一 media_root 同一时间只允许一个扫描任务；扫描期间再次变更会排队，当前扫描完成后补跑一次。
- 自动扫描流程统一为 `scan_media(root)` → `upsert_movie()` → `cleanup_deleted_files()` → `scrape_for_library()`。
- `/api/scan/status` 复用现有进度结构并补充 `trigger` 字段。

### 字幕回退与 CJK 字体
- 回退上一轮“等待字体列表后再创建 libass”的播放器改动，恢复到上一版外挂字幕选择和 ASS 立即渲染逻辑，解决外挂字幕不显示的问题。
- 参考 OpenList 的 libass 字体方案，新增前端内置 `SourceHanSansCN-Bold.woff2`，并通过 `/fonts/SourceHanSansCN-Bold.woff2` 作为固定 CJK `fallbackFont`。
- ASS/SSA 字幕不再把 libass fallback 落到自带 Latin-only `default.woff2`；常见 Source Han / Noto / WenQuanYi / YaHei / SimSun / SimHei / 宋体 / 黑体 / 微软雅黑等字体名会映射到 CJK fallback。
- 后端新增 `/api/subtitle-fonts/default`，字体 API 支持 GET/HEAD 和正确 font MIME；Docker 内系统 CJK 字体列表优先显示 SC/CN 字族，便于排查。

### 验证
- Docker Python 3.12：`PYTHONPATH=/app python -m unittest /app/tests/test_scanner_tmdbid.py` 通过。
- `python -m compileall backend/app` 通过。
- `npm run build` 通过，生产构建仅保留 Vite chunk size 常规警告。
- `docker compose build && docker compose up -d` 通过；`/fonts/SourceHanSansCN-Bold.woff2` 返回 `font/woff2` 且文件头为 `wOF2`。

---

## v2.9.0 (2026-05-20) - Jellyfin 兼容 API 层

### Jellyfin 兼容 API
- 新增 30+ Jellyfin 风格 API 端点：`/System/Info/Public`、`/Users/AuthenticateByName`、`/Users/{uid}/Views`、`/Items`、`/Items/{id}/PlaybackInfo`、`/Videos/{id}/stream`、`/Sessions/Playing` 等。
- 支持 VidHub / Infuse / Kodi / VLC / IINA / mpv 直接添加为 Jellyfin 服务器。
- 多客户端鉴权：MediaBrowser Token、X-Emby-Token、Bearer Token、api_key、query token 统一支持。
- Emby 路径兼容：`/emby/*` 请求自动重写到 Jellyfin 路径，通过 `EmbyPathRewriteMiddleware` 实现。

### Series/Season/Episode 分组
- 电视剧/番剧自动按 Series → Season → Episode 层级分组展示。
- 通过 `folder_levels` 字段解析季文件夹（S01/S02），多文件目录自动识别为系列。
- 集数自动提取（SxxExx / [01] / EP01 / 第X集 多种格式）。
- 支持 `IncludeItemTypes=Series,Movie,Episode` 过滤，`ParentId` 层级导航。
- Series/Season 伪 ID 使用 `series_` / `season_` 前缀，基于路径 hash 生成稳定 ID。

### DirectPlay 优先
- PlaybackInfo 默认 `SupportsDirectPlay=true`、`SupportsTranscoding=false`。
- `/Videos/{id}/stream` 原文件直传，不转码 E-AC-3 / DTS / TrueHD / MKV / ASS。
- 视频流支持 Range 206、HEAD、Content-Disposition: inline。
- 字幕流支持 `/Videos/{id}/{mid}/Subtitles/{n}/Stream.{ass,srt,vtt}`。
- 字幕轨道嵌入 PlaybackInfo MediaStreams（含 DeliveryUrl / DeliveryMethod）。

### 播放进度与会话
- 新增 `user_data` 表：存储播放位置、播放次数、收藏、已看状态。
- 新增 `playback_sessions` 表：记录播放会话（client/device/position）。
- `/Sessions/Playing/Progress` 频繁调用时安全节流，不产生过多日志。
- `/Sessions/Playing/Stopped` 接近结尾（>90%）自动标记 Played=true。
- 新增 `jellyfin_tokens` 表：持久化客户端鉴权 token。

### 图片与字幕
- `/Items/{id}/Images/Primary` 支持 Series/Season/Episode 三级封面。
- `/Items/{id}/Images/Backdrop` 返回 fanart 背景图。
- 封面服务支持 ETag 和 If-None-Match 返回 304。
- `/DisplayPreferences/{uid}` 返回默认 Poster 视图偏好。

### 新增文件
- `backend/app/jellyfin_compat.py` — Jellyfin 兼容路由（1274 行）
- `backend/app/jellyfin_auth.py` — 多源鉴权 + token 管理（204 行）
- `backend/app/jellyfin_mappers.py` — 数据映射 + Series/Season/Episode 分组（628 行）
- `backend/app/jellyfin_models.py` — 请求 Pydantic 模型（36 行）

### 修改文件
- `backend/app/main.py` — 注册 Jellyfin 路由器 + EmbyPathRewriteMiddleware + AuthMiddleware 白名单扩展

---

## v2.8.0 (2026-05-19) - 字幕完整渲染 + 移动端 UI + Docker 2.8

### 字幕与外部播放
- ASS/SSA 字幕改为 JASSUB/libass canvas 渲染，保留特效、字体、定位、描边和多行排版。
- `SubtitleRenderer.tsx` 保留 DOM fallback：JASSUB 启动失败时自动使用 ASS 解析器输出基础字幕，避免完全无字幕。
- 修正转码播放字幕时间：`?transcode=1&start=` 后以前端 `transcodeStart` 叠加视频当前时间，字幕仍按原始媒体时间同步。
- 自动选轨改为优先选择外挂 ASS/SRT/VTT 等文本字幕，避免优先选中 PGS 图形字幕后无法显示。
- `/api/subtitle-tracks/{id}` 加入认证白名单，字幕轨列表不再因 token 状态导致播放器拿不到轨道。
- `/api/subtitle-file/{id}/{track}/{filename}` 提供原始外挂字幕文件，`/api/external-play/{id}.m3u` 生成 IINA / MPV 可用的本地播放列表。
- 外部播放列表在 Docker Desktop 下自动把 `0.0.0.0` 改为 `127.0.0.1`，避免外部播放器无法连接。

### 刮削与命名兼容
- 手动刮削应用时加入右下角“正在应用刮削结果”提示，单影片和文件夹级应用都可见。
- 番剧分集命名兼容 `[组标] 片名 [01][画质][音画格式].mkv`，读取 `[01]` 作为集数并显示在分集封面。
- 首次引导页保存库刮削器配置后自动触发首次全库扫描和刮削，扫描/刮削进度由右下角弹窗显示。
- TMDB 配置文案调整为 API 读访问令牌，保留旧版 API Key 兼容。

### UI 与移动端
- 主导航、搜索框、首页网格、浏览页网格、详情页按钮组、设置页表单、手动刮削弹窗和封面弹窗补齐移动端布局。
- 搜索浮层不再卸载当前路由内容，避免聚焦搜索或进入登录流程时出现空白主区域。
- 页面卡片、弹窗、按钮统一为简约深色和 8px 圆角风格；清理可见 UI 中的 emoji、箭头和勾号装饰。
- 前端 favicon 改为几何 SVG 图标，不再使用 emoji。

### 验证与发布
- 前端生产构建通过。
- 后端 Python 编译检查通过。
- Docker 本地构建与运行通过后发布 `zasenjc/mediatree:2.8`。

---

## v2.5.0 (2026-05-18) — 播放器重构 + 字幕重写 + 流优化

### 播放器重构
- **自定义 Jellyfin 风格播放器**：完全重写 `VideoPlayer.tsx`，舍弃 video.js（从未使用），使用原生 `<video>` 元素构建完整自定义 UI
- **触控手势系统** (`GestureLayer.tsx`)：
  - 双击左/右 1/3：快退/快进 5s，双击中央：暂停/播放
  - 垂直滑动左半屏：亮度，右半屏：音量
  - 水平滑动：拖拽进度
- **OSD 中央覆盖层** (`OSD.tsx`)：播放/暂停/快进/快退/音量图标指示
- **键盘快捷键**：Space/K 暂停, ←→快进快退, ↑↓ 音量, F 全屏, M 静音, J/L 速度调节
- **进度条拖拽**：onMouseDown+Move+Up 完整拖拽逻辑
- **画中画按钮** + **全屏适配**
- **本地播放器调用**：IINA / MPV URL scheme 按钮 + 复制链接

### 字幕系统重写
- **放弃浏览器原生 `<track>` + `::cue`**（索引错位、样式限制、Safari不兼容）
- **客户端 VTT 解析器** (`utils/vttParser.ts`)：解析 WebVTT → `[{start, end, text}]`
- **自定义 DOM overlay 渲染** (`SubtitleRenderer.tsx`)：fetch VTT → rAF 同步 video.time → CSS div 渲染
  - 完整 CSS 控制：fontSize / fontFamily / color / textShadow / background
  - 不受浏览器 `::cue` 限制，全浏览器一致
- **字幕设置 UI**：字号 6 档、颜色 5 色、背景透明度、字体选择
- **外挂字幕增强匹配**：`{stem}.{lang}.{ext}` 和 `{stem}_{lang}.{ext}` 双模式
- **`_guess_lang` 修复**：set 交集替代子串匹配，杜绝 `"japanese"`→eng 误判
- **`_post_process_vtt` 修复**：不再删除 cue 间空行，保留 WebVTT 规范格式

### 视频流优化
- **默认直传原文件**：移除自动音频转码，Range 206 → 进度条 + seek 完整
- **可选转码**：`?transcode=1` → ffmpeg pipe H.264+AAC MP4
- **`<video src={streamSrc}>`**：直接用 video 的 src 属性，不用 `<source>` 子元素
- **`key={streamSrc}` + `v.load()`**：转码切换时强制重建 video 元素
- **音视频错误提示**：解码失败时弹窗提示"切换为转码播放"

### 刮削修复
- **单影片手动刮削 source_id 传递**：前端发送 `source_id`+`media_type`，后端直接 fetch 详情，避免重新搜索导致匹配错误
- **`_apply_scraped_data` 清理**：移除无用 `code` 参数，新增 `return affected`
- **`apply_folder_scrape_result`**：移除重复 bangumi 死代码，修正参数传递

### 新增 API
- `/api/subtitle-content/{id}/{n}` — 原始字幕内容
- `/api/subtitle-fonts` (CRUD) — 字体上传/列表/删除/服务

### 移除
- `hls.js` 依赖 — 之前的 HLS 实验方案（不稳定，已回退）
- `video.js` 依赖 — 从未实际使用

### 文档更新
- AGENTS.md / TECHNICAL.md / README.md / CHANGEME.md 全面更新至 v2.5.0

---

## v2.4.0 (2026-05-17) — 文件监控 + 文件夹级操作 + 右键菜单增强

### 新增
- **文件监控自动扫描**：`watcher.py` 使用 watchfiles 监控所有媒体根目录，15 秒防抖自动增量扫描新增/删除文件
- **文件夹级批量操作**：首页文件夹卡片右键菜单支持对整个目录执行重新刮削、手动刮削、更换封面/背景、编辑元数据、删除
- **手动刮削搜索选择器**：搜索结果网格展示（标题/封面/来源/年份），用户自选应用到整个目录或单独更换背景
- **封面与背景分别管理**：更换封面弹窗同时展示竖屏海报和横屏 Fanart
- **文件夹级 API**：`/api/rescrape-folder`、`/api/apply-folder-scrape`、`/api/search-scrape`、`/api/search-backdrops`、`/api/folder/cover`、`/api/folder/backdrop`、`/api/folder/edit`、`/api/folder/delete`

### 修复
- 右键菜单改用 inline styles（Tailwind 动态类打包丢失问题）
- 右键菜单全局唯一关闭机制（`activeOnClose` 模块变量）
- 手动刮削 apply 后 `cover_local` 不清除导致旧封面霸占显示 — 先清 NULL 再下载新缓存
- `dict.get("poster_url", "")` 当值为 None 时返回 None 而非 ""的 bug — 改用 `or ""` 处理
- Folder 页背景图高度自适应（vh 单位 + 渐变仅底部）
- 刮削器搜索从只看第 1 条改为遍历前 3 条结果
- TMDB 集号匹配正则扩展：`第X集`、`^01.`、`#01`、`No.01`
- 备份恢复后自动清除缓存 + 刷新页面
- 日志输出到文件：`global` 声明 + handler 挂载到命名 logger
- 首页/Browse/Favorites 各自独立卡片组件，不复用 MovieCard

### 已解决（来自 v2.3 待改进）
- 部分番剧无封面 — 搜索遍历前 3 条 + 标题匹配放宽
- TMDB 集号匹配 — 正则扩展
- 备份恢复后需刷新 — 自动 clearCache + reload
- 日志未输出到文件 — global 声明
- Folder 背景模糊 — 移除 blur-xl，vh 自适应
- Folder 标题显示集标题 — display_title 查询排除剧集标题

### 文档更新
- AGENTS.md 精简重写，清理已解决问题
- README.md / TECHNICAL.md / CHANGEME.md 同步更新
- 当时记录手动刮削为待改进问题，后续版本已修复

---

## v2.3.0 (2026-05-16) — 代码清洗 & 稳定版

### Bug 修复
- 修复 `/api/cover/{id}` 端点：`cover_local` 现为 cache key，增加 covers_dir 回退查找
- 修复 `/api/episode-still/{id}` 缺少 AuthMiddleware 白名单导致 401
- 修复 Settings 页进度条轮询：移除 `not_found` 提前终止，增加 120 次上限
- 修复 `get_movies()`/`search_movies()` SQL SELECT 缺少 TMDB 字段导致前端集数/封面不显示
- 修复日志文件未写入：`setup_file_logging()` 移至 lifespan 阶段初始化
- 修复 Bangumi.py `stype` 变量未定义错误
- 修复封面缓存路径：`cover_local` 存 cache key → `_normalize_cover_path()` → `/api/cached-cover/{key}`

### 代码清洗
- 删除 `config.py` 重复的 `tmdb_api_key` 声明和未使用的 `bangumi_enabled`
- 删除 `config.py` 未使用的全局变量 `log_dir`/`log_file`（改为局部变量）
- 删除 `scanner.py` 未使用函数 `_get_media_root_label()`
- 删除 `database.py` 重复的 `clear_library_scraped_data()` 函数
- 删除 `database.py` `library_settings` 表未使用列 `bangumi_type`
- 删除 `database.py` `save_library_settings()` 未使用参数 `bangumi_type`
- 删除 `tmdb.py` 未使用 `import asyncio`
- 删除 `bangumi.py` 未使用 `import json, asyncio`
- 删除 `main.py` 未使用 `import PlainTextResponse`
- 删除 `config.py` 未使用 `bangumi_type` 字段（BGM 硬编码 type=2）

### 文档更新
- AGENTS.md 完整重写：包含所有新 API、数据结构、数据流、已知问题
- CHANGEME.md 更新至最新版本
- README.md 更新镜像地址和功能列表
- TECHNICAL.md 更新技术栈说明

---

## v2.2.0 (2026-05-16) — 集数/封面/进度重大修复

### 新增
- **季度选项卡**：Folder 页自动检测 S01/S02 子目录，生成季节筛选 tabs
- **发行日期排序**：backend sort_map + 前端按钮（Home/Folder/Browse）
- **Settings 扫描进度条**：每库独立进度 + 实时日志面板
- **数据库备份恢复**：`GET /api/backup?type=core|full` + `POST /api/restore/upload`
- **集剧照端点**：`/api/episode-still/{movieId}` 服务本地/远程集剧照
- **统一影片卡片** `MovieCard.tsx`：集标题/Sx·Ey 徽标/集剧照

### 变更
- javdb 不参与 fallback：独立运行，tmdb↔bangumi 互备
- BGM 仅动画：硬编码 type=2，删除真人剧集选项
- 标题匹配增强：CJK/Romaji/Alpha 多路匹配
- 封面/剧照本地压缩缓存：Pillow → data/covers/ + data/stills/
- 扫描进度追踪：`_scan_progress[media_root]` → `GET /api/scan/status`
- 首页封面智能处理：`getCoverSrc()` 区分远程 URL/本地路径/cache key
- Settings 页 UI 统一：卡片式 + 统一间距 + 统一色系
- 首页移除"重新扫描"按钮，迁至 Settings 页媒体库配置

### 数据库新增字段
- `movies.tmdb_id`, `tmdb_type`, `tmdb_season`, `tmdb_episode`
- `movies.episode_title`, `episode_overview`, `episode_still`, `episode_still_local`

---

## v2.1.0 (2026-05-16) — 本地刮削优先 & Jellyfin 兼容

### 新增
- **Jellyfin/Kodi 文件夹结构兼容**：识别非 JAV 番号目录、NFO 文件解析
- **本地元数据优先**：NFO 标题 + 本地封面齐全则跳过在线刮削
- **递归封面查找**：子目录（S01）向上递归查找封面
- **刮削器 fallback 链**：首选失败后自动尝试其余刮削器
- **标题匹配验证**：刮削结果与目录名对比，不匹配丢弃
- **默认关闭所有在线刮削器**：`library_settings.scraper` 默认 `'none'`

### 修复
- TMDB 支持 Bearer Token (v4) + API Key (v3) 双认证
- 首页远程封面 URL 直接作为 `<img src>`，不再走 `/api/media/`
- 文件夹树 cover_remote 作为 fallback 封面源
- 季节目录检测：S01/S02 等子目录使用父级目录名搜索
- 关键词查询变体：特殊字符剥离后搜索（解决 BanG Dream! 匹配问题）

---

## v2.0.0 (2026-05-16) — 插件化刮削系统
(内容同原版，略)

- **每库独立配置**：不同媒体库可选不同刮削器
- **引导向导**：首次部署打开网页弹出 SetupWizard，逐库配置
- **设置页管理**：后期可随时修改刮削器、API Key、搜索类型

### 封面压缩缓存
- 在线封面下载后 resize(max_width=500) → JPEG q=80 压缩存储
- `data/covers/` 目录本地缓存，`/api/cached-cover/{key}` 端点服务

### 字幕支持
- 内嵌字幕检测：`ffprobe` 解析 MKV 字幕流
- 实时字幕提取：`ffmpeg` 转 WebVTT，`/api/subtitle/{id}/{n}` 端点
- 外挂字幕：同目录自动识别 `.srt/.ass/.ssa/.vtt`
- 前端播放器：`<track>` 元素 + 字幕选择按钮

### MKV格式增强
- 支持 AVC/HEVC/AV1 编码
- HTTP Range 流式播放不变

### 日志系统
- `RotatingFileHandler` → `data/logs/mediatree.log`（2MB×3滚动）
- 统一 `logger` 输出关键操作日志

### 数据库新增表
- `library_settings`：每库配置（刮削器/API Key/密码）
- `scraper_cache`：通用刮削缓存（source+query+data）

---

## v1.5.0 (2026-05-16)

### 功能新增
- 媒体库密码保护、排序修正(mtime)、滚动恢复、URL排序持久化
- 文件夹树 DB 构建、代码清洗、默认排序改为最近添加

---

## v1.1.0 (2026-05-15)
- 搜索功能、多媒体库、连接池、配置持久化、前端缓存

## v1.0.0 (2026-05-15)
- 正式发布：认证、演员筛选、灯箱、安全加固

## v0.2.0 (2026-05-15)
- 中文化、首页重设计、收藏系统、javdatabase.com 数据源

## v0.1.x (2026-05-15)
- 初始开发：FastAPI + React + SQLite + Docker

### 功能新增
- **媒体库密码保护**：设置页为每个媒体库独立设置密码，切换时需验证
- **排序修正**：`created_at` 改为文件夹文件系统修改时间（mtime），排序更准确
- **滚动位置恢复**：页面切换返回时恢复滚动位置（sessionStorage）
- **排序持久化**：排序选择存储在 URL search params，导航返回保持
- **文件夹树 DB 构建**：1 次 SQL 查询替代文件系统遍历，10-50x 速度提升
- **默认排序改为最近添加**：首页、文件夹页、收藏页默认 created_desc

### 代码清洗
- 删除 `get_folder_tree_fast`、`_build_node_fast`、`get_folder_tree` 等文件系统遍历代码
- 删除未使用的 `get_folders`、`get_config_value`、`set_config_value` 函数
- 删除 `MovieCard.tsx` 废弃组件
- 删除 `javdbAutoLogin`、`javdb_cookie` 等未实现功能
- 删除 config.py 中未使用的字段（`scan_interval_minutes`、`host`、`port`、`database_url`）
- 统一标签加载为批量查询模式
- 移除 `store.ts` 未使用的 `isExcluded`

### 修复
- 修复 API 401 重定向在登录页的无限循环问题
- 修复数据库迁移时索引创建在列不存在之前的问题
- 修复 `search_movies` 中不存在的 `setdefault` 方法调用

---

## v1.1.0 (2026-05-15)

### 功能新增
- **搜索功能**：页面右上角搜索框，实时搜索影片编号/标题/演员
- **多媒体库支持**：所有库挂载于 /media/ 下，子目录名即库名
- **切换媒体库自动刷新**：key prop 强制组件重新挂载
- **浏览页文件夹选择持久化**：点击侧栏文件夹更新 URL，返回时保持选中

### 性能优化
- 数据库连接池化（单连接复用 + busy_timeout 5s）
- 影片列表查询改为精确列选择（排除大 JSON 字段）+ 批量标签查询
- 配置运行时修改持久化到 config.json
- 前端 API 响应缓存 120s TTL

### 排序调整
- 删除"时间正序/时间倒序"（date_asc/date_desc）
- 新增"随机排列"选项
- 统一所有封面网格页排序按钮

---

## v1.0.0 (2026-05-15)

### 正式发布
- 完整的技术文档（TECHNICAL.md）
- 全面的代码审查和 bug 修复
- 安全加固：SPA 中间件异常不再静默吞掉、/api/media/ 符号链接路径解析
- 影片详情页演员名可点击跳转该演员全部片单
- 缩略图改为灯箱模式（方向键切换、ESC 关闭）
- 设置页标题与详情页来源链接联动
- 首页排除机制持久化（localStorage）
- 认证系统（AUTH_USER/AUTH_PASS）
- 登录页移出主布局，独立全屏渲染

---

## v0.2.0 (2026-05-15)

### 大版本更新
- 全部界面文字中文化，移除所有 emoji
- 首页仅展示顶层文件夹卡片，封面随机取自子文件夹
- 新增独立 `/folder` 页面（卡片网格，无缩放），从首页点进逐层浏览
- 浏览页重做为 Finder 风格列表视图，带左侧文件夹勾选筛选
- 缩略图悬停缩放改用 `transform: scale()`，修复 z-index 层叠 bug
- 新增排序：按添加时间正序/倒序、按文件夹名称
- Categories 改为收藏页，影片详情页添加收藏按钮
- 新增收藏 API (`/api/favorites`)，基于 tag 系统
- 文件夹树新增 `random_cover` 字段，随机选取子目录封面

---

## v0.1.3 (2026-05-15)

### Bug 修复 & 功能改进
- 修复 `get_movies` SQL 计数查询语法错误导致 API 崩溃返回 HTML
- 新增 `/api/media/{path}` 端点代理静态媒体文件（覆盖图、封面等）
- 影片文件夹筛选改用 `folder_levels` 字段，支持多层路径精确匹配
- 首页改为递归渲染，完整展示任意深度的文件夹层级
- 封面图 URL 编码修复：`#` 等特殊字符通过 encodeURIComponent 正确处理
- 首页布局优化：响应式网格对齐、空 children 数组修复
- 修复文件夹树扫描器遇到特殊文件时 is_dir() 抛 PermissionError

---

## v0.1.2 (2026-05-15)

### Bug 修复
- 修复首页 404 问题：FRONTEND_DIR 路径计算错误（多一层 parent）
- 改用 SPAFallbackMiddleware 替代 StaticFiles mount 根路径
- 非 `/api/*` 的 404 请求自动返回 index.html 实现 SPA 客户端路由

---

## v0.1.1 (2026-05-15)

### 项目重命名 & 部署调整
- 项目名称从 jav-browser 更名为 **MediaTree**
- 默认端口从 8090 改为高位端口 **27580**
- 编写 README 使用说明

---

## v0.1.0 (2026-05-15)

### 初始开发
- 项目初始化，确定技术栈：FastAPI + React + TailwindCSS + SQLite
- Docker 部署方案，支持一键启动
- 后端：文件递归扫描器、JAVDB 数据抓取模块、MP4 视频流、RESTful API
- 前端：Vite + React + TypeScript，首页分类卡片、影片浏览、详情播放、设置页
- 参考项目：sakuramedia, JavdBviewed
