import os
import uuid
import time
import asyncio
import hashlib
import json as json_module
from pathlib import Path
from fastapi import APIRouter, Request, Query, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings, logger
from .database import get_db, get_movie_detail
from .stream import _full_stream, _range_stream, MIME_MAP as STREAM_MIME_MAP
from .subtitles import (
    get_subtitle_tracks, find_external_subtitles,
    load_external_subtitle, extract_subtitle_stream_raw,
    get_subtitle_content,
)
from .jellyfin_auth import (
    _ensure_jellyfin_tables, get_jellyfin_user, get_jellyfin_user_optional,
    create_jellyfin_token, get_user_id_from_username, get_server_id,
    validate_jellyfin_token, parse_jellyfin_auth, SERVER_ID,
)
from .jellyfin_models import AuthByNameRequest, PlayingRequest, PlaybackInfoRequest
from .jellyfin_mappers import (
    make_library_id, parse_library_id, make_collection_folder,
    map_movie_to_jellyfin_item, map_playback_info,
    map_subtitle_tracks_to_media_streams,
    _get_container, _get_content_type, _get_file_size, _get_etag,
    build_series_items, get_seasons_for_series, get_episodes_for_season,
    make_series_id, make_season_id, _get_series_folder, SEASON_DIR_RE,
)

router = APIRouter()
_jf_logger = logger.getChild("jellyfin")


