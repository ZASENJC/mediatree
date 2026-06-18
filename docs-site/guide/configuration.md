# 配置说明

MediaTree 使用环境变量和运行时设置共同配置。环境变量适合部署级配置，设置页适合媒体库、刮削器和界面偏好。

## 认证设置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AUTH_USER` | `""` | 管理员用户名。留空时首次打开网页创建管理员账号。 |
| `AUTH_PASS` | `""` | 管理员密码。启用认证时请使用强密码。 |

认证密钥只从环境变量读取，不会写入 `data/config.json`。

## 媒体和数据

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MEDIA_ROOT` | `/media` | 容器内媒体根目录。 |
| `DATA_DIR` | `../data` | 持久化数据目录。 |
| `SCAN_ON_STARTUP` | `true` | 容器启动时执行扫描。 |
| `FILE_WATCHER_ENABLED` | `true` | 启用文件系统监控和自动扫描。 |

多媒体库建议在 `docker-compose.yml` 中挂载多个目录到 `/media/*`，再在设置页为不同媒体库配置刮削器和密码。

## 刮削器配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TMDB_ACCESS_TOKEN` | `""` | TMDB v4 读取访问令牌，推荐使用。 |
| `SCRAPE_CONCURRENCY_PER_LIBRARY` | `8` | 每个库最大并发刮削数。 |
| `SCRAPE_GLOBAL_CONCURRENCY` | `16` | 全局最大并发刮削数。 |
| `SCRAPER_API_CONCURRENCY` | `8` | 最大并发 API 请求数。 |
| `SCRAPER_HTTP_TIMEOUT` | `10.0` | 外部 HTTP 请求超时秒数。 |

Javdatabase 作为内置刮削器插件提供；在设置页为对应媒体库选择 `Javdatabase` 即可使用。缓存有效期和 Javdatabase 请求间隔是内部策略，不再作为设置项暴露。手动扫描、重新刮削和手动应用结果会绕过缓存。

## 运行时设置

以下内容通过设置页管理，并持久化到 `data/config.json`：

- 媒体库配置：路径、刮削器、密码。
- TMDB 读访问令牌。
- 界面偏好：隐藏首页标题、环境光模式、显示源文件名等。
- 备份、恢复、更新和字幕字体。

## 获取 TMDB 读取访问令牌

1. 注册或登录 [TMDB](https://www.themoviedb.org/)。
2. 打开 [API 设置](https://www.themoviedb.org/settings/api)。
3. 生成 v4 Read Access Token。
4. 在 `.env` 填入 `TMDB_ACCESS_TOKEN`，或在设置页的“刮削器”里填入 `TMDB 读访问令牌`。

没有 TMDB 凭据时，MediaTree 仍可扫描和播放文件，但电影、电视剧元数据和图片会减少。
