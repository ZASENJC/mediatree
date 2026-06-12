[English](../wiki/Jellyfin-Clients) | **简体中文**

# Jellyfin 客户端

MediaTree 当前服务端不再包含 Jellyfin/Emby 兼容 API 层。旧的 Jellyfin 风格路径，例如 `/System/*`、`/Users/*`、`/Items/*`、`/Videos/*` 和 `/emby/*`，不再属于当前服务端 API。

需要在浏览器外播放时，可以使用网页播放器的外部播放器操作，或直接访问 MediaTree 的 M3U 端点：

```text
http://你的服务器:27580/api/external-play/{movie_id}.m3u
```

独立 Android 客户端可以直连 MediaTree，也可以作为独立客户端连接 Jellyfin、Emby、SMB 和 WebDAV。
