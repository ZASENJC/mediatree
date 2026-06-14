# External Clients

MediaTree's primary interface is the Web app, but it also supports external playback and client access patterns.

## External Players

Movie detail pages can generate external playback links and M3U playlists for VLC, IINA, mpv, and similar players.

Typical URL format:

```text
http://your-server:27580/api/external-play/{movie_id}.m3u
```

These links use short-lived media access tokens so media files are not exposed without application authorization.

## Android Client

The standalone Android client lives at [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app). It can connect to MediaTree and can also work as an independent client for Jellyfin, Emby, SMB, and WebDAV.

For MediaTree, use a server URL such as:

```text
http://192.168.1.10:27580
```

For access outside your home network, configure a reverse proxy, HTTPS, and a strong password first.

## Jellyfin / Emby Note

MediaTree can generate external player playlists, but it is not a full Jellyfin/Emby-compatible server. Use a real Jellyfin or Emby server when you need their native protocols.