class EmbyPathRewriteMiddleware(BaseHTTPMiddleware):
    """Rewrites /emby/X requests to /X for Emby client compatibility."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/emby"):
            new_path = path[5:] or "/"
            request.scope["path"] = new_path
            request.scope["raw_path"] = new_path.encode()
        return await call_next(request)


_HOST_BASE = ""


def set_host_base(base: str):
    global _HOST_BASE
    _HOST_BASE = base.rstrip("/")


def _log(route: str, user_id: str = "", item_id: str = "", extra: str = ""):
    uid = user_id[:8] + ".." if len(user_id) > 8 else user_id
    msg = f"JF {route} user={uid} item={item_id}"
    if extra:
        msg += f" {extra}"
    _jf_logger.info(msg)


async def _get_media_info_cached(movie_id: int) -> dict | None:
    from .stream import get_media_info
    movie = await get_movie_detail(movie_id)
    if not movie:
        return None
    return get_media_info(movie["path"])


def _resolve_host_base(request: Request) -> str:
    if _HOST_BASE:
        return _HOST_BASE
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host", "127.0.0.1:27580")
    return f"{scheme}://{host}"


# ─── Lifecycle ───
async def init_jellyfin():
    await _ensure_jellyfin_tables()


# ─── System Info ───

@router.get("/System/Info/Public")
async def jf_system_info_public(request: Request):
    host_base = _resolve_host_base(request)
    local_address = host_base
    return {
        "LocalAddress": local_address,
        "ServerName": "MediaTree",
        "Version": "10.10.0",
        "ProductName": "Jellyfin Server",
        "OperatingSystem": _get_os_name(),
        "Id": get_server_id(),
        "StartupWizardCompleted": True,
    }


@router.get("/System/Info")
async def jf_system_info(request: Request):
    user = await get_jellyfin_user(request)
    _log("System/Info", user.get("user_id", ""))
    host_base = _resolve_host_base(request)
    return {
        "LocalAddress": host_base,
        "ServerName": "MediaTree",
        "Version": "10.10.0",
        "ProductName": "Jellyfin Server",
        "OperatingSystem": _get_os_name(),
        "Id": get_server_id(),
        "StartupWizardCompleted": True,
        "Architecture": "x64" if os.uname().machine in ("x86_64", "amd64") else os.uname().machine,
        "WebSocketPortNumber": 0,
        "CompletedInstallations": [],
        "CanSelfRestart": False,
        "CanLaunchWebBrowser": False,
    }


def _get_os_name() -> str:
    try:
        return os.uname().sysname
    except Exception:
        return "Linux"


# ─── Auth ───

@router.post("/Users/AuthenticateByName")
async def jf_authenticate_by_name(request: Request, body: AuthByNameRequest):
    username = body.Username or body.username
    password = body.Pw or body.password
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    if not settings.auth_enabled:
        pass
    elif username != settings.auth_user or password != settings.auth_pass:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    auth_header = request.headers.get("Authorization", "")
    client = ""
    device = ""
    device_id = ""
    version = ""
    if auth_header.startswith("MediaBrowser "):
        from .jellyfin_auth import _extract_from_mediabrowser
        client = _extract_from_mediabrowser(auth_header, "Client") or ""
        device = _extract_from_mediabrowser(auth_header, "Device") or ""
        device_id = _extract_from_mediabrowser(auth_header, "DeviceId") or ""
        version = _extract_from_mediabrowser(auth_header, "Version") or ""

    token = await create_jellyfin_token(username, client, device, device_id, version)
    user_id = get_user_id_from_username(username)

    _jf_logger.info(f"JF login: user={username} client={client} device={device}")

    return {
        "User": {
            "Name": username,
            "ServerId": get_server_id(),
            "Id": user_id,
            "HasPassword": True,
            "HasConfiguredPassword": True,
            "HasConfiguredEasyPassword": False,
            "EnableAutoLogin": False,
            "Policy": {
                "IsAdministrator": True,
                "IsHidden": False,
                "IsDisabled": False,
            },
        },
        "SessionInfo": {
            "UserId": user_id,
            "UserName": username,
            "Client": client,
            "DeviceName": device,
            "DeviceId": device_id,
            "ApplicationVersion": version,
            "IsActive": True,
        },
        "AccessToken": token,
        "ServerId": get_server_id(),
    }


@router.get("/Users/Me")
async def jf_users_me(request: Request):
    user = await get_jellyfin_user(request)
    _log("Users/Me", user.get("user_id", ""))
    return _build_user_info(user["user_name"], user["user_id"])


@router.get("/Users/{user_id}")
async def jf_user_by_id(user_id: str, request: Request):
    user = await get_jellyfin_user(request)
    _log(f"Users/{user_id}", user.get("user_id", ""))
    return _build_user_info(user.get("user_name", "unknown"), user_id)


def _build_user_info(name: str, uid: str) -> dict:
    return {
        "Name": name,
        "ServerId": get_server_id(),
        "Id": uid,
        "HasPassword": True,
        "HasConfiguredPassword": True,
        "HasConfiguredEasyPassword": False,
        "EnableAutoLogin": False,
        "Policy": {
            "IsAdministrator": True,
            "IsHidden": False,
            "IsDisabled": False,
        },
    }


# ─── Views (Libraries) ───

@router.get("/Users/{user_id}/Views")
async def jf_user_views(user_id: str, request: Request):
    user = await get_jellyfin_user(request)
    _log(f"Users/{user_id}/Views", user.get("user_id", ""))
    roots = settings.get_all_media_roots()
    items = [make_collection_folder(r) for r in roots]
    return {
        "Items": items,
        "TotalRecordCount": len(items),
    }


# ─── Items ───

@router.get("/Items")
async def jf_items(request: Request):
    user = await get_jellyfin_user(request)
    return await _get_items(request, user)


@router.get("/Users/{user_id}/Items")
async def jf_user_items(user_id: str, request: Request):
    user = await get_jellyfin_user(request)
    return await _get_items(request, user)


@router.get("/Items/{item_id}")
async def jf_item_detail(item_id: str, request: Request):
    user = await get_jellyfin_user(request)
    return await _get_item_detail(item_id, request, user)


@router.get("/Users/{user_id}/Items/{item_id}")
async def jf_user_item_detail(user_id: str, item_id: str, request: Request):
    user = await get_jellyfin_user(request)
    if item_id.lower() == "resume":
        return await _handle_resume(request, user)
    if item_id.lower() == "intros":
        return {"Items": [], "TotalRecordCount": 0}
    return await _get_item_detail(item_id, request, user)


async def _get_item_detail(item_id: str, request: Request, user: dict):
    user_id = user.get("user_id", "")
    _log(f"Items/{item_id}", user_id, item_id)

    host_base = _resolve_host_base(request)

    # Handle Series/Season pseudo-IDs
    if item_id.startswith("series_"):
        return await _get_series_detail(item_id, user_id, host_base)
    if item_id.startswith("season_"):
        return await _get_season_detail(item_id, user_id, host_base)

    try:
        mid = int(item_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")

    movie = await get_movie_detail(mid)
    if not movie:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check if this movie is an episode in a series
    fl = movie.get("folder_levels", "")
    series_path, season_sub, _ = _get_series_folder(fl, "")
    is_episode = False
    if season_sub:
        is_episode = True
    elif fl:
        from .database import get_db
        db = await get_db()
        cur = await db.execute("SELECT COUNT(*) as cnt FROM movies WHERE folder_levels = ?", (fl,))
        row = await cur.fetchone()
        if row and row["cnt"] > 1:
            is_episode = True

    if is_episode:
        # Return Episode style detail
        user_data_lookup = {item_id: await _get_user_data(user_id, item_id)}
        eps = get_episodes_for_season(
            (series_path + "/" + season_sub) if season_sub else (series_path + "/S01"),
            [movie], host_base, user_data_lookup
        )
        if eps:
            # Enrich with media info
            media_info = None
            try:
                from .stream import get_media_info
                media_info = await asyncio.to_thread(get_media_info, movie["path"])
            except Exception:
                pass
            ep = eps[0]
            if media_info:
                ep["RunTimeTicks"] = int(media_info.get("duration", 0) * 10_000_000)
                ep["Container"] = media_info.get("container", ep.get("Container", ""))
                stream_list = []
                if media_info.get("video_codec"):
                    stream_list.append({"Codec": media_info["video_codec"], "Type": "Video", "Index": 0, "IsDefault": True, "IsForced": False, "IsInterlaced": False})
                if media_info.get("audio_codec"):
                    stream_list.append({"Codec": media_info["audio_codec"], "Type": "Audio", "Index": 1, "Channels": media_info.get("audio_channels", 0), "IsDefault": True, "IsForced": False})
                ep["MediaSources"][0]["MediaStreams"] = stream_list
            ep["ImageTags"] = {"Primary": hashlib.md5(str(mid).encode()).hexdigest()[:16]}
            ep["BackdropImageTags"] = []
            return ep

    media_info = None
    try:
        from .stream import get_media_info
        media_info = await asyncio.to_thread(get_media_info, movie["path"])
    except Exception:
        media_info = None

    ud = await _get_user_data(user_id, item_id)
    result = map_movie_to_jellyfin_item(movie, host_base, media_info, ud)
    return result


async def _get_series_detail(series_id: str, user_id: str, host_base: str) -> dict:
    from .database import get_db
    db = await get_db()
    cur = await db.execute("SELECT folder_levels, title, cover_local, cover_remote, fanart_local FROM movies WHERE folder_levels != '' ORDER BY folder_levels")
    all_movies = [dict(r) for r in await cur.fetchall()]

    series_movies = []
    series_title = ""
    cover_local = ""
    cover_remote = ""
    fanart_local = ""
    for m in all_movies:
        fl = m.get("folder_levels", "")
        sp, _, _ = _get_series_folder(fl, "")
        if make_series_id(sp) == series_id:
            series_movies.append(m)
            if m.get("title") and m["title"] != m.get("code") and not series_title:
                series_title = m["title"]
            if not cover_local:
                cover_local = m.get("cover_local", "")
            if not cover_remote:
                cover_remote = m.get("cover_remote", "")
            if not fanart_local:
                fanart_local = m.get("fanart_local", "")

    if not series_movies:
        raise HTTPException(status_code=404, detail="Series not found")

    user_data_lookup = {}
    for m in series_movies:
        ud = await _get_user_data(user_id, str(m["id"]))
        if ud:
            user_data_lookup[str(m["id"])] = ud

    series_items = build_series_items(
        {_get_series_folder(m["folder_levels"], "")[0]: [m] for m in series_movies},
        "", host_base, user_data_lookup
    )
    if series_items:
        return series_items[0]
    raise HTTPException(status_code=404, detail="Series not found")


async def _get_season_detail(season_id: str, user_id: str, host_base: str) -> dict:
    from .database import get_db
    db = await get_db()
    cur = await db.execute("SELECT folder_levels FROM movies WHERE folder_levels != '' ORDER BY folder_levels")
    all_movies = [dict(r) for r in await cur.fetchall()]

    season_movies = []
    season_path = ""
    for m in all_movies:
        fl = m.get("folder_levels", "")
        sp, ss, _ = _get_series_folder(fl, "")
        key = (sp + "/" + ss) if ss else (sp + "/S01")
        if make_season_id(key) == season_id:
            season_movies.append(m)
            season_path = key

    if not season_movies:
        raise HTTPException(status_code=404, detail="Season not found")

    user_data_lookup = {}
    for m in season_movies:
        ud = await _get_user_data(user_id, str(m["id"]))
        if ud:
            user_data_lookup[str(m["id"])] = ud

    season_items = get_seasons_for_series(
        "/".join(season_path.split("/")[:-1]), season_movies, host_base, user_data_lookup
    )
    for item in season_items:
        if item.get("Id") == season_id:
            return item
    raise HTTPException(status_code=404, detail="Season not found")


async def _get_items(request: Request, user: dict) -> dict:
    user_id = user.get("user_id", "")
    parent_id = request.query_params.get("ParentId", "")
    include_item_types = request.query_params.get("IncludeItemTypes", "")
    recursive = request.query_params.get("Recursive", "").lower() == "true"
    try:
        start_index = int(request.query_params.get("StartIndex", "0"))
    except (ValueError, TypeError):
        start_index = 0
    try:
        limit = int(request.query_params.get("Limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    sort_by = request.query_params.get("SortBy", "SortName")
    sort_order = request.query_params.get("SortOrder", "Ascending").lower()
    search_term = request.query_params.get("SearchTerm", "")

    _log(f"Items", user_id, parent_id, f"limit={limit} offset={start_index} types={include_item_types}")

    host_base = _resolve_host_base(request)

    # Parent is a Season → return Episodes
    if parent_id.startswith("season_"):
        return await _items_for_season(parent_id, user_id, host_base, start_index, limit)

    # Parent is a Series → return Seasons
    if parent_id.startswith("series_"):
        return await _items_for_series(parent_id, user_id, host_base, start_index, limit)

    # Parent is a Library → return Series + Movies
    media_root = ""
    if parent_id.startswith("library_"):
        mr = parse_library_id(parent_id)
        if mr:
            media_root = mr

    if not media_root:
        roots = settings.get_all_media_roots()
        if roots:
            media_root = roots[0]

    # Determine which types to return
    item_types = [t.strip() for t in include_item_types.split(",") if t.strip()]

    if search_term:
        from .database import search_movies
        result = await search_movies(search_term, media_root=media_root, limit=limit, offset=start_index)
        movies = result.get("movies", [])
        total = result.get("total", 0)
        items = []
        for movie in movies:
            ud = await _get_user_data(user_id, str(movie["id"]))
            item = map_movie_to_jellyfin_item(movie, host_base, None, ud)
            items.append(item)
        return {"Items": items, "TotalRecordCount": total, "StartIndex": start_index}

    # Fetch all movies for this library (for grouping purposes)
    from .database import get_db
    db = await get_db()
    cols = "id, path, code, title, cover_local, cover_remote, fanart_local, folder_levels, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, duration, created_at"
    where = " WHERE media_root = ?"
    params = [media_root]
    cur = await db.execute(f"SELECT {cols} FROM movies{where} ORDER BY folder_levels, path", params)
    all_movies = [dict(r) for r in await cur.fetchall()]

    if not all_movies:
        return {"Items": [], "TotalRecordCount": 0, "StartIndex": 0}

    # Determine which folders are TV series (multi-file or have season subdirs)
    shows_wanted = not item_types or "Series" in item_types
    movies_wanted = not item_types or "Movie" in item_types

    # Build user_data lookup
    user_data_lookup = {}
    for m in all_movies:
        mid = str(m["id"])
        ud = await _get_user_data(user_id, mid)
        if ud:
            user_data_lookup[mid] = ud

    items = []

    if shows_wanted:
        # Group by series folder
        movies_by_folder: dict[str, list[dict]] = {}
        standalone_movies: dict[str, list[dict]] = {}
        for m in all_movies:
            fl = m.get("folder_levels", "")
            if not fl:
                continue
            series_path, season_sub, _ = _get_series_folder(fl, media_root)
            # Check if this is part of a multi-episode show
            if season_sub:
                # Has season subfolder → definitely a series
                movies_by_folder.setdefault(series_path, []).append(m)
            else:
                # Check if folder has multiple files → series
                standalone_movies.setdefault(fl, []).append(m)

        # Merge standalone folders with multiple files into series
        standalone_series = []
        standalone_true_movies = []
        for folder_path, folder_movies in standalone_movies.items():
            if len(folder_movies) > 1:
                movies_by_folder[folder_path] = folder_movies
            else:
                standalone_true_movies.extend(folder_movies)

        # Build Series items grouped with their seasons
        if movies_by_folder:
            series_items = build_series_items(movies_by_folder, media_root, host_base, user_data_lookup)
            items.extend(series_items)

        # Add standalone Movies
        if movies_wanted:
            for movie in standalone_true_movies:
                ud = user_data_lookup.get(str(movie["id"]), {})
                item = map_movie_to_jellyfin_item(movie, host_base, None, ud)
                items.append(item)

    elif movies_wanted:
        for movie in all_movies:
            ud = user_data_lookup.get(str(movie["id"]), {})
            item = map_movie_to_jellyfin_item(movie, host_base, None, ud)
            items.append(item)

    total = len(items)
    # Apply pagination
    items = items[start_index:start_index + limit]

    return {
        "Items": items,
        "TotalRecordCount": total,
        "StartIndex": start_index,
    }


async def _items_for_season(season_id: str, user_id: str, host_base: str, start_index: int, limit: int) -> dict:
    from .database import get_db
    db = await get_db()
    cols = "id, path, code, title, cover_local, cover_remote, fanart_local, folder_levels, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, duration"
    cur = await db.execute(f"SELECT {cols} FROM movies WHERE folder_levels != '' ORDER BY folder_levels, path")
    all_movies = [dict(r) for r in await cur.fetchall()]

    # Filter episodes belonging to this season
    season_movies = []
    for m in all_movies:
        fl = m.get("folder_levels", "")
        series_path, season_sub, _ = _get_series_folder(fl, "")
        if season_sub:
            key = series_path + "/" + season_sub
        else:
            key = series_path + "/S01"
        if make_season_id(key) == season_id:
            season_movies.append(m)

    if not season_movies:
        return {"Items": [], "TotalRecordCount": 0, "StartIndex": 0}

    user_data_lookup = {}
    for m in season_movies:
        ud = await _get_user_data(user_id, str(m["id"]))
        if ud:
            user_data_lookup[str(m["id"])] = ud

    season_path = ""
    for m in season_movies:
        fl = m.get("folder_levels", "")
        sp, ss, _ = _get_series_folder(fl, "")
        season_path = (sp + "/" + ss) if ss else (sp + "/S01")
        break

    items = get_episodes_for_season(season_path, season_movies, host_base, user_data_lookup)
    total = len(items)
    items = items[start_index:start_index + limit]
    return {"Items": items, "TotalRecordCount": total, "StartIndex": start_index}


async def _items_for_series(series_id: str, user_id: str, host_base: str, start_index: int, limit: int) -> dict:
    from .database import get_db
    db = await get_db()
    cols = "id, path, code, title, folder_levels, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, duration"
    cur = await db.execute(f"SELECT {cols} FROM movies WHERE folder_levels != '' ORDER BY folder_levels, path")
    all_movies = [dict(r) for r in await cur.fetchall()]

    # Filter movies belonging to this series
    series_movies = []
    for m in all_movies:
        fl = m.get("folder_levels", "")
        sp, _, _ = _get_series_folder(fl, "")
        if make_series_id(sp) == series_id:
            series_movies.append(m)

    if not series_movies:
        return {"Items": [], "TotalRecordCount": 0, "StartIndex": 0}

    user_data_lookup = {}
    for m in series_movies:
        ud = await _get_user_data(user_id, str(m["id"]))
        if ud:
            user_data_lookup[str(m["id"])] = ud

    # Get the series path
    series_path = ""
    for m in series_movies:
        fl = m.get("folder_levels", "")
        sp, _, _ = _get_series_folder(fl, "")
        series_path = sp
        break

    items = get_seasons_for_series(series_path, series_movies, host_base, user_data_lookup)
    total = len(items)
    items = items[start_index:start_index + limit]
    return {"Items": items, "TotalRecordCount": total, "StartIndex": start_index}


# ─── Playback Info ───

@router.get("/Items/{item_id}/PlaybackInfo")
async def jf_playback_info_get(item_id: str, request: Request):
    return await _handle_playback_info(item_id, request, PlaybackInfoRequest())


@router.post("/Items/{item_id}/PlaybackInfo")
async def jf_playback_info_post(item_id: str, request: Request, body: PlaybackInfoRequest = None):
    if body is None:
        body = PlaybackInfoRequest()
    return await _handle_playback_info(item_id, request, body)


@router.get("/Users/{user_id}/Items/{item_id}/PlaybackInfo")
async def jf_user_playback_info_get(user_id: str, item_id: str, request: Request):
    return await _handle_playback_info(item_id, request, PlaybackInfoRequest(UserId=user_id))


@router.post("/Users/{user_id}/Items/{item_id}/PlaybackInfo")
async def jf_user_playback_info_post(user_id: str, item_id: str, request: Request, body: PlaybackInfoRequest = None):
    if body is None:
        body = PlaybackInfoRequest()
    if not body.UserId:
        body.UserId = user_id
    return await _handle_playback_info(item_id, request, body)


async def _handle_playback_info(item_id: str, request: Request, body: PlaybackInfoRequest):
    user = await get_jellyfin_user(request)
    user_id = body.UserId or user.get("user_id", "")
    _log(f"Items/{item_id}/PlaybackInfo", user_id, item_id)

    try:
        mid = int(item_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")

    movie = await get_movie_detail(mid)
    if not movie:
        raise HTTPException(status_code=404, detail="Item not found")

    media_info = None
    try:
        from .stream import get_media_info
        media_info = await asyncio.to_thread(get_media_info, movie["path"])
    except Exception:
        pass

    subtitle_tracks = _get_full_subtitle_tracks(movie["path"])

    host_base = _resolve_host_base(request)
    play_session_id = str(uuid.uuid4())

    client = user.get("client", "")
    device = user.get("device", "")
    device_id = user.get("device_id", "")

    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO playback_sessions
           (play_session_id, user_id, item_id, client, device, device_id, started_at, last_seen_at)
           VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))""",
        (play_session_id, user_id, item_id, client, device, device_id),
    )
    await db.commit()

    enable_dp = body.EnableDirectPlay if body else True
    enable_ds = body.EnableDirectStream if body else True

    result = map_playback_info(
        movie, host_base, media_info, subtitle_tracks, play_session_id,
        enable_direct_play=enable_dp, enable_direct_stream=enable_ds,
    )
    return result


