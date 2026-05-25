<p align="center">
  <img src="https://raw.githubusercontent.com/ZASENJC/mediatree/main/frontend/public/icon.svg" alt="MediaTree" width="80" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</p>

<p align="center">
  <em>一键部署的个人媒体库。<br>质感 UI，多源元数据刮削，ASS 特效字幕渲染，<br>电影、电视剧、动漫与 JAV — 一站管理。</em>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG_zh-CN.md"><img src="https://img.shields.io/badge/版本-1.0.02-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
</p>

---

## 界面预览

![首页](https://img.qunq.de/file/1779640696711_home_no_text.png)
*首页 — 卡片瀑布流媒体库*

![浏览](https://img.qunq.de/file/1779640700855_browser.png)
*浏览页 — 文件夹树导航与季集切换*

![播放器](https://img.qunq.de/file/1779640693184_movie.png)
*播放页 — 流媒体播放 + 完整影片信息*

![设置页](https://img.qunq.de/file/1779640699625_settings.png)
*设置 — 刮削器配置、媒体库管理、备份与自更新*

---

## 特性

### 媒体库

- 多库支持，每个库独立刮削器配置和访问密码
- 递归扫描 + 文件监控自动增量更新
- 文件夹树浏览器，支持季集标签切换
- 源文件名 / 刮削标题 显示切换
- 收藏、分类和排除文件夹

### 刮削器

- **TMDB** — 电影和电视剧元数据（演员、制作人、剧照、评论、关键词）
- **Bangumi** — 中/日文动漫元数据
- **Javdatabase** — JAV 番号元数据，支持模糊搜索回退
- 插件架构 + 可配置智能回退链
- 手动刮削，支持搜索选择和确认
- 右键菜单批量文件夹刮削
- 刮削缓存，可配置 TTL（24h–168h）

### 视频播放器

- ArtPlayer 5 定制 YouTube 风格控件
- 直链播放 + HTTP Range 字节跳转
- 按需 ffmpeg H.264 转码
- 触摸手势 — 轻触、双击、滑动移动端控制
- 键盘快捷键 — Space/K、方向键、F、M
- VR/360° 视频（Three.js 等距矩形渲染）
- 画中画 + 外部播放器（IINA、mpv、VLC）

### 字幕系统

- ASS/SSA 渲染（@jellyfin/libass-wasm，完整特效、字体、定位）
- 外挂字幕自动匹配（文件名 + 语言后缀 + 集数）
- CJK 回退字体（思源黑体 CN Bold），适配动漫字幕
- SRT → WebVTT 原生转换（纯 Python，无 ffmpeg 依赖）
- 编码自动检测（16 种编码 + charset-normalizer）
- 用户字体上传和管理

### Jellyfin 兼容

36 个 Jellyfin 兼容 API 端点 — 可直接接入 **VidHub**、**Infuse**、**Kodi**、**VLC**、**IINA** 和 **mpv**。支持 Series → Season → Episode 文件夹层级、多客户端认证（MediaBrowser Token、X-Emby-Token、Bearer、api_key）、Emby 路径兼容和播放进度跟踪。

### UI 设计

玻璃态 + Apple 风格设计语言，定制 TailwindCSS 调色板。Liquid Glass 顶栏色散光晕、极光渐变背景、剧院模式环境光效、图片灯箱手势导航和响应式移动端布局。

### 设置

控制中心 — 逐库配置刮削器与访问密码、调整缓存 TTL（24h–168h）、绑定 TMDB API 密钥、一键备份还原数据库，以及轻量应用包更新与更新日志查看。

---

## 快速开始

```bash
git clone https://github.com/ZASENJC/mediatree.git && cd mediatree
cp .env.example .env
# 编辑 .env — 设置 AUTH_USER、AUTH_PASS 和 MEDIA_VOLUMES
docker compose up -d
open http://localhost:27580
```

> **Docker Hub**: `docker pull zasenjc/mediatree:latest`

---

## 配置

**`AUTH_USER`** — 管理员用户名（设置后启用认证）

**`AUTH_PASS`** — 管理员密码

**`MEDIA_VOLUMES`** — 媒体目录：`/主机路径:/容器挂载点:ro`

**`DATA_DIR`** — 持久化数据（数据库、封面、字体）— 默认 `./data`

**`HOST_PORT`** — 主机端口映射 — 默认 `27580`

**`SCAN_ON_STARTUP`** — 容器启动时自动扫描 — 默认 `true`

**`TMDB_API_KEY`** — TMDB v3 API 密钥（可选）

**`TMDB_ACCESS_TOKEN`** — TMDB v4 访问令牌（可选）

**`JAVDB_ENABLED`** — 启用 JavDatabase 刮削器 — 默认 `true`

完整配置项参见 `.env.example`。

---

## 技术栈

**后端** — Python 3.12 · FastAPI · Uvicorn · httpx · aiosqlite · Pydantic v2 · ffmpeg

**前端** — React 18 · TypeScript 5 · TailwindCSS 3 · Vite · ArtPlayer 5 · Three.js

**字幕** — @jellyfin/libass-wasm · fonttools · charset-normalizer

**数据库** — SQLite（WAL 模式，aiosqlite）

**部署** — Docker 多阶段构建（node:20-alpine + python:3.12-slim）

**平台支持** — linux/amd64 · linux/arm64

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
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | 版本历史和发布说明（英文） |
| [CHANGELOG_zh-CN.md](CHANGELOG_zh-CN.md) | 版本历史（中文） |
| [CLAUDE.md](CLAUDE.md) | AI 辅助开发指南 |
| [Wiki](https://github.com/ZASENJC/mediatree/wiki) | 完整文档和指南 |

---

## 许可证

MIT © [ZASENJC](https://github.com/ZASENJC)
