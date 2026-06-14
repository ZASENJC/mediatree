# 安装指南

## 环境要求

- 已安装 Docker 和 Docker Compose。
- 已准备包含视频、字幕或封面的媒体目录。
- 至少 1GB 可用磁盘空间，用于数据库、封面缓存、字体和应用包更新。

## 快速开始

### 1. 准备配置

可以直接使用预构建镜像，也可以 clone 仓库后复制示例配置：

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
```

编辑 `.env` 和 `docker-compose.yml`，至少设置管理员账号、数据目录和媒体目录挂载。

### 2. 最小 docker-compose.yml

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    restart: unless-stopped
    ports:
      - "27580:80"
    volumes:
      - ./data:/app/data
      - /path/to/your/movies:/media/movies:ro
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=change-me
      - PORT=80
      - SCAN_ON_STARTUP=true
      - JAVDB_ENABLED=true
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:80/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

媒体目录建议以只读方式挂载，例如 `/host/movies:/media/movies:ro`。MediaTree 会读取文件并把数据库、封面、配置、字体、备份和应用包更新写入 `./data`。

### 3. 启动

```bash
docker compose up -d
```

打开 `http://localhost:27580`。如果没有预置 `AUTH_USER` / `AUTH_PASS`，首次打开会进入管理员账号创建流程。

## 支持平台

- `linux/amd64`
- `linux/arm64`

## 常见启动问题

### 数据目录权限

容器以非 root 用户运行。若 `./data` 无法写入，可以在宿主机调整权限：

```bash
mkdir -p ./data
sudo chown -R 1000:1000 ./data
chmod 755 ./data
```

### 端口冲突

如果 `27580` 已被占用，修改端口映射左侧：

```yaml
ports:
  - "3000:80"
```

然后通过 `http://localhost:3000` 访问。

### 中文字幕字体

默认 Docker 镜像内置 WenQuanYi Micro Hei，并随前端提供 Source Han Sans 兜底字体以降低镜像体积。需要更完整的 Noto CJK 或 emoji 字体时，可在自定义构建中设置 `INCLUDE_FULL_CJK_FONTS=true` 或 `INCLUDE_EMOJI_FONT=true`；也可以在设置页上传字幕字体。