def _get_full_subtitle_tracks(file_path: str) -> list[dict]:
    tracks = get_subtitle_tracks(file_path)
    external = find_external_subtitles(file_path)
    result = list(tracks)
    for i, t in enumerate(external):
        result.append({
            "index": 1000 + i,
            "stream_index": -1,
            "codec": Path(t["path"]).suffix.lstrip("."),
            "language": t.get("language", "und"),
            "title": t.get("name", ""),
            "source": "external",
            "path": t["path"],
        })
    return result


# ─── Video Stream ───

@router.head("/Videos/{item_id}/stream")
@router.get("/Videos/{item_id}/stream")
async def jf_video_stream(item_id: str, request: Request):
    return await _handle_video_stream(item_id, request)


@router.head("/Videos/{item_id}/stream.{container}")
@router.get("/Videos/{item_id}/stream.{container}")
async def jf_video_stream_container(item_id: str, container: str, request: Request):
    return await _handle_video_stream(item_id, request)


async def _handle_video_stream(item_id: str, request: Request):
    auth = parse_jellyfin_auth(request)
    token = auth.get("token") or ""
    if token:
        user_info = await validate_jellyfin_token(token)
        if not user_info:
            _jf_logger.warning(f"JF stream auth failed for item {item_id}: invalid token")
            raise HTTPException(status_code=401, detail="Unauthorized")
        user_id = user_info.get("user_id", "")
    else:
        shared_token = (request.query_params.get("token") or
                        request.query_params.get("api_key") or "")
        if shared_token:
            user_info = await validate_jellyfin_token(shared_token)
            if not user_info:
                raise HTTPException(status_code=401, detail="Invalid token")
            user_id = user_info.get("user_id", "")
        else:
            raise HTTPException(status_code=401, detail="Authentication required")

    try:
        mid = int(item_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")

    movie = await get_movie_detail(mid)
    if not movie:
        raise HTTPException(status_code=404, detail="Item not found")

    file_path = Path(movie["path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_root = movie.get("media_root", "")
    allowed_roots = settings.get_all_media_roots() + [settings.media_root]
    is_allowed = False
    resolved_path = file_path.resolve()
    for root_path in allowed_roots:
        resolved_root = Path(root_path).resolve()
        try:
            if resolved_path.is_relative_to(resolved_root):
                is_allowed = True
                break
        except (ValueError, AttributeError):
            if str(resolved_path).startswith(str(resolved_root)):
                is_allowed = True
                break
    if not is_allowed:
        _jf_logger.warning(f"JF stream blocked: {file_path} not in allowed roots")
        raise HTTPException(status_code=403, detail="Forbidden")

    ext = file_path.suffix.lower()
    content_type = STREAM_MIME_MAP.get(ext, "application/octet-stream")
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range", "")

    _log("Videos/stream", user_id, item_id,
         f"Range={'yes' if range_header else 'no'} size={file_size}")

    if request.method == "HEAD":
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": content_type,
            "Content-Disposition": "inline",
            "Access-Control-Allow-Origin": "*",
        }
        return Response(status_code=200, headers=headers)

    if not range_header:
        return _full_stream(file_path, content_type, file_size)

    return _range_stream(file_path, content_type, file_size, range_header)


# ─── Images ───

@router.get("/Items/{item_id}/Images/Primary")
async def jf_item_image_primary(item_id: str, request: Request):
    return await _serve_image(item_id, "primary", request)


@router.get("/Items/{item_id}/Images/Backdrop")
async def jf_item_image_backdrop(item_id: str, request: Request):
    return await _serve_image(item_id, "backdrop", request)


@router.get("/Items/{item_id}/Images/Logo")
async def jf_item_image_logo(item_id: str, request: Request):
    return await _serve_image(item_id, "logo", request)


async def _serve_image(item_id: str, image_type: str, request: Request):
    # Handle Series/Season IDs
    if item_id.startswith("series_"):
        return await _serve_series_image(item_id, image_type)
    if item_id.startswith("season_"):
        return await _serve_season_image(item_id, image_type)

    try:
        mid = int(item_id)
    except ValueError:
        raise HTTPException(status_code=404)

    movie = await get_movie_detail(mid)
    if not movie:
        raise HTTPException(status_code=404)

    etag = _get_etag(mid)
    if_none_match = request.headers.get("If-None-Match", "")
    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304)

    if image_type == "primary":
        cover_local = movie.get("cover_local")
        if cover_local:
            if "/" not in cover_local and "\\" not in cover_local:
                p = Path(settings.covers_dir) / f"{cover_local}.jpg"
                if p.exists():
                    return FileResponse(
                        str(p), media_type="image/jpeg",
                        headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"},
                    )
            if Path(cover_local).exists():
                return FileResponse(
                    cover_local, media_type="image/jpeg",
                    headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"},
                )
        cover_remote = movie.get("cover_remote")
        if cover_remote:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(cover_remote)
                    if resp.status_code == 200:
                        return Response(
                            content=resp.content,
                            media_type=resp.headers.get("content-type", "image/jpeg"),
                            headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"},
                        )
            except Exception:
                pass

    elif image_type == "backdrop":
        fanart = movie.get("fanart_local")
        if fanart:
            if fanart.startswith("http://") or fanart.startswith("https://"):
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(fanart)
                        if resp.status_code == 200:
                            return Response(
                                content=resp.content,
                                media_type=resp.headers.get("content-type", "image/jpeg"),
                                headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"},
                            )
                except Exception:
                    pass
            elif Path(fanart).exists():
                return FileResponse(
                    fanart, media_type="image/jpeg",
                    headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"},
                )

    raise HTTPException(status_code=404)


# ─── Subtitles ───

@router.get("/Videos/{item_id}/{media_source_id}/Subtitles/{index}/Stream.{format}")
async def jf_subtitle_stream(
    item_id: str, media_source_id: str,
    index: int, format: str, request: Request,
):
    auth = parse_jellyfin_auth(request)
    token = auth.get("token") or ""
    if not token:
        raise HTTPException(status_code=401)
    user_info = await validate_jellyfin_token(token)
    if not user_info:
        raise HTTPException(status_code=401)

    try:
        mid = int(item_id)
    except ValueError:
        raise HTTPException(status_code=404)

    movie = await get_movie_detail(mid)
    if not movie:
        raise HTTPException(status_code=404)

    file_path = movie["path"]
    content = None
    content_type = f"application/x-subrip; charset=utf-8"

    if index >= 1000:
        ext_idx = index - 1000
        ext_subs = find_external_subtitles(file_path)
        if ext_idx < len(ext_subs):
            sub_path = ext_subs[ext_idx]["path"]
            if format.lower() in ("ass", "ssa"):
                content = get_subtitle_content(sub_path)
                content_type = "text/plain; charset=utf-8"
            elif format.lower() == "vtt":
                from .subtitles import convert_external_to_webvtt
                content = convert_external_to_webvtt(sub_path)
                content_type = "text/vtt; charset=utf-8"
            else:
                content = get_subtitle_content(sub_path)
                content_type = "application/x-subrip; charset=utf-8"
    else:
        tracks = get_subtitle_tracks(file_path)
        matching = [t for t in tracks if t.get("index") == index]
        if matching:
            codec = matching[0].get("codec", "")
            if codec in ("ass", "ssa") and format.lower() in ("ass", "ssa"):
                raw, _ = extract_subtitle_stream_raw(
                    file_path, matching[0]["stream_index"], codec
                )
                content = raw
                content_type = "text/plain; charset=utf-8"
            elif format.lower() == "vtt":
                from .subtitles import extract_subtitle_stream
                content = extract_subtitle_stream(
                    file_path, matching[0]["stream_index"]
                )
                content_type = "text/vtt; charset=utf-8"
            else:
                raw, _ = extract_subtitle_stream_raw(
                    file_path, matching[0]["stream_index"], codec
                )
                content = raw
                content_type = "application/x-subrip; charset=utf-8"

    if content is None:
        raise HTTPException(status_code=404)

    return Response(
        content=content,
        media_type=content_type,
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ─── Sessions / Playing ───

@router.post("/Sessions/Playing")
async def jf_sessions_playing(request: Request):
    body = await _parse_playing_body(request)
    return await _handle_playing_progress(request, body, "started")


@router.post("/Sessions/Playing/Progress")
async def jf_sessions_playing_progress(request: Request):
    body = await _parse_playing_body(request)
    return await _handle_playing_progress(request, body, "progress")


@router.post("/Sessions/Playing/Stopped")
async def jf_sessions_playing_stopped(request: Request):
    body = await _parse_playing_body(request)
    return await _handle_playing_progress(request, body, "stopped")


async def _parse_playing_body(request: Request) -> PlayingRequest:
    try:
        raw = await request.body()
        if not raw:
            return PlayingRequest()
        data = json_module.loads(raw.decode("utf-8"))
        return PlayingRequest(**data)
    except Exception:
        return PlayingRequest()


async def _handle_playing_progress(request: Request, body: PlayingRequest, event: str):
    auth = parse_jellyfin_auth(request)
    token = auth.get("token") or ""
    if not token:
        raise HTTPException(status_code=401)
    user_info = await validate_jellyfin_token(token)
    if not user_info:
        raise HTTPException(status_code=401)

    user_id = user_info.get("user_id", "")
    item_id = body.ItemId or ""
    position_ticks = body.PositionTicks or 0
    is_paused = body.IsPaused
    play_session_id = body.PlaySessionId or ""
    client = user_info.get("client", "")
    device = user_info.get("device", "") or auth.get("device", "")
    device_id = user_info.get("device_id", "") or auth.get("device_id", "")

    db = await get_db()

    if play_session_id:
        if event == "stopped":
            await db.execute(
                "UPDATE playback_sessions SET position_ticks=?, is_paused=?, stopped_at=datetime('now'), last_seen_at=datetime('now') WHERE play_session_id=?",
                (position_ticks, 0, play_session_id),
            )
        else:
            await db.execute(
                "UPDATE playback_sessions SET position_ticks=?, is_paused=?, last_seen_at=datetime('now') WHERE play_session_id=?",
                (position_ticks, 1 if is_paused else 0, play_session_id),
            )

    if item_id:
        try:
            mid = int(item_id)
        except ValueError:
            mid = 0

        if mid:
            movie = await get_movie_detail(mid)
            if movie and movie.get("duration"):
                total_duration = float(movie["duration"])
                if total_duration < 1000 and position_ticks > int(total_duration * 10_000_000):
                    total_duration *= 60
                total_ticks = int(total_duration * 10_000_000)
                is_played = 0
                if event == "stopped" and total_ticks > 0:
                    progress_pct = position_ticks / total_ticks
                    if progress_pct >= 0.90:
                        is_played = 1
                stored_position = 0 if is_played else position_ticks

                await db.execute(
                    """INSERT OR REPLACE INTO user_data
                       (user_id, item_id, playback_position_ticks, play_count, is_favorite, played, last_played_date, updated_at)
                       VALUES (?, ?, ?, COALESCE((SELECT play_count FROM user_data WHERE user_id=? AND item_id=?), 0) + CASE WHEN ? = 'started' THEN 1 ELSE 0 END,
                               COALESCE((SELECT is_favorite FROM user_data WHERE user_id=? AND item_id=?), 0),
                               MAX(COALESCE((SELECT played FROM user_data WHERE user_id=? AND item_id=?), 0), ?),
                               CASE WHEN ? = 'stopped' THEN datetime('now') ELSE COALESCE((SELECT last_played_date FROM user_data WHERE user_id=? AND item_id=?), datetime('now')) END,
                               datetime('now'))""",
                    (user_id, item_id, stored_position, user_id, item_id, event,
                     user_id, item_id,
                     user_id, item_id, is_played,
                     event, user_id, item_id),
                )
                if is_played:
                    await db.execute(
                        "INSERT OR IGNORE INTO tags (movie_id, tag, created_at) VALUES (?,?,datetime('now'))",
                        (mid, "watched"),
                    )

    await db.commit()

    if event != "progress":
        _log(f"Sessions/{event}", user_id, item_id,
             f"position={position_ticks}")

    return Response(status_code=204)


# ─── UserData ───

@router.post("/Users/{user_id}/PlayedItems/{item_id}")
async def jf_mark_played(user_id: str, item_id: str, request: Request):
    user = await get_jellyfin_user(request)
    await _set_user_data_state(user_id, item_id, "played", True)
    return await _get_user_item_data(user_id, item_id)


@router.delete("/Users/{user_id}/PlayedItems/{item_id}")
async def jf_unmark_played(user_id: str, item_id: str, request: Request):
    user = await get_jellyfin_user(request)
    await _set_user_data_state(user_id, item_id, "played", False)
    return await _get_user_item_data(user_id, item_id)


@router.post("/Users/{user_id}/FavoriteItems/{item_id}")
async def jf_mark_favorite(user_id: str, item_id: str, request: Request):
    user = await get_jellyfin_user(request)
    await _set_user_data_state(user_id, item_id, "favorite", True)
    _log(f"Users/{user_id}/FavoriteItems/{item_id}", user_id, item_id, "mark")
    return await _get_user_item_data(user_id, item_id)


@router.delete("/Users/{user_id}/FavoriteItems/{item_id}")
async def jf_unmark_favorite(user_id: str, item_id: str, request: Request):
    user = await get_jellyfin_user(request)
    await _set_user_data_state(user_id, item_id, "favorite", False)
    _log(f"Users/{user_id}/FavoriteItems/{item_id}", user_id, item_id, "unmark")
    return await _get_user_item_data(user_id, item_id)


async def _get_user_data(user_id: str, item_id: str) -> dict:
    if not user_id or not item_id:
        return {}
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM user_data WHERE user_id=? AND item_id=?",
        (user_id, item_id),
    )
    row = await cur.fetchone()
    if row:
        return dict(row)
    return {}


async def _set_user_data_state(user_id: str, item_id: str, field: str, value: bool):
    db = await get_db()
    int_val = 1 if value else 0
    if field == "played":
        cur = await db.execute(
            "SELECT user_id FROM user_data WHERE user_id=? AND item_id=?",
            (user_id, item_id),
        )
        if await cur.fetchone():
            await db.execute(
                "UPDATE user_data SET played=?, updated_at=datetime('now') WHERE user_id=? AND item_id=?",
                (int_val, user_id, item_id),
            )
        else:
            await db.execute(
                """INSERT INTO user_data (user_id, item_id, playback_position_ticks, play_count, is_favorite, played, last_played_date, updated_at)
                   VALUES (?,?,0,0,0,?,datetime('now'),datetime('now'))""",
                (user_id, item_id, int_val),
            )
        try:
            mid = int(item_id)
            if value:
                await db.execute(
                    "INSERT OR IGNORE INTO tags (movie_id, tag, created_at) VALUES (?,?,datetime('now'))",
                    (mid, "watched"),
                )
            else:
                await db.execute("DELETE FROM tags WHERE movie_id=? AND tag='watched'", (mid,))
        except ValueError:
            pass
    elif field == "favorite":
        cur = await db.execute(
            "SELECT user_id FROM user_data WHERE user_id=? AND item_id=?",
            (user_id, item_id),
        )
        if await cur.fetchone():
            await db.execute(
                "UPDATE user_data SET is_favorite=?, updated_at=datetime('now') WHERE user_id=? AND item_id=?",
                (int_val, user_id, item_id),
            )
        else:
            await db.execute(
                """INSERT INTO user_data (user_id, item_id, playback_position_ticks, play_count, is_favorite, played, last_played_date, updated_at)
                   VALUES (?,?,0,0,?,0,datetime('now'),datetime('now'))""",
                (user_id, item_id, int_val),
            )
    await db.commit()


async def _get_user_item_data(user_id: str, item_id: str) -> dict:
    ud = await _get_user_data(user_id, item_id)
    return {
        "PlaybackPositionTicks": ud.get("playback_position_ticks", 0),
        "PlayCount": ud.get("play_count", 0),
        "IsFavorite": bool(ud.get("is_favorite", False)),
        "Played": bool(ud.get("played", False)),
        "Key": item_id,
    }


# ─── Utility: sync MediaTree watched/favorite tags with user_data ───

async def _handle_resume(request: Request, user: dict) -> dict:
    user_id = user.get("user_id", "")
    req = request.query_params
    limit = int(req.get("Limit", "20"))
    host_base = _resolve_host_base(request)

    items = []
    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, item_id, playback_position_ticks, played FROM user_data WHERE user_id=? AND played=0 AND playback_position_ticks > 0 ORDER BY updated_at DESC LIMIT ?",
        (user_id, limit),
    )
    for row in await cur.fetchall():
        try:
            mid = int(row["item_id"])
        except ValueError:
            continue
        movie = await get_movie_detail(mid)
        if movie:
            ud = {
                "playback_position_ticks": row["playback_position_ticks"],
                "play_count": 0, "is_favorite": 0, "played": row["played"],
            }
            item = map_movie_to_jellyfin_item(movie, host_base, None, ud)
            items.append(item)

    return {"Items": items, "TotalRecordCount": len(items)}


