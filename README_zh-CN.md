<p align="center">
  <img src="docs/assets/logo.png" alt="MediaTree" width="112" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <strong>把本地视频文件夹变成一个好看、好刮削、好播放的私人媒体库。</strong><br>
  支持电影、番剧及JAV。
</p>

<p align="center">
  <strong>简体中文</strong> · <a href="README_en.md">English</a> · <a href="#快速部署">快速部署</a> · <a href="https://github.com/ZASENJC/mediatree/wiki">Wiki</a> · <a href="CHANGELOG_zh-CN.md">更新日志</a>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG_zh-CN.md"><img src="https://img.shields.io/badge/版本-1.0.07-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
  <a href="https://github.com/ZASENJC/mediatree-app"><img src="https://img.shields.io/badge/android-app-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android App"></a>
</p>

MediaTree 面向把电影、电视剧、动漫和私人片库保存在自己硬盘上的用户。你只需要把媒体目录挂进去，它会扫描文件、补全海报和信息，并提供浏览器播放与 Jellyfin 兼容客户端访问能力，不需要搭一套复杂的媒体服务器。

## 为什么用 MediaTree

- **文件还在原处**：用只读挂载接入现有目录，不改变你的文件结构。
- **少做手工整理**：从 TMDB、Bangumi、Javdatabase 获取海报、标题、演员、季集和详情。
- **播放器够用**：支持直链播放、HTTP Range 跳转、按需转码、ASS/SSA 特效字幕、画中画和 IINA/mpv/VLC 外部播放。
- **打开就能管理**：按媒体库、文件夹树、收藏、分类和季集浏览；支持启动扫描和文件变动自动更新。
- **不只 Web 能用**：提供 Jellyfin 兼容 API，可接入 VidHub、Infuse、Kodi、VLC、IINA 和 mpv。
- **部署简单**：Docker Compose、SQLite、持久化 `./data`，支持 linux/amd64 和 linux/arm64。

需要移动端体验时，可以配合独立 Android 客户端 [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app) 使用；它支持 MediaTree、Jellyfin、Emby、SMB 和 WebDAV，本项目仍作为可独立部署的服务端。

## 界面预览

| 媒体库 | 播放器 |
|---|---|
| ![首页](https://img.qunq.de/file/1779640696711_home_no_text.png) | ![播放器](https://img.qunq.de/file/1779640693184_movie.png) |
| 扫描后的海报墙 | 播放、详情和字幕 |

| 浏览 | 设置 |
|---|---|
| ![浏览](https://img.qunq.de/file/1779640700855_browser.png) | ![设置页](https://img.qunq.de/file/1779640699625_settings.png) |
| 文件夹树和季集导航 | 媒体库、刮削器、备份和更新 |

## 快速部署

克隆项目，复制示例配置，挂载至少一个媒体目录，然后启动容器：

```bash
git clone https://github.com/ZASENJC/mediatree.git && cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml

# 先编辑 .env：
# AUTH_USER=admin
# AUTH_PASS=change-me
# MEDIA_VOLUMES=/path/to/movies:/media/movies:ro

docker compose up -d
```

打开 `http://localhost:27580`，登录后扫描媒体库即可使用。

Docker Hub 镜像：`zasenjc/mediatree:latest`

## 常用配置

| 变量 | 作用 |
|---|---|
| `AUTH_USER` / `AUTH_PASS` | 启用管理员登录 |
| `MEDIA_VOLUMES` | 挂载媒体目录，例如 `/host/movies:/media/movies:ro` |
| `DATA_DIR` | 保存数据库、封面、字体、备份和应用包更新。默认 `./data` |
| `HOST_PORT` | Web 访问端口。默认 `27580` |
| `TMDB_API_KEY` / `TMDB_ACCESS_TOKEN` | 可选，用于改善 TMDB 刮削 |
| `JAVDB_ENABLED` | 启用或关闭 Javdatabase 刮削 |

完整配置见 [.env.example](.env.example)。高级配置、刮削逻辑、客户端兼容和排障说明放在 [Wiki](https://github.com/ZASENJC/mediatree/wiki)。

## 更新

日常版本可以在设置页安装小型应用包，更新内容会进入 `./data`。只有 Python、系统包、ffmpeg、字体或启动流程等基础运行层变化时，才需要完整镜像更新。

完整镜像更新：

```bash
docker compose pull
docker compose up -d
```

## 文档

| 文档 | 说明 |
|---|---|
| [Wiki](https://github.com/ZASENJC/mediatree/wiki) | 完整使用指南、高级配置、刮削说明和排障 |
| [README_en.md](README_en.md) | English README |
| [CHANGELOG_zh-CN.md](CHANGELOG_zh-CN.md) | 中文版本历史 |
| [CHANGELOG.md](CHANGELOG.md) | 英文版本历史 |
| [CLAUDE.md](CLAUDE.md) | 开发和 AI 辅助维护说明 |

## 许可证

MIT © [ZASENJC](https://github.com/ZASENJC)
