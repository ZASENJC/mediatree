**English** | [简体中文](../wiki_zh-CN/Jellyfin-Clients)

# Jellyfin Clients

MediaTree no longer includes the Jellyfin/Emby compatibility API layer. Legacy Jellyfin-style paths such as `/System/*`, `/Users/*`, `/Items/*`, `/Videos/*`, and `/emby/*` are not part of the current server API.

For playback outside the browser, use the web player's external-player action or call MediaTree's M3U endpoint:

```text
http://your-server:27580/api/external-play/{movie_id}.m3u
```

The standalone Android app can connect to MediaTree directly and can also act as a separate client for Jellyfin, Emby, SMB, and WebDAV.