@router.get("/Shows/NextUp")
async def jf_shows_next_up(request: Request):
    user = await get_jellyfin_user(request)
    user_id = user.get("user_id", "")
    req = request.query_params
    limit = int(req.get("Limit", "20"))
    host_base = _resolve_host_base(request)

    db = await get_db()
    cur = await db.execute(
        "SELECT user_id, item_id, playback_position_ticks, played FROM user_data WHERE user_id=? AND played=0 ORDER BY updated_at DESC LIMIT ?",
        (user_id, limit),
    )
    items = []
    for row in await cur.fetchall():
        try:
            mid = int(row["item_id"])
        except ValueError:
            continue
        movie = await get_movie_detail(mid)
        if movie:
            ud = {
                "playback_position_ticks": row["playback_position_ticks"],
                "play_count": 0, "is_favorite": 0, "played": row["played"],
            }
            item = map_movie_to_jellyfin_item(movie, host_base, None, ud)
            items.append(item)

    return {"Items": items, "TotalRecordCount": len(items)}


@router.get("/Library/MediaFolders")
async def jf_library_media_folders(request: Request):
    user = await get_jellyfin_user(request)
    roots = settings.get_all_media_roots()
    items = [make_collection_folder(r) for r in roots]
    return {"Items": items, "TotalRecordCount": len(items)}


