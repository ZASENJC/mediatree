# MediaTree

本地影片 Web 浏览管理器。支持电影/动画/番剧刮削、Jellyfin 兼容 API（VidHub/Infuse/Kodi 客户端）、Series/Season/Episode 分组、集数匹配、触控手势播放器、ASS/SSA 特效字幕渲染、本地播放器调用、多媒体库密码保护、文件监控自动扫描。

## 特性

- **Jellyfin 兼容 API** — 实现 `/System/Info/Public`、`/Users/AuthenticateByName`、`/Users/{id}/Views`、`/Items`、`/Videos/{id}/stream`、`/Sessions/Playing` 等 30+ Jellyfin 风格端点，VidHub / Infuse / VLC / IINA / mpv / Kodi 可直接添加
- **电视剧分季分组** — 自动检测多集目录和 S01/S02 季文件夹，按 Series → Season → Episode 层级展示
- **DirectPlay 优先** — 服务端不转码 E-AC-3 / DTS / TrueHD / MKV / ASS，原文件直传，由客户端播放器解码
- **多客户端鉴权** — MediaBrowser Token / X-Emby-Token / Bearer / api_key 统一支持
- **Emby 路径兼容** — `/emby/*` 路径自动重写，兼容 Emby 客户端
- **ArtPlayer 播放器** — ArtPlayer 5 + React，触控手势（双击快进/快退、左右滑动 seek）、键盘快捷键、画中画、转码入口、本地播放器入口、基础 VR 模式
- **客户端字幕渲染** — ASS/SSA 使用 `@jellyfin/libass-wasm` canvas 渲染，VTT/SRT 使用 ArtPlayer 原生字幕层，保留外挂字幕和外部播放器播放列表
- **本地播放器调用** — 一键拉起 IINA / MPV 播放，外挂字幕通过播放列表传递，支持复制流链接
- **插件化刮削** — 自动模式（显式 TMDB movie/tv ID → 本地类型推断 → Bangumi → TMDB）、TMDB（电影/电视剧/集数匹配）、Bangumi（动画）、Javdatabase（JAV）
- **Jellyfin 结构兼容** — 识别 NFO 元数据、递归封面查找、本地数据优先
- **Fallback 链** — 刮削器互备（tmdb↔bangumi），javdb 独立运行
- **集数匹配** — TMDB TV 季节/集数自动识别，兼容 `[组标] 片名 [01][画质][格式].mkv` 番剧命名，集剧照本地压缩缓存
- **动画发布组命名兼容** — 扫描时清洗 `[ANi]`、`[NC-Raws]`、`[VCB-Studio]` 等发布组标签和 `[1080P]`、`[Ma10p_1080p]`、`[x265_flac]` 等技术标签，识别 `[01]`、`[EP01]`、`S01E01`、`1x01`、`第1话` 集数并按数字排序
- **单集资源匹配** — 支持同 basename 的单集封面/剧照（`.jpg/.png/.webp`、`.cover/.still/.thumb`）和 VCB-Studio 常见外挂字幕、外挂音轨命名
- **季度选项卡** — Folder 页自动检测 S01/S02 等子目录
- **右键菜单** — 首页文件夹/Folder 页影片右键操作：重新/手动刮削、换封面/背景、编辑、删除
- **文件监控** — watchfiles 自动检测视频、字幕、NFO、封面变更，15 秒防抖后按启用媒体库自动增量扫描和刮削
- **首次引导** — 首次打开自动弹出 SetupWizard，逐库配置刮削源，保存后自动启动首次全库扫描和刮削
- **多媒体库** — 多个库挂载于 `/media/` 下，独立配置
- **库密码** — 为敏感媒体库设置独立密码
- **字幕支持** — 内嵌字幕检测 + 外挂字幕自动识别（`.chs.srt` / `.en.ass` / `_cht.srt` 等命名）+ 编码识别 + ASS 原文输出 + ffmpeg WebVTT 转换 + CJK 字体 fallback
- **响应式 UI** — 统一 8px 圆角、简约深色界面，首页、浏览、详情、设置和弹窗均适配移动端
- **封面压缩** — 在线封面/剧照本地缓存（JPEG 500px/300px），节省带宽
- **备份恢复** — 核心数据库/完整（含封面）备份下载 + 上传恢复
- **搜索 / 排序 / 收藏 / 灯箱 / 认证**

