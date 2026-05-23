<p align="center">
  <img src="https://raw.githubusercontent.com/ZASENJC/mediatree/main/frontend/public/icon.svg" alt="MediaTree" width="80" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong>
  <br><br>
  <strong>自托管的媒体库管理器，拥有优雅的玻璃态 UI、<br>Jellyfin 兼容 API 和强大的插件化刮削系统。</strong>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/版本-1.0.0-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
</p>

---

## 特性

<table>
<tr>
<td width="50%">

### 媒体库
- 多库支持，每个库独立刮削器配置和访问密码
- 递归扫描 + 文件监控自动增量更新
- 文件夹树浏览器，支持季集标签切换
- 源文件名 / 刮削标题 显示切换
- 收藏、分类和排除文件夹

### 刮削器
- **TMDB** — 电影和电视剧元数据（演员、剧照、评论等）
- **Bangumi** — 中/日文动漫元数据
- **Javdatabase** — JAV 番号元数据
- 插件架构 + 智能回退链
- 手动刮削，支持搜索选择和确认

</td>
<td width="50%">

### 视频播放器
- ArtPlayer 5 定制 YouTube 风格界面
- 直链播放 + HTTP Range 字节跳转
- 按需 ffmpeg H.264 转码
- 触摸手势和键盘快捷键
- VR/360° 视频（Three.js）
- 画中画 + 外部播放器（IINA/mpv）

### 字幕系统
- ASS/SSA 渲染（libass-wasm，完整特效）
- 外挂字幕自动匹配（文件名 + 语言后缀）
- CJK 回退字体（思源黑体 CN）
- SRT → WebVTT 原生转换
- 用户字体上传和管理

</td>
</tr>
</table>

### Jellyfin 兼容

36 个 Jellyfin API 端点 — 可直接接入 **VidHub**、**Infuse**、**Kodi**、**VLC**、**IINA** 和 **mpv**。支持文件夹结构的 Series/Season/Episode 层级、多客户端认证（MediaBrowser Token、X-Emby-Token、Bearer）、Emby 路径兼容和播放进度跟踪。

### UI 设计

玻璃态 + Apple 风格设计，定制 TailwindCSS 调色板。Liquid Glass 顶栏、极光渐变背景、剧院模式环境光效、图片灯箱和响应式移动端布局。

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/ZASENJC/mediatree.git && cd mediatree

# 配置环境
cp .env.example .env
# 编辑 .env — 设置 AUTH_USER、AUTH_PASS 和 MEDIA_VOLUMES

# 启动容器
docker compose up -d

# 打开浏览器
open http://localhost:27580
```

> **Docker Hub**: `docker pull zasenjc/mediatree:latest`

---

## 配置

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `AUTH_USER` | — | 管理员用户名（设置后启用认证） |
| `AUTH_PASS` | — | 管理员密码 |
| `MEDIA_VOLUMES` | — | 媒体目录：`/主机路径:/容器挂载点:ro` |
| `DATA_DIR` | `./data` | 持久化数据（数据库、封面、字体） |
| `HOST_PORT` | `27580` | 主机端口映射 |
| `SCAN_ON_STARTUP` | `true` | 容器启动时自动扫描 |
| `JAVDB_ENABLED` | `true` | 启用 JavDatabase 刮削器 |
| `TMDB_API_KEY` | — | TMDB v3 API 密钥（可选）|
| `TMDB_ACCESS_TOKEN` | — | TMDB v4 访问令牌（可选）|

完整配置项参见 `.env.example`。

---

## 技术栈

| 层级 | 技术 |
|-------|-----------|
| **后端** | Python 3.12 · FastAPI · Uvicorn · httpx · aiosqlite · Pydantic v2 · ffmpeg |
| **前端** | React 18 · TypeScript 5 · TailwindCSS 3 · Vite · ArtPlayer 5 · Three.js |
| **字幕** | @jellyfin/libass-wasm · fonttools · charset-normalizer |
| **数据库** | SQLite（WAL 模式 · aiosqlite）|
| **部署** | Docker 多阶段构建（node:20-alpine + python:3.12-slim）|
| **平台** | linux/amd64 · linux/arm64 |

---

## 本地开发

```bash
# 后端（端口 80）
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# 前端（端口 5173，反向代理 /api -> localhost:80）
cd frontend && npm install && npm run dev

# 测试
cd backend && python -m unittest discover -s tests -p 'test_*.py'
```

---

## 文档

| 文档 | 说明 |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | 版本历史和发布说明 |
| [CHANGELOG_zh-CN.md](CHANGELOG_zh-CN.md) | 版本历史（中文）|
| [Wiki](https://github.com/ZASENJC/mediatree/wiki) | 完整文档和指南 |

---

## 许可证

MIT © [ZASENJC](https://github.com/ZASENJC)
