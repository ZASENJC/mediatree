**English** | [简体中文](../wiki_zh-CN/Jellyfin-Clients)

# Jellyfin Clients

MediaTree implements 36 Jellyfin-compatible API endpoints, allowing you to use your favorite media clients directly.

## Supported Clients

| Client | Platform | Status |
|--------|----------|--------|
| **VidHub** | iOS, macOS, Apple TV | ✓ Tested |
| **Infuse** | iOS, macOS, Apple TV | ✓ Tested |
| **Kodi** | All platforms | ✓ via Jellyfin plugin |
| **VLC** | All platforms | ✓ via UPnP/network |
| **IINA** | macOS | ✓ via M3U playlist |
| **mpv** | All platforms | ✓ via M3U playlist |

## Connection Setup

### VidHub / Infuse

1. Open the app → Add Server
2. Choose "Jellyfin" as server type
3. Server URL: `http://your-server-ip:27580`
4. Username: Your `AUTH_USER` from `.env`
5. Password: Your `AUTH_PASS` from `.env`

### Kodi (Jellyfin Plugin)

1. Install the [Jellyfin for Kodi](https://github.com/jellyfin/jellyfin-kodi) addon
2. Server host: `your-server-ip`
3. Port: `27580`
4. Use HTTP (not HTTPS unless you've configured a reverse proxy)

### VLC / IINA / mpv

Use the "External Player" button in MediaTree's web player, or access M3U playlists directly:

```
# With subtitles
http://your-server:27580/api/external-play/{movie_id}.m3u
```

## API Compatibility

### Supported Endpoints

- **System**: `/System/Info`, `/System/Info/Public`
- **Auth**: `/Users/AuthenticateByName`
- **Browsing**: `/Items`, `/Items/{id}`, `/Shows/{id}/Seasons`
- **Streaming**: `/Videos/{id}/stream` (DirectPlay)
- **Sessions**: `/Sessions/Playing`, `/Sessions/Playing/Progress`

### Auth Methods

- `MediaBrowser Token` — Standard Jellyfin token auth
- `X-Emby-Token` — Emby compatibility header
- `Authorization: Bearer` — OAuth-style bearer token
- `api_key` query parameter

### Emby Compatibility

All `/emby/*` paths are automatically rewritten to Jellyfin equivalents via `EmbyPathRewriteMiddleware`. No additional configuration needed.

## Hierarchy Mapping

MediaTree maps your folder structure to the Jellyfin Series → Season → Episode hierarchy:

```
/media/shows/
├── My Show/                    ← Series
│   ├── S01/                    ← Season 1
│   │   ├── E01.mkv            ← Episode 1
│   │   └── E02.mkv            ← Episode 2
│   └── S02/                    ← Season 2
│       └── E01.mkv            ← Episode 1
└── Movie Collection/           ← Movie collection
    └── Movie.mkv              ← Individual movie
```

## Limitations

- **Transcoding**: MediaTree serves DirectPlay by default. Clients must support the video codec natively.
- **LiveTV**: Not supported
- **Collections**: Folder-based only, no Jellyfin Collection support
- **Users**: Single user only (the admin account)

## Performance Tips

- Mount media volumes as `:ro` (read-only) for best Docker performance
- Use modern clients that support HEVC/AV1 codecs natively (avoids transcoding)
- For large libraries, consider increasing `SCRAPE_CONCURRENCY_PER_LIBRARY` in `.env`
