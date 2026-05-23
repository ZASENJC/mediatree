[English](../wiki/Installation) | [简体中文](Installation)

# 安装指南

## 环境要求

- 已安装 Docker 和 Docker Compose
- 包含媒体文件（视频、字幕、封面）的目录
- 至少 1GB 可用磁盘空间（用于数据库和封面缓存）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```env
# 必填 — 设置你的凭据
AUTH_USER=你的用户名
AUTH_PASS=你的安全密码

# 媒体目录（格式：/主机路径:/容器挂载点:ro）
MEDIA_VOLUMES=/home/user/media/movies:/media/movies:ro \
             /home/user/media/shows:/media/shows:ro

# 可选 — TMDB API 获取更丰富的元数据
TMDB_ACCESS_TOKEN=你的_tmdb_读取访问令牌
```

### 3. 启动容器

```bash
docker compose up -d
```

### 4. 打开浏览器

访问 `http://localhost:27580`，跟随设置向导完成配置。

## Docker Hub

也可以直接拉取预构建镜像：

```bash
docker pull zasenjc/mediatree:latest
```

完整的部署示例参见 [docker-compose.yml 模板](https://github.com/ZASENJC/mediatree/blob/main/docker-compose.yml)。

## 卷挂载说明

| 挂载 | 模式 | 用途 |
|-------|------|---------|
| `/主机路径:/media/名称` | `:ro` | 媒体文件（只读）|
| `./data:/app/data` | `:rw` | 持久化数据（数据库、封面、配置、字体）|

## 支持的平台

- `linux/amd64` — Intel/AMD x86_64
- `linux/arm64` — Apple Silicon、树莓派 4/5、ARM 服务器

## 升级

```bash
# 拉取最新镜像并重启
docker compose pull
docker compose up -d --force-recreate

# 或从源码重新构建
docker compose build --no-cache
docker compose up -d
```

## 常见问题

### 权限问题
容器以非 root 用户（uid 1000）运行。确保数据目录可写：
```bash
chmod 755 ./data
```

### 端口冲突
如果端口 27580 已被占用，在 `.env` 中修改 `HOST_PORT`：
```env
HOST_PORT=3000
```

### Docker 中文字幕字体
系统 CJK 字体（Noto CJK、WenQuanYi Micro Hei）已自动安装。可通过 设置 → 字幕字体 上传自定义字体。