## 快速开始

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:3.0
    ports:
      - "27580:27580"
    volumes:
      - /path/to/movies:/media/库1:ro
      - /path/to/anime:/media/动画:ro
      - ./data:/app/data
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=password
```

```bash
docker compose up -d
# 访问 http://localhost:27580
```

## 刮削数据源

| 数据源 | 需要 Key | 适合 | 说明 |
|---|---|---|---|
| TMDB | 是 ([免费申请](https://www.themoviedb.org/settings/api)) | 电影/电视剧/集数 | 推荐填写 API 读访问令牌，兼容旧版 API Key |
| Bangumi | 否 | 动画/番剧 | 仅搜索动画 (type=2) |
| Javdatabase | 否 | JAV 番号 | 独立运行，不参与 fallback |
| 自动 | 视 TMDB 是否配置 | 混合媒体库 | 支持 `[tmdb-movie=123]` / `[tmdb-tv=123]`；无类型 `tmdbid=123` 会先用本地集数/季目录/年份/NFO 推断 movie/tv，不明确时 fallback 到 Bangumi → TMDB 标题搜索 |

## Jellyfin 兼容 API

MediaTree 实现 Jellyfin Server 兼容 API 层，第三方客户端可直接添加为 Jellyfin 服务器：

| 客户端 | 添加方式 |
|--------|---------|
| VidHub | 添加服务器 → Jellyfin → 地址 `http://IP:27580` |
| Infuse | 添加媒体服务器 → Jellyfin → 地址 `http://IP:27580` |
| VLC / IINA / mpv | `mpv "http://IP:27580/Videos/{id}/stream.mkv?api_key=TOKEN"` |
| Kodi | Jellyfin 插件 → 地址 `http://IP:27580` |

**特点：**
- 服务端不转码，DirectPlay 原始文件（EAC3/DTS/TrueHD 由客户端解码）
- 播放进度自动回传保存（/Sessions/Playing/Progress）
- 电视剧自动按 Series → Season → Episode 分组
- 支持外挂字幕流（ASS/SRT/VTT）

## 设置页功能

- **全局刮削器设置**：TMDB API Key/Token、缓存时间
- **媒体库配置**：每库选择刮削器（默认自动）+ 密码 + 重新扫描（带进度条+实时日志）
- **数据备份恢复**：下载数据库（core）/ 完整备份（含封面），上传恢复

## 字幕字体

- 前端内置 OpenList-style 固定 CJK fallback：`/fonts/SourceHanSansCN-Bold.woff2`。ASS/SSA 初始化时会立即把它传给 `@jellyfin/libass-wasm` 的 `fallbackFont`，避免 libass 落到自带 Latin-only `default.woff2` 后出现方块字。
- Docker 镜像安装 `fonts-noto-cjk`、`fonts-noto-color-emoji`、`fonts-wqy-microhei` 并执行 `fc-cache`。
- `/api/subtitle-fonts` 会同时列出用户上传字体和系统 CJK 字体，`/api/subtitle-fonts/default` 返回容器内首选 CJK 系统字体。
- ASS/SSA 字幕使用 libass canvas；找不到字幕指定字体时会把 Noto/Source Han/WenQuanYi/PingFang/YaHei/SimSun/SimHei/宋体/黑体/微软雅黑等常见 ASS 字体名映射到 CJK fallback。
- VTT/SRT 字幕使用 ArtPlayer 原生字幕层，并通过 CSS 设置 CJK 字体族。

## 动画 / 番剧命名兼容

扫描阶段会保留原有 JAV 番号、NFO、本地封面和刮削逻辑，同时为常见动画发布组命名补充结构化字段：

| 文件名 | 清洗标题 | 集数 | 显示标题 |
|---|---|---:|---|
| `[ANi] 葬送的芙莉莲 [01][1080P][Baha][WEB-DL][AAC AVC].mkv` | 葬送的芙莉莲 | 1 | 葬送的芙莉莲 - EP01 |
| `[NC-Raws] 孤独摇滚 [1080p][HEVC][AAC].mkv` | 孤独摇滚 | — | 孤独摇滚 |
| `[VCB-Studio] Senpai wa Otokonoko [12][Ma10p_1080p][x265_flac].mkv` | Senpai wa Otokonoko | 12 | Senpai wa Otokonoko - EP12 |

- 外挂字幕优先匹配完全同 basename，支持 `.zh/.chs/.cht/.sc/.tc/.zh-cn/.zh-tw/.ja/.jp/.en + .ass/.ssa/.srt/.vtt`。
- 外挂音轨记录到 `/api/media-info/{id}` 的 `external_audio_tracks`，支持 `.mka/.aac/.flac/.opus/.ac3/.eac3/.dts` 和 `.zh/.ja/.en/.jpn/.eng/.chs/.cht` 语言后缀。
- 多集目录按 `tmdb_episode` 或本地 `episode_number` 数字升序排列，避免 `[12]` 排在 `[05]` 前。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `MEDIA_ROOT` | `/media` | 媒体根目录 |
| `AUTH_USER` | — | 登录账号 |
| `AUTH_PASS` | — | 登录密码 |
| `SCAN_ON_STARTUP` | `true` | 启动扫描 |

## 许可证

MIT
