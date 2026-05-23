[English](../wiki/Jellyfin-Clients) | [简体中文](Jellyfin-Clients)

# Jellyfin 客户端

MediaTree 实现了 36 个 Jellyfin 兼容 API 端点，可直接使用你常用的媒体客户端访问。

## 支持的客户端

| 客户端 | 平台 | 状态 |
|--------|----------|--------|
| **VidHub** | iOS、macOS、Apple TV | ✓ 已测试 |
| **Infuse** | iOS、macOS、Apple TV | ✓ 已测试 |
| **Kodi** | 全平台 | ✓ 通过 Jellyfin 插件 |
| **VLC** | 全平台 | ✓ 通过 UPnP/网络 |
| **IINA** | macOS | ✓ 通过 M3U 播放列表 |
| **mpv** | 全平台 | ✓ 通过 M3U 播放列表 |

## 连接设置

### VidHub / Infuse

1. 打开应用 → 添加服务器
2. 服务器类型选择 "Jellyfin"
3. 服务器地址：`http://你的服务器IP:27580`
4. 用户名：`.env` 中设置的 `AUTH_USER`
5. 密码：`.env` 中设置的 `AUTH_PASS`

### Kodi（Jellyfin 插件）

1. 安装 [Jellyfin for Kodi](https://github.com/jellyfin/jellyfin-kodi) 插件
2. 服务器主机：`你的服务器IP`
3. 端口：`27580`
4. 使用 HTTP（除非配置了反向代理则使用 HTTPS）

### VLC / IINA / mpv

使用 MediaTree 网页播放器中的「外部播放器」按钮，或直接访问 M3U 播放列表：

```
# 含字幕
http://你的服务器:27580/api/external-play/{movie_id}.m3u
```

## API 兼容性

### 支持的端点

- **系统**：`/System/Info`、`/System/Info/Public`
- **认证**：`/Users/AuthenticateByName`
- **浏览**：`/Items`、`/Items/{id}`、`/Shows/{id}/Seasons`
- **流媒体**：`/Videos/{id}/stream`（直链播放）
- **会话**：`/Sessions/Playing`、`/Sessions/Playing/Progress`

### 认证方式

- `MediaBrowser Token` — 标准 Jellyfin 令牌认证
- `X-Emby-Token` — Emby 兼容请求头
- `Authorization: Bearer` — OAuth 风格的 Bearer 令牌
- `api_key` 查询参数

### Emby 兼容性

所有 `/emby/*` 路径通过 `EmbyPathRewriteMiddleware` 自动重写为 Jellyfin 对应的路径。无需额外配置。

## 层级映射

MediaTree 将你的文件夹结构映射为 Jellyfin 的 Series → Season → Episode 层级：

```
/media/shows/
├── 我的节目/                    ← 系列
│   ├── S01/                    ← 第 1 季
│   │   ├── E01.mkv            ← 第 1 集
│   │   └── E02.mkv            ← 第 2 集
│   └── S02/                    ← 第 2 季
│       └── E01.mkv            ← 第 1 集
└── 电影合集/                    ← 电影合集
    └── 电影.mkv               ← 单独电影
```

## 已知限制

- **转码**：MediaTree 默认直链播放。客户端必须原生支持视频编码格式。
- **LiveTV**：不支持
- **合集**：仅基于文件夹，不支持 Jellyfin Collection 功能
- **用户**：仅支持单用户（管理员账号）

## 性能提示

- 将媒体卷以 `:ro`（只读）模式挂载以获得最佳 Docker 性能
- 使用原生支持 HEVC/AV1 编码的现代客户端（避免转码）
- 媒体库较大时，考虑在 `.env` 中增加 `SCRAPE_CONCURRENCY_PER_LIBRARY`
