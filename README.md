# MediaTree

基于 Docker 的本地影片 Web 浏览管理器。支持多媒体库、插件化刮削、ArtPlayer 播放器、ASS/SSA 特效字幕渲染。

## 功能

- **多媒体库管理**：多目录分类，每库独立刮削配置和访问密码
- **插件化刮削**：TMDB（电影/电视剧）、Bangumi（动画）、Javdatabase（JAV 番号）
- **ArtPlayer 播放器**：触控手势、键盘快捷键、移动端全屏适配、画中画
- **ASS/SSA 特效字幕**：libass-wasm 渲染，CJK 字体回退，外挂字幕自动匹配
- **Jellyfin 兼容**：30+ Jellyfin API 端点，VidHub/Infuse/Kodi 直接连接
- **文件监控**：watchfiles 自动增量扫描新增/删除文件
- **右键菜单**：文件夹批量操作、手动刮削、封面/背景更换

## 快速开始

```bash
# 克隆项目
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree

# 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 设置 MEDIA_ROOT=/your/media/path

# 启动
docker compose up -d

# 访问 http://localhost:27580
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `MEDIA_ROOT` | `/media` | 媒体根目录 |
| `SCAN_ON_STARTUP` | `true` | 启动时自动扫描 |
| `AUTH_USER` | — | 登录账号 |
| `AUTH_PASS` | — | 登录密码 |

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn |
| 前端 | React 18 + TypeScript 5 + TailwindCSS 3 + Vite |
| 播放器 | ArtPlayer 5 + @jellyfin/libass-wasm |
| 数据库 | SQLite (aiosqlite, WAL mode) |
| 部署 | Docker multi-stage (amd64/arm64) |
| 刮削源 | TMDB / Bangumi / Javdatabase |

## 文档

- [AGENTS.md](AGENTS.md) — 项目开发指南
- [CHANGEME.md](CHANGEME.md) — 版本更新记录
- [CLAUDE.md](CLAUDE.md) — AI 辅助开发配置
