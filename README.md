<p align="center">
  <img src="docs/assets/logo.png" alt="MediaTree" width="112" />
</p>

<h1 align="center">MediaTree</h1>

<p align="center">
  <strong>把本地视频文件夹变成一个好看、好刮削、好播放的私人媒体库。</strong><br>
  支持电影、番剧及JAV。
</p>

<p align="center">
  <strong>简体中文</strong> · <a href="README_en.md">English</a> · <a href="#快速部署">快速部署</a> · <a href="https://zasenjc.github.io/mediatree/">文档站</a> · <a href="CHANGELOG_zh-CN.md">更新日志</a>
</p>

<p align="center">
  <a href="https://github.com/ZASENJC/mediatree/blob/main/CHANGELOG_zh-CN.md"><img src="https://img.shields.io/badge/版本-1.1.0-blue?style=flat-square" alt="Version"></a>
  <a href="https://github.com/ZASENJC/mediatree/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/react-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/docker-amd64|arm64-2496ED?style=flat-square&logo=docker" alt="Docker">
  <a href="https://github.com/ZASENJC/mediatree-app"><img src="https://img.shields.io/badge/android-app-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android App"></a>
</p>

MediaTree 面向把电影、电视剧、动漫和私人片库保存在自己硬盘上的用户。你只需要把媒体目录挂进去，它会扫描文件、补全海报和信息，并提供浏览器播放和外部播放器串流能力，不需要搭一套复杂的媒体服务器。

## 为什么用 MediaTree

- **文件还在原处**：用只读挂载接入现有目录，不改变你的文件结构。
- **少做手工整理**：从 TMDB、Bangumi、Javdatabase 获取海报、标题、演员、季集和详情。
- **花絮不打扰正片**：把非正片内容放进影片目录下的 `sp` 文件夹即可按花絮入库，默认隐藏，可在目录里单独显示。
- **播放器够用**：支持直链播放、HTTP Range 跳转、按需转码、AC3 自动转码、ASS/SSA 特效字幕、播放状态标签标题、画中画和 IINA/mpv/VLC 外部播放。
- **打开就能管理**：按媒体库、文件夹树、收藏、分类和季集浏览；支持启动扫描和文件变动自动更新，花絮不会混入继续观看。
- **不只 Web 能用**：网页播放器可生成外部播放链接和 M3U 播放列表，方便用 VLC、IINA 或 mpv 继续播放。
- **部署简单**：Docker Compose、SQLite、持久化 `./data`，支持 linux/amd64 和 linux/arm64。

需要移动端体验时，可以配合独立 Android 客户端 [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app) 使用；它可以连接 MediaTree，也可以作为独立客户端连接 Jellyfin、Emby、SMB 和 WebDAV。

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

新建 `.env` 和 `docker-compose.yml`，按注释改好数据目录和媒体目录后启动；管理员账号可以预置，也可以首次打开网页时创建：

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    restart: unless-stopped
    init: true
    stop_grace_period: 30s
    user: "${PUID:-1000}:${PGID:-1000}"
    security_opt:
      - no-new-privileges:true

    ports:
      # 左侧是宿主机访问端口，启动后打开 http://localhost:27580
      - "27580:80"

    volumes:
      # 持久化数据目录：数据库、封面、字体、备份和应用包更新都会保存在这里
      - ./data:/app/data

      # 媒体目录只读挂载；左侧改成宿主机真实路径，右侧是容器内路径
      - /path/to/your/media:/media/movies:ro
      # 需要多个媒体库时继续添加：
      # - /path/to/your/anime:/media/anime:ro

      # 可选：允许设置页执行完整 Docker 镜像更新。
      # 这会让容器获得宿主机 Docker 控制权限；普通应用包更新不需要。
      # - /var/run/docker.sock:/var/run/docker.sock

    env_file:
      - .env
    environment:
      # 容器内部服务端口，通常不需要改
      PORT: "80"

    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:80/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
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

