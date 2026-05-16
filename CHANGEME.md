# CHANGEME - MediaTree 版本更新记录

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
- 新增手动刮削为已知待修复问题

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
