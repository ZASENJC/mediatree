# 外部客户端

MediaTree 的主界面是 Web 应用，同时提供外部播放器和客户端接入能力。

## 外部播放器

影片详情页可生成外部播放链接和 M3U 播放列表，适合交给 VLC、IINA、mpv 等播放器继续播放。

典型地址格式：

```text
http://your-server:27580/api/external-play/{movie_id}.m3u
```

这些链接受媒体访问令牌保护，避免绕过应用认证直接读取媒体文件。

## Android 客户端

独立 Android 客户端位于 [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app)。它可以连接 MediaTree，也可以作为独立客户端连接 Jellyfin、Emby、SMB 和 WebDAV。

连接 MediaTree 时，需要填写服务地址，例如：

```text
http://192.168.1.10:27580
```

如果服务部署在家庭局域网外，请先配置反向代理、HTTPS 和强密码。

## Jellyfin / Emby 说明

MediaTree 可以生成外部播放器播放列表，但它不是完整 Jellyfin/Emby 兼容服务端。需要 Jellyfin/Emby 原生协议时，请使用对应服务端；MediaTree 文档中的外部客户端能力只覆盖当前实际支持的播放和访问方式。
