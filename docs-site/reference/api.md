# API Reference

MediaTree 的 API 主要服务于 Web 前端和外部播放链接。除少量健康检查、登录和首次设置端点外，`/api/*` 默认需要应用认证。

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/auth/login` | 登录并获取会话 token。 |
| `POST` | `/api/auth/setup` | 首次创建管理员账号。 |
| `GET` | `/api/auth/status` | 查询认证和初始化状态。 |
| `POST` | `/api/auth/change-password` | 修改管理员密码。 |
| `POST` | `/api/media-token` | 获取短期媒体访问 token。 |

## 媒体库和扫描

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查。 |
| `GET` | `/api/scan` | 启动扫描。 |
| `GET` | `/api/scan/status` | 查询扫描状态。 |
| `GET` | `/api/scan/log` | 查询扫描日志。 |
| `GET` | `/api/media-roots` | 获取媒体根目录。 |
| `GET` | `/api/library-settings` | 获取媒体库设置。 |
| `POST` | `/api/library-settings` | 保存媒体库设置。 |
| `POST` | `/api/library/clear` | 清空媒体库数据。 |

## 浏览和详情

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/folders` | 获取文件夹树和文件夹级元数据。 |
| `GET` | `/api/movies` | 获取影片列表。 |
| `GET` | `/api/search` | 搜索影片。 |
| `GET` | `/api/favorites` | 获取收藏。 |
| `GET` | `/api/detail/{movie_id}` | 获取影片详情。 |
| `GET` | `/api/recent-watched` | 获取继续观看列表。 |
| `GET` | `/api/categories` | 获取分类。 |
| `POST` | `/api/categories` | 创建分类。 |
| `PUT` | `/api/categories/{cat_id}` | 更新分类。 |
| `DELETE` | `/api/categories/{cat_id}` | 删除分类。 |

## 播放、字幕和媒体文件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/stream/{movie_id}` | 视频流，支持 Range 和必要转码。 |
| `GET` | `/api/media-info/{movie_id}` | 获取媒体信息。 |
| `GET` | `/api/external-play/{movie_id}.m3u` | 生成外部播放器播放列表。 |
| `GET` | `/api/subtitle-tracks/{movie_id}` | 获取字幕轨道。 |
| `GET` | `/api/subtitle/{movie_id}/{track_index}` | 获取 Web 字幕。 |
| `GET` | `/api/subtitle-file/{movie_id}/{track_index}/{filename}` | 获取字幕文件。 |
| `GET` | `/api/media/{file_path}` | 读取媒体文件路径。 |

## 封面和图片

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/cover/{movie_id}` | 获取影片封面。 |
| `GET` | `/api/cached-cover/{cache_key}` | 获取缓存封面。 |
| `GET` | `/api/episode-still/{movie_id}` | 获取分集剧照。 |
| `GET` | `/api/thumbnail/{movie_id}/{index}` | 获取缩略图。 |
| `POST` | `/api/movies/{movie_id}/cover` | 修改影片封面。 |
| `POST` | `/api/folder/cover` | 修改文件夹封面。 |
| `POST` | `/api/folder/backdrop` | 修改文件夹背景图。 |

## 刮削和元数据

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/movies/{movie_id}/rescrape` | 重新刮削影片。 |
| `POST` | `/api/movies/{movie_id}/manual-scrape` | 手动应用影片刮削结果。 |
| `POST` | `/api/rescrape-folder` | 重新刮削文件夹。 |
| `POST` | `/api/search-scrape` | 搜索刮削候选。 |
| `POST` | `/api/apply-folder-scrape` | 应用文件夹刮削结果。 |
| `POST` | `/api/javdb/fetch` | 按番号获取 Javdatabase 信息。 |

## 更新、备份和设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/config` | 获取运行时配置。 |
| `POST` | `/api/config` | 保存运行时配置。 |
| `GET` | `/api/backup` | 下载备份。 |
| `POST` | `/api/restore` | 从备份恢复。 |
| `POST` | `/api/restore/upload` | 上传备份并恢复。 |
| `GET` | `/api/version` | 获取当前版本和运行层信息。 |
| `GET` | `/api/update/check` | 检查可用更新。 |
| `POST` | `/api/update/perform` | 执行更新。 |
| `GET` | `/api/update/status` | 获取更新状态。 |
| `POST` | `/api/update/rollback` | 回滚应用包更新。 |
| `GET` | `/api/update/changelog` | 获取版本更新日志。 |

## 使用建议

第三方客户端应优先使用公开稳定的播放和媒体浏览能力，不要依赖前端内部字段。涉及认证、媒体 token、恢复、更新和文件路径访问的端点属于高风险接口，调用前应明确权限边界。
