# MediaTree

本地影片 Web 浏览管理器。支持电影/动画/番剧刮削、Jellyfin 结构兼容、集数匹配、字幕、多媒体库密码保护、文件监控自动扫描。

## 特性

- **插件化刮削** — TMDB（电影/电视剧/集数匹配）、Bangumi（动画）、Javdatabase（JAV）
- **Jellyfin 兼容** — 识别 NFO 元数据、递归封面查找、本地数据优先
- **Fallback 链** — 刮削器互备（tmdb↔bangumi），javdb 独立运行
- **集数匹配** — TMDB TV 季节/集数自动识别，集剧照本地压缩缓存
- **季度选项卡** — Folder 页自动检测 S01/S02 等子目录
- **右键菜单** — 首页文件夹/Folder 页影片右键操作：重新/手动刮削、换封面/背景、编辑、删除
- **文件监控** — watchfiles 自动检测媒体库文件增减，15 秒防抖自动扫描
- **首次引导** — 首次打开自动弹出 SetupWizard，逐库配置刮削源
- **多媒体库** — 多个库挂载于 `/media/` 下，独立配置
- **库密码** — 为敏感媒体库设置独立密码
- **字幕支持** — 内嵌字幕检测 + 外挂字幕识别 + WebVTT 实时转换
- **封面压缩** — 在线封面/剧照本地缓存（JPEG 500px/300px），节省带宽
- **备份恢复** — 核心数据库/完整（含封面）备份下载 + 上传恢复
- **搜索 / 排序 / 收藏 / 灯箱 / 认证**

## 快速开始

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
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
| TMDB | 是 ([免费申请](https://www.themoviedb.org/settings/api)) | 电影/电视剧/集数 | 支持 API Key + Bearer Token 双认证 |
| Bangumi | 否 | 动画/番剧 | 仅搜索动画 (type=2) |
| Javdatabase | 否 | JAV 番号 | 独立运行，不参与 fallback |

## 设置页功能

- **全局刮削器设置**：TMDB API Key/Token、缓存时间
- **媒体库配置**：每库选择刮削器 + 密码 + 重新扫描（带进度条+实时日志）
- **数据备份恢复**：下载数据库（core）/ 完整备份（含封面），上传恢复

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `MEDIA_ROOT` | `/media` | 媒体根目录 |
| `AUTH_USER` | — | 登录账号 |
| `AUTH_PASS` | — | 登录密码 |
| `SCAN_ON_STARTUP` | `true` | 启动扫描 |

## 许可证

MIT
