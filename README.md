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
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG_zh-CN.md"><img src="https://img.shields.io/badge/版本-1.0.12-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/windows-desktop-0078D4?style=flat-square&logo=windows11&logoColor=white" alt="Windows Desktop">
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

需要桌面本地体验时，可以使用 Windows 桌面版：它通过 WinUI 3 原生客户端启动本机 FastAPI 后端，支持在软件内添加本地媒体文件夹、浏览媒体库，并用内置 libmpv 播放器观看。需要移动端体验时，可以配合独立 Android 客户端 [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app) 使用；它支持 MediaTree、Jellyfin、Emby、SMB 和 WebDAV，本项目仍作为可独立部署的服务端。

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

新建 `docker-compose.yml`，按注释改好账号、密码和媒体目录后启动：

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    restart: unless-stopped

    ports:
      # 左侧是宿主机访问端口，启动后打开 http://localhost:27580
      - "27580:80"

    volumes:
      # 持久化数据目录：数据库、封面、字体、备份和应用包更新都会保存在这里
      - ./data:/app/data

      # 挂载你的媒体目录，建议只读。左侧改成宿主机真实路径，右侧是容器内路径
      - /path/to/your/movies:/media/movies:ro
      # 可以继续添加更多媒体目录
      # - /path/to/your/anime:/media/anime:ro

      # 可选：允许设置页执行完整 Docker 镜像更新。
      # 这会让容器获得宿主机 Docker 控制权限；普通应用包更新不需要。
      # - /var/run/docker.sock:/var/run/docker.sock

    environment:
      # 预置管理员账号。也可以留空，首次打开网页时创建管理员账号
      - AUTH_USER=admin
      - AUTH_PASS=change-me

      # 容器内部服务端口，通常不需要改
      - PORT=80

      # 启动时自动扫描媒体库
      - SCAN_ON_STARTUP=true

      # 是否启用 Javdatabase 刮削
      - JAVDB_ENABLED=true

    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:80/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

启动：

```bash
docker compose up -d
```

打开 `http://localhost:27580`，登录后扫描媒体库即可使用。未预置 `AUTH_USER` / `AUTH_PASS` 时，首次打开会先要求创建管理员账号。

也可以从仓库 clone 示例配置：

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml

# 编辑 .env 和 docker-compose.yml 后启动
docker compose up -d
```

Docker Hub 镜像：`zasenjc/mediatree:latest`

## Windows 桌面版

Windows 桌面版面向 Windows 10 19041+ / Windows 11 x64。它不是外部浏览器启动器，而是一个 WinUI 3 原生客户端：应用会在后台启动本地 `mediatree-server.exe`，主界面使用 Windows 原生导航、媒体库网格、详情页和内置 libmpv 播放器。

桌面版数据默认保存在 `%APPDATA%\MediaTree\data`，日志保存在 `%LOCALAPPDATA%\MediaTree\logs`。日常 FastAPI / React 更新仍复用 GitHub Release 中的 `mediatree-app-<version>.tar.gz` 应用包；只有 Python 依赖、ffmpeg/libmpv、WinUI 原生客户端或 PyInstaller 基础运行时变化时，才需要下载新的 `MediaTree-Windows-<version>.msix` / `.appinstaller`。

维护者本地构建 Windows 版：

```powershell
pwsh packaging/windows/build-windows.ps1 -Configuration Release
```

## 常用配置

| 变量 | 作用 |
|---|---|
| `AUTH_USER` / `AUTH_PASS` | 预置管理员登录账号；留空时首次打开网页创建账号 |
| `MEDIA_VOLUMES` | 挂载媒体目录，例如 `/host/movies:/media/movies:ro` |
| `DATA_DIR` | 保存数据库、封面、字体、备份和应用包更新。默认 `./data` |
| `HOST_PORT` | Web 访问端口。默认 `27580` |
| `TMDB_API_KEY` / `TMDB_ACCESS_TOKEN` | 可选，用于改善 TMDB 刮削 |
| `JAVDB_ENABLED` | 启用或关闭 Javdatabase 刮削 |

完整配置见 [.env.example](.env.example)。高级配置、刮削逻辑、客户端兼容和排障说明放在 [Wiki](https://github.com/ZASENJC/mediatree/wiki)。

## 更新

大多数更新都可以直接在设置页完成，点一下就会下载小型应用包并安装到 `./data`，不需要重新拉 Docker 镜像。应用包更新成功并完成重启后，会自动保留当前版本和一个可回滚的上一版，并清理更旧的应用包。新安装的用户只要使用 `zasenjc/mediatree:latest`，也会直接拿到最新版本。

发布应用包更新时，维护者会在本地构建并推送 `zasenjc/mediatree:latest`，不再通过 GitHub Actions 同步 DockerHub。这样新安装用户仍会拿到最新应用基线，已安装用户则继续走设置页里的应用包更新。

Windows 桌面版也使用同一套应用包更新。发布时如果只改 FastAPI / React，`.github/release-metadata.json` 保持 `requires_windows_base_update: false`；如果改 Python 依赖、ffmpeg/libmpv、WinUI 原生客户端或 PyInstaller 打包，则把对应版本标记为 `requires_windows_base_update: true` 并发布新的 MSIX/.appinstaller。

少数更新会提示“需要完整镜像更新”，通常是因为运行环境也变了，例如 Python、ffmpeg、字体或启动流程。这时最简单的做法是在宿主机执行下面两条命令。如果想让设置页也能自动完成这类完整镜像更新，可以在 `docker-compose.yml` 里挂载 `/var/run/docker.sock:/var/run/docker.sock`；但这会让容器获得控制宿主机 Docker 的能力，不确定时建议不要挂载。

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

## 群组 / 频道

- Telegram 群组：[加入讨论](https://t.me/mediatree_group)
- Telegram 更新通知频道：[订阅更新](https://t.me/mediatreex)

## 许可证

MIT © [ZASENJC](https://github.com/ZASENJC)