@router.get("/Items/{item_id}/Intros")
async def jf_item_intros(item_id: str, request: Request):
    return {"Items": [], "TotalRecordCount": 0}


@router.get("/Users/{user_id}/Items/{item_id}/Intros")
async def jf_user_item_intros(user_id: str, item_id: str, request: Request):
    return {"Items": [], "TotalRecordCount": 0}


@router.get("/Genres")
async def jf_genres(request: Request):
    user = await get_jellyfin_user(request)
    return {"Items": [], "TotalRecordCount": 0}


@router.get("/DisplayPreferences/{user_id}")
async def jf_display_preferences(user_id: str, request: Request):
    return {
        "Id": user_id,
        "SortBy": "SortName",
        "SortOrder": "Ascending",
        "ViewType": "Poster",
        "CustomPrefs": {},
    }


@router.post("/DisplayPreferences/{user_id}")
async def jf_display_preferences_save(user_id: str, request: Request):
    return {"ok": True}


async def _sync_tags_to_user_data(user_name: str):
    """Sync MediaTree 'favorite' and 'watched' tags to user_data table."""
    user_id = get_user_id_from_username(user_name)
    db = await get_db()

    fav_rows = await db.execute(
        "SELECT movie_id FROM tags WHERE tag='favorite'"
    )
    for row in await fav_rows.fetchall():
        item_id = str(row["movie_id"])
        await db.execute(
            """INSERT OR IGNORE INTO user_data (user_id, item_id, is_favorite, updated_at)
               VALUES (?,?,1,datetime('now'))""",
            (user_id, item_id),
        )
        await db.execute(
            "UPDATE user_data SET is_favorite=1 WHERE user_id=? AND item_id=?",
            (user_id, item_id),
        )

    watched_rows = await db.execute(
        "SELECT movie_id FROM tags WHERE tag='watched'"
    )
    for row in await watched_rows.fetchall():
        item_id = str(row["movie_id"])
        await db.execute(
            """INSERT OR IGNORE INTO user_data (user_id, item_id, played, updated_at)
               VALUES (?,?,1,datetime('now'))""",
            (user_id, item_id),
        )
        await db.execute(
            "UPDATE user_data SET played=1 WHERE user_id=? AND item_id=?",
            (user_id, item_id),
        )

    await db.commit()


