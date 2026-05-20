import os
import hashlib
import json
from pathlib import Path
from typing import Optional
from .config import settings
from .jellyfin_auth import SERVER_ID

MIME_MAP = {
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm",
    ".avi": "video/x-msvideo", ".mov": "video/quicktime", ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv", ".m4v": "video/mp4", ".ts": "video/mp2t",
    ".mpg": "video/mpeg", ".mpeg": "video/mpeg",
    ".ogv": "video/ogg", ".ogm": "video/ogg", ".divx": "video/x-msvideo",
    ".rmvb": "application/vnd.rn-realmedia", ".rm": "application/vnd.rn-realmedia",
    ".asf": "video/x-ms-asf", ".3gp": "video/3gpp", ".3g2": "video/3gpp2",
}


def _duration_to_ticks(seconds: Optional[float]) -> int:
    if not seconds or seconds <= 0:
        return 0
    return int(seconds * 10_000_000)


def _get_container(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower().lstrip(".")
    return suffix or "mkv"


def _get_content_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return MIME_MAP.get(ext, "application/octet-stream")


def _get_file_size(file_path: str) -> int:
    try:
        return Path(file_path).stat().st_size
    except OSError:
        return 0


def _get_etag(movie_id: int) -> str:
    return hashlib.md5(str(movie_id).encode()).hexdigest()[:16]


def _parse_staff(raw) -> list[dict]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except Exception:
            return [{"name": n.strip()} for n in raw.split(",") if n.strip()]
    return []


def _people_from_movie(movie: dict) -> list[dict]:
    people = []
    for p in _parse_staff(movie.get("cast")):
        name = p.get("name")
        if name:
            people.append({"Name": name, "Type": "Actor", "Role": p.get("role") or p.get("character") or ""})
    if movie.get("actress"):
        for name in str(movie["actress"]).replace("，", ",").replace("、", ",").split(","):
            name = name.strip()
            if name and not any(p["Name"] == name for p in people):
                people.append({"Name": name, "Type": "Actor", "Role": ""})
    for p in _parse_staff(movie.get("crew")):
        name = p.get("name")
        job = p.get("job") or ""
        if not name:
            continue
        lower = job.lower()
        ptype = "Writer" if "writer" in lower else "Director" if "director" in lower or "supervisor" in lower else "Producer"
        people.append({"Name": name, "Type": ptype, "Role": job})
    return people


def make_library_id(media_root: str) -> str:
    return "library_" + hashlib.md5(media_root.encode()).hexdigest()[:12]


def parse_library_id(library_id: str) -> str | None:
    if not library_id.startswith("library_"):
        return None
    from .config import settings as s
    for root in s.get_all_media_roots():
        if make_library_id(root) == library_id:
            return root
    return None


def make_collection_folder(media_root: str) -> dict:
    lib_id = make_library_id(media_root)
    label = Path(media_root).name or media_root
    people = _people_from_movie(movie)
    studios = [
        p["Name"] for p in people
        if p.get("Role") and "studio" in str(p["Role"]).lower()
    ]

    return {
        "Name": label,
        "ServerId": SERVER_ID,
        "Id": lib_id,
        "Type": "CollectionFolder",
        "CollectionType": "movies",
        "IsFolder": True,
        "MediaType": "Unknown",
    }


def map_movie_to_jellyfin_item(
    movie: dict,
    host_base: str = "",
    media_info: Optional[dict] = None,
    user_data: Optional[dict] = None,
) -> dict:
    movie_id = movie["id"]
    item_id = str(movie_id)
    name = movie.get("title") or movie.get("code") or Path(movie.get("path", "")).name or "Unknown"
    path = movie.get("path", "")
    container = _get_container(path) if path else "mkv"

    duration = 0
    if media_info:
        duration = media_info.get("duration", 0)
    elif movie.get("duration"):
        duration = float(movie["duration"])

    run_time_ticks = _duration_to_ticks(duration)
    file_size = _get_file_size(path) if path else 0
    production_year = None
    if movie.get("release_date"):
        try:
            production_year = int(str(movie["release_date"])[:4])
        except (ValueError, TypeError):
            pass

    etag = _get_etag(movie_id)
    image_tags = {}
    if movie.get("cover_local") or movie.get("cover_remote"):
        image_tags["Primary"] = etag

    backdrop_tags = []
    if movie.get("fanart_local"):
        backdrop_tags = [etag]

    stream_url = f"{host_base}/Videos/{item_id}/stream.{container}" if host_base else f"/Videos/{item_id}/stream.{container}"

    sorted_name = name
    if name.lower().startswith("the "):
        sorted_name = name[4:] + ", The"

    ud = user_data or {}
    user_item_data = {
        "PlaybackPositionTicks": ud.get("playback_position_ticks", 0),
        "PlayCount": ud.get("play_count", 0),
        "IsFavorite": bool(ud.get("is_favorite", False)),
        "Played": bool(ud.get("played", False)),
    }

    media_streams = _build_media_streams(media_info, path, host_base, item_id)

    return {
        "Name": name,
        "ServerId": SERVER_ID,
        "Id": item_id,
        "Type": "Movie",
        "MediaType": "Video",
        "IsFolder": False,
        "RunTimeTicks": run_time_ticks,
        "ProductionYear": production_year,
        "Container": container,
        "Path": path,
        "SortName": sorted_name,
        "ImageTags": image_tags,
        "BackdropImageTags": backdrop_tags,
        "UserData": user_item_data,
        "MediaSources": [
            {
                "Id": item_id,
                "Path": stream_url,
                "Protocol": "Http",
                "Container": container,
                "Size": file_size,
                "Name": name,
                "IsRemote": False,
                "RunTimeTicks": run_time_ticks,
                "SupportsTranscoding": False,
                "SupportsDirectStream": True,
                "SupportsDirectPlay": True,
                "IsInfiniteStream": False,
                "RequiresOpening": False,
                "RequiresClosing": False,
                "RequiresLooping": False,
                "MediaStreams": media_streams,
            }
        ],
        "People": people,
        "Studios": [{"Name": s, "Id": hashlib.md5(s.encode()).hexdigest()[:12]} for s in studios],
    }


def _build_media_streams(
    media_info: Optional[dict],
    file_path: str,
    host_base: str,
    item_id: str,
) -> list[dict]:
    streams = []
    if not media_info:
        return streams

    if media_info.get("video_codec"):
        streams.append({
            "Codec": media_info["video_codec"],
            "Type": "Video",
            "Index": 0,
            "IsInterlaced": False,
            "IsDefault": True,
            "IsForced": False,
        })

    if media_info.get("audio_codec"):
        stream = {
            "Codec": media_info["audio_codec"],
            "Type": "Audio",
            "Index": 1,
            "Channels": media_info.get("audio_channels", 0),
            "IsDefault": True,
            "IsForced": False,
        }
        sample_rate = media_info.get("sample_rate")
        if sample_rate:
            stream["SampleRate"] = sample_rate
        lang = media_info.get("audio_language", "")
        if lang:
            stream["Language"] = lang
        streams.append(stream)

    return streams


def map_subtitle_tracks_to_media_streams(
    subtitle_tracks: list[dict],
    host_base: str = "",
    item_id: str = "",
    media_source_id: str = "",
) -> list[dict]:
    result = []
    for track in subtitle_tracks:
        idx = track.get("index", 0)
        codec = track.get("codec", "srt")
        is_external = track.get("source") == "external"
        lang = track.get("language", "und")
        title = track.get("title", "")

        stream = {
            "Codec": codec,
            "Type": "Subtitle",
            "Index": idx,
            "Language": lang,
            "DisplayTitle": title or codec.upper(),
            "IsDefault": False,
            "IsForced": False,
            "IsExternal": is_external,
        }

        if is_external:
            mid = media_source_id or item_id
            ext = codec if codec in ("ass", "ssa", "srt", "vtt") else "srt"
            stream["DeliveryMethod"] = "External"
            stream["DeliveryUrl"] = f"{host_base}/Videos/{item_id}/{mid}/Subtitles/{idx}/Stream.{ext}"
        else:
            stream["DeliveryMethod"] = "Embed"

        result.append(stream)

    return result


def map_playback_info(
    movie: dict,
    host_base: str = "",
    media_info: Optional[dict] = None,
    subtitle_tracks: Optional[list[dict]] = None,
    play_session_id: str = "",
    enable_direct_play: bool = True,
    enable_direct_stream: bool = True,
) -> dict:
    movie_id = movie["id"]
    item_id = str(movie_id)
    name = movie.get("title") or movie.get("code") or Path(movie.get("path", "")).name or "Unknown"
    path = movie.get("path", "")
    container = _get_container(path) if path else "mkv"

    duration = 0
    if media_info:
        duration = media_info.get("duration", 0)
    elif movie.get("duration"):
        duration = float(movie["duration"])

    run_time_ticks = _duration_to_ticks(duration)
    file_size = _get_file_size(path) if path else 0

    direct_stream_url = f"{host_base}/Videos/{item_id}/stream.{container}"
    if path:
        direct_stream_url += f"?MediaSourceId={item_id}&Static=true"

    media_streams = _build_media_streams(media_info, path, host_base, item_id)

    if subtitle_tracks:
        media_streams += map_subtitle_tracks_to_media_streams(
            subtitle_tracks, host_base, item_id, item_id
        )

    return {
        "MediaSources": [
            {
                "Id": item_id,
                "Path": f"{host_base}/Videos/{item_id}/stream.{container}" if host_base else f"/Videos/{item_id}/stream.{container}",
                "Protocol": "Http",
                "Container": container,
                "Size": file_size,
                "Name": name,
                "IsRemote": False,
                "ETag": _get_etag(movie_id),
                "RunTimeTicks": run_time_ticks,
                "SupportsDirectPlay": enable_direct_play,
                "SupportsDirectStream": enable_direct_stream,
                "SupportsTranscoding": False,
                "DirectStreamUrl": direct_stream_url,
                "TranscodingUrl": None,
                "TranscodingSubProtocol": None,
                "TranscodingContainer": None,
                "AnalyzeDurationMs": 1000,
                "MediaStreams": media_streams,
            }
        ],
        "PlaySessionId": play_session_id,
    }


def map_cached_jellyfin_path(cover_key: str) -> dict | None:
    p = Path(settings.covers_dir) / f"{cover_key}.jpg"
    if p.exists():
        return {"path": str(p), "content_type": "image/jpeg"}
    return None


# ─── Series / Season / Episode helpers ───

SEASON_DIR_RE = __import__("re").compile(
    r'^(S|Season\s*|第)\s*\d{1,2}$', __import__("re").I
)


def _get_series_folder(folder_levels: str, media_root: str) -> tuple[str, str | None, str]:
    """Returns (series_path, season_subpath|None, episode_name)."""
    parts = [p for p in folder_levels.replace("\\", "/").split("/") if p]
    if not parts:
        return folder_levels, None, folder_levels

    series_parts = []
    season_sub = None
    for i, part in enumerate(parts):
        if SEASON_DIR_RE.match(part):
            season_sub = part
            break
        series_parts.append(part)

    series_path = "/".join(series_parts)
    episode_name = parts[-1] if parts else ""
    return series_path, season_sub, episode_name


def make_series_id(series_path: str) -> str:
    return "series_" + hashlib.md5(("series:" + series_path).encode()).hexdigest()[:12]


def make_season_id(season_path: str) -> str:
    return "season_" + hashlib.md5(("season:" + season_path).encode()).hexdigest()[:12]


def _parse_season_number(name: str | None) -> int | None:
    if not name:
        return None
    m = __import__("re").search(r'\d+', name)
    if m:
        return int(m.group())
    return None


def build_series_items(
    movies_by_folder: dict[str, list[dict]],
    media_root: str,
    host_base: str,
    user_data_lookup: dict[str, dict] = None,
) -> list[dict]:
    """Group movies into Series with Seasons and Episodes, returns Jellyfin-format items."""
    if user_data_lookup is None:
        user_data_lookup = {}

    # Step 1: build hierarchy
    series_map: dict[str, dict] = {}  # series_path -> {series_info, seasons: {season_path -> {season_info, episodes: [...]}}}

    for folder_levels, folder_movies in movies_by_folder.items():
        if not folder_levels:
            continue
        series_path, season_sub, _ = _get_series_folder(folder_levels, media_root)

        if series_path not in series_map:
            cover_local = ""
            cover_remote = ""
            fanart_local = ""
            for m in folder_movies:
                if m.get("cover_local") and not cover_local:
                    cover_local = m["cover_local"]
                if m.get("cover_remote") and not cover_remote:
                    cover_remote = m["cover_remote"]
                if m.get("fanart_local") and not fanart_local:
                    fanart_local = m["fanart_local"]
            series_map[series_path] = {
                "series_path": series_path,
                "title": series_path.split("/")[-1] if series_path else "",
                "cover_local": cover_local,
                "cover_remote": cover_remote,
                "fanart_local": fanart_local,
                "seasons": {},
            }

        if season_sub:
            season_path = series_path + "/" + season_sub
        else:
            # episodes directly in series folder → default season
            season_sub = "S01"
            season_path = series_path + "/S01"

        if season_path not in series_map[series_path]["seasons"]:
            series_map[series_path]["seasons"][season_path] = {
                "season_path": season_path,
                "season_name": season_sub,
                "season_number": _parse_season_number(season_sub) or 1,
                "episodes": [],
            }

        series_map[series_path]["seasons"][season_path]["episodes"].extend(folder_movies)

    # Step 2: assign scraped titles to series
    for series_path, sinfo in series_map.items():
        for season_path, seainfo in sinfo["seasons"].items():
            for ep in seainfo["episodes"]:
                if ep.get("title") and ep.get("title") != ep.get("code"):
                    if not sinfo.get("title") or sinfo["title"] == series_path.split("/")[-1]:
                        sinfo["title"] = ep["title"]
                    break

    # Step 3: build Jellyfin items
    items = []

    for series_path, sinfo in series_map.items():
        series_id = make_series_id(series_path)

        # Build seasons list
        season_items = []
        for season_path, seainfo in sinfo["seasons"].items():
            season_id = make_season_id(season_path)
            episode_items = []
            for ep in seainfo["episodes"]:
                ep_id = str(ep["id"])
                ep_name = Path(ep.get("path", "")).stem or ep.get("code") or "Episode"
                container = _get_container(ep.get("path", ""))
                duration = float(ep.get("duration", 0)) if ep.get("duration") else 0
                run_ticks = _duration_to_ticks(duration)
                file_size = _get_file_size(ep.get("path", ""))

                ep_num = ep.get("tmdb_episode") or _extract_episode_number_from_name(ep_name)
                season_num = ep.get("tmdb_season") or seainfo["season_number"]

                etag = hashlib.md5(str(ep["id"]).encode()).hexdigest()[:16]
                ud = user_data_lookup.get(ep_id, {})

                episode_items.append({
                    "Name": ep.get("episode_title") or ep_name,
                    "ServerId": SERVER_ID,
                    "Id": ep_id,
                    "Type": "Episode",
                    "MediaType": "Video",
                    "IsFolder": False,
                    "RunTimeTicks": run_ticks,
                    "Container": container,
                    "Path": ep.get("path", ""),
                    "SortName": f"{season_num:02d}x{ep_num:02d}" if ep_num else ep_name,
                    "IndexNumber": ep_num,
                    "ParentIndexNumber": season_num,
                    "SeriesId": series_id,
                    "SeriesName": sinfo["title"],
                    "SeasonId": season_id,
                    "SeasonName": seainfo["season_name"],
                    "UserData": {
                        "PlaybackPositionTicks": ud.get("playback_position_ticks", 0),
                        "PlayCount": ud.get("play_count", 0),
                        "IsFavorite": bool(ud.get("is_favorite", False)),
                        "Played": bool(ud.get("played", False)),
                    },
                    "MediaSources": [
                        {
                            "Id": ep_id,
                            "Path": f"{host_base}/Videos/{ep_id}/stream.{container}",
                            "Protocol": "Http",
                            "Container": container,
                            "Size": file_size,
                            "Name": ep.get("episode_title") or ep_name,
                            "IsRemote": False,
                            "RunTimeTicks": run_ticks,
                            "SupportsTranscoding": False,
                            "SupportsDirectStream": True,
                            "SupportsDirectPlay": True,
                            "IsInfiniteStream": False,
                            "RequiresOpening": False,
                            "RequiresClosing": False,
                            "RequiresLooping": False,
                            "MediaStreams": [],
                        }
                    ],
                })

            season_items.append({
                "Name": seainfo["season_name"],
                "ServerId": SERVER_ID,
                "Id": season_id,
                "Type": "Season",
                "SeriesId": series_id,
                "SeriesName": sinfo["title"],
                "IndexNumber": seainfo["season_number"],
                "IsFolder": True,
                "ChildCount": len(episode_items),
                "UserData": {"PlaybackPositionTicks": 0, "PlayCount": 0, "IsFavorite": False, "Played": False},
                "ImageTags": {},
                "BackdropImageTags": [],
            })

        series_item = {
            "Name": sinfo["title"] or series_path.split("/")[-1],
            "ServerId": SERVER_ID,
            "Id": series_id,
            "Type": "Series",
            "IsFolder": True,
            "ChildCount": sum(s["ChildCount"] for s in season_items),
            "RecursiveItemCount": sum(s["ChildCount"] for s in season_items),
            "UserData": {"PlaybackPositionTicks": 0, "PlayCount": 0, "IsFavorite": False, "Played": False},
        }

        cov = sinfo.get("cover_local") or sinfo.get("cover_remote")
        if cov:
            cov_path = _normalize_cover_path(cov) if hasattr(__import__("sys").modules["app.jellyfin_mappers"], '_normalize_cover_path') else _normalize_cover_path(cov)
            series_item["ImageTags"] = {"Primary": hashlib.md5(cov.encode()).hexdigest()[:16]}
        else:
            series_item["ImageTags"] = {}

        if sinfo.get("fanart_local"):
            series_item["BackdropImageTags"] = [hashlib.md5(sinfo["fanart_local"].encode()).hexdigest()[:16]]
        else:
            series_item["BackdropImageTags"] = []

        items.append(series_item)

    return items


def _extract_episode_number_from_name(name: str) -> int | None:
    import re
    patterns = [
        r'\[(\d{1,3})\](?=\[[^\]]+\])',
        r'(?i)\bS\d{1,2}E(\d{1,3})\b',
        r'(?i)\bEP(?:ISODE)?\s*\.?\s*(\d{1,3})\b',
        r'(?i)\bE(\d{1,3})\b',
        r'第\s*(\d{1,3})\s*[集話话]',
        r'[\[\(\s._-](\d{1,3})[\]\)\s._-]',
    ]
    for pattern in patterns:
        m = re.search(pattern, name)
        if m:
            try:
                num = int(m.group(1))
                if 0 < num < 1000:
                    return num
            except ValueError:
                pass
    return None


def _normalize_cover_path(cover: str) -> str:
    if cover.startswith("http://") or cover.startswith("https://"):
        return cover
    if cover.startswith("/media/"):
        return cover[7:]
    if "/" not in cover and "\\" not in cover:
        return f"/api/cached-cover/{cover}"
    return cover


def get_seasons_for_series(series_path: str, movies: list[dict], host_base: str, user_data_lookup: dict[str, dict]) -> list[dict]:
    """Return Season items for a specific Series."""
    seasons: dict[str, list[dict]] = {}
    for movie in movies:
        fl = movie.get("folder_levels", "")
        s_path, season_sub, _ = _get_series_folder(fl, "")
        if make_series_id(s_path) != make_series_id(series_path):
            continue
        if season_sub:
            key = s_path + "/" + season_sub
        else:
            key = s_path + "/S01"
        if key not in seasons:
            seasons[key] = []
        seasons[key].append(movie)

    result = []
    for season_path, eps in seasons.items():
        season_name = season_path.split("/")[-1]
        season_num = _parse_season_number(season_name) or 1
        season_id = make_season_id(season_path)
        series_id = make_series_id(series_path)

        result.append({
            "Name": season_name,
            "ServerId": SERVER_ID,
            "Id": season_id,
            "Type": "Season",
            "SeriesId": series_id,
            "SeriesName": series_path.split("/")[-1],
            "IndexNumber": season_num,
            "IsFolder": True,
            "ChildCount": len(eps),
            "UserData": {"PlaybackPositionTicks": 0, "PlayCount": 0, "IsFavorite": False, "Played": False},
            "ImageTags": {},
            "BackdropImageTags": [],
        })

    return result


def get_episodes_for_season(season_path: str, movies: list[dict], host_base: str, user_data_lookup: dict[str, dict]) -> list[dict]:
    """Return Episode items for a specific Season."""
    result = []
    season_name = season_path.split("/")[-1]
    season_num = _parse_season_number(season_name) or 1
    series_path = "/".join(season_path.split("/")[:-1])
    series_id = make_series_id(series_path)
    season_id = make_season_id(season_path)

    for ep in movies:
        fl = ep.get("folder_levels", "")
        s_path, s_sub, _ = _get_series_folder(fl, "")
        if s_sub:
            key = s_path + "/" + s_sub
        else:
            key = s_path + "/S01"
        if key != season_path:
            continue

        ep_id = str(ep["id"])
        ep_name = Path(ep.get("path", "")).stem or ep.get("code") or "Episode"
        container = _get_container(ep.get("path", ""))
        duration = float(ep.get("duration", 0)) if ep.get("duration") else 0
        run_ticks = _duration_to_ticks(duration)
        file_size = _get_file_size(ep.get("path", ""))
        ep_num = ep.get("tmdb_episode") or _extract_episode_number_from_name(ep_name)
        ud = user_data_lookup.get(ep_id, {})

        result.append({
            "Name": ep.get("episode_title") or ep_name,
            "ServerId": SERVER_ID,
            "Id": ep_id,
            "Type": "Episode",
            "MediaType": "Video",
            "IsFolder": False,
            "RunTimeTicks": run_ticks,
            "Container": container,
            "Path": ep.get("path", ""),
            "SortName": f"{season_num:02d}x{ep_num:02d}" if ep_num else ep_name,
            "IndexNumber": ep_num,
            "ParentIndexNumber": season_num,
            "SeriesId": series_id,
            "SeriesName": series_path.split("/")[-1] if series_path else "",
            "SeasonId": season_id,
            "SeasonName": season_name,
            "UserData": {
                "PlaybackPositionTicks": ud.get("playback_position_ticks", 0),
                "PlayCount": ud.get("play_count", 0),
                "IsFavorite": bool(ud.get("is_favorite", False)),
                "Played": bool(ud.get("played", False)),
            },
            "MediaSources": [
                {
                    "Id": ep_id,
                    "Path": f"{host_base}/Videos/{ep_id}/stream.{container}",
                    "Protocol": "Http",
                    "Container": container,
                    "Size": file_size,
                    "Name": ep.get("episode_title") or ep_name,
                    "IsRemote": False,
                    "RunTimeTicks": run_ticks,
                    "SupportsTranscoding": False,
                    "SupportsDirectStream": True,
                    "SupportsDirectPlay": True,
                    "IsInfiniteStream": False,
                    "RequiresOpening": False,
                    "RequiresClosing": False,
                    "RequiresLooping": False,
                    "MediaStreams": [],
                }
            ],
        })

    result.sort(key=lambda e: (e.get("IndexNumber") or 0))
    return result