默认镜像为了减小体积，只内置轻量中文字体 `fonts-wqy-microhei`，并使用前端随包的字幕兜底字体；不再默认包含完整 Noto CJK 和 emoji 字体。需要更完整的字幕字体覆盖时，可以在设置页上传字体；维护者只有在发布内容明确需要时才会用 `INCLUDE_FULL_CJK_FONTS=true` 或 `INCLUDE_EMOJI_FONT=true` 构建完整字体镜像。

## 常用配置

| 变量 | 作用 |
|---|---|
| `AUTH_USER` / `AUTH_PASS` | 预置管理员登录账号；留空时首次打开网页创建账号 |
| `PUID` / `PGID` | 容器运行用户 UID/GID；Linux/macOS 可用 `id -u` 和 `id -g` 查看 |
| 媒体目录挂载 | 在 `docker-compose.yml` 的 `volumes` 中配置，例如 `/host/movies:/media/movies:ro` |
| 数据目录挂载 | 在 `docker-compose.yml` 的 `volumes` 中配置，例如 `./data:/app/data` |
| 访问端口 | 在 `docker-compose.yml` 的 `ports` 中配置，例如 `27580:80` |
| `TMDB_ACCESS_TOKEN` | 可选，用于改善 TMDB 刮削；申请方式见[文档站](https://zasenjc.github.io/mediatree/guide/configuration#获取-tmdb-读取访问令牌) |

Javdatabase 现在作为内置刮削器插件提供；在设置页为对应媒体库选择 `Javdatabase` 即可使用。刮削器缓存有效期和 Javdatabase 请求间隔由应用内部管理，不再需要在设置页或环境变量里调整。手动扫描、重新刮削和手动应用结果会绕过缓存，空结果不会写入缓存，避免旧的空结果挡住后续补齐的数据。

完整配置见 [.env.example](.env.example)。高级配置、刮削逻辑、播放和排障说明放在 [文档站](https://zasenjc.github.io/mediatree/)。

## 更新

大多数更新都可以直接在设置页完成，点一下就会下载小型应用包并安装到 `./data`，不需要重新拉 Docker 镜像。应用包更新成功并完成重启后，会自动保留当前版本和一个可回滚的上一版，并清理更旧的应用包。新安装的用户只要使用 `zasenjc/mediatree:latest`，也会直接拿到最新版本。

发布应用包更新时，维护者会在本地构建并推送 `zasenjc/mediatree:latest`，不再通过 GitHub Actions 同步 DockerHub。这样新安装用户仍会拿到最新应用基线，已安装用户则继续走设置页里的应用包更新。

少数更新会提示“需要完整镜像更新”，通常是因为运行环境也变了，例如 Python、ffmpeg、字体或启动流程。这时最简单的做法是在宿主机执行下面两条命令。如果想让设置页也能自动完成这类完整镜像更新，需要挂载 `/var/run/docker.sock:/var/run/docker.sock`，并使用包含 Docker CLI 的镜像；但这会让容器获得控制宿主机 Docker 的能力，不确定时建议不要挂载。

完整镜像更新：

```bash
docker compose pull
docker compose up -d
```

## 文档

| 文档 | 说明 |
|---|---|
| [文档站](https://zasenjc.github.io/mediatree/) | 推荐入口，包含部署、配置、刮削、升级、API 和开发文档 |
| [README_en.md](README_en.md) | English README |
| [CHANGELOG_zh-CN.md](CHANGELOG_zh-CN.md) | 中文版本历史 |
| [CHANGELOG.md](CHANGELOG.md) | 英文版本历史 |
| [CLAUDE.md](CLAUDE.md) | 开发和 AI 辅助维护说明 |

## 群组 / 频道

- Telegram 群组：[加入讨论](https://t.me/mediatree_group)
- Telegram 更新通知频道：[订阅更新](https://t.me/mediatreex)

## 许可证

MIT © [ZASENJC](https://github.com/ZASENJC)