# ─── Series/Season image helpers ───

async def _serve_series_image(series_id: str, image_type: str):
    from .database import get_db
    db = await get_db()
    cur = await db.execute(
        "SELECT cover_local, cover_remote, fanart_local, folder_levels FROM movies WHERE folder_levels != ''"
    )
    all_movies = [dict(r) for r in await cur.fetchall()]

    cover_local = ""
    cover_remote = ""
    fanart_local = ""
    for m in all_movies:
        fl = m.get("folder_levels", "")
        sp, _, _ = _get_series_folder(fl, "")
        if make_series_id(sp) == series_id:
            if not cover_local:
                cover_local = m.get("cover_local", "")
            if not cover_remote:
                cover_remote = m.get("cover_remote", "")
            if not fanart_local:
                fanart_local = m.get("fanart_local", "")

    if image_type == "primary" and (cover_local or cover_remote):
        return await _serve_image_blob(cover_local, cover_remote, series_id)
    if image_type == "backdrop" and fanart_local:
        return await _serve_image_blob("", fanart_local, series_id)
    raise HTTPException(status_code=404)


async def _serve_season_image(season_id: str, image_type: str):
    from .database import get_db
    db = await get_db()
    cur = await db.execute(
        "SELECT cover_local, cover_remote, fanart_local, folder_levels FROM movies WHERE folder_levels != ''"
    )
    all_movies = [dict(r) for r in await cur.fetchall()]

    cover_local = ""
    cover_remote = ""
    fanart_local = ""
    for m in all_movies:
        fl = m.get("folder_levels", "")
        sp, ss, _ = _get_series_folder(fl, "")
        key = (sp + "/" + ss) if ss else (sp + "/S01")
        if make_season_id(key) == season_id:
            if not cover_local:
                cover_local = m.get("cover_local", "")
            if not cover_remote:
                cover_remote = m.get("cover_remote", "")
            if not fanart_local:
                fanart_local = m.get("fanart_local", "")

    if image_type == "primary" and (cover_local or cover_remote):
        return await _serve_image_blob(cover_local, cover_remote, season_id)
    if image_type == "backdrop" and fanart_local:
        return await _serve_image_blob("", fanart_local, season_id)
    raise HTTPException(status_code=404)


async def _serve_image_blob(cover_local: str, cover_remote_or_fanart: str, etag_key: str):
    import hashlib
    etag = hashlib.md5(etag_key.encode()).hexdigest()[:16]
    url = cover_local or cover_remote_or_fanart

    if cover_local:
        if "/" not in cover_local and "\\" not in cover_local:
            p = Path(settings.covers_dir) / f"{cover_local}.jpg"
            if p.exists():
                return FileResponse(str(p), media_type="image/jpeg",
                                    headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"})
        if Path(cover_local).exists():
            return FileResponse(cover_local, media_type="image/jpeg",
                                headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"})

    if url and (url.startswith("http://") or url.startswith("https://")):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return Response(content=resp.content,
                                    media_type=resp.headers.get("content-type", "image/jpeg"),
                                    headers={"ETag": f'"{etag}"', "Cache-Control": "public, max-age=3600"})
        except Exception:
            pass
    raise HTTPException(status_code=404)
