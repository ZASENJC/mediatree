import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from ..config import fetch_safe_image, settings
from ..covers import (
    delete_continue_snapshot,
    find_local_episode_still,
    generate_video_still,
    get_continue_snapshot,
    should_use_continue_snapshot,
)
from ..database import get_movie_detail
from ..security import require_media_access
from ..stream import get_media_info, get_video_stream
from ..subtitles import find_external_audio_tracks

router = APIRouter()


def _safe_local_file(path_value: str | os.PathLike | None, allowed_roots: list[Path]) -> Path | None:
    if not path_value:
        return None
    try:
        p = Path(path_value)
        if not p.exists() or not p.is_file():
            return None
        real = p.resolve()
        for root in allowed_roots:
            try:
                if real.is_relative_to(root.resolve()):
                    return real
            except (OSError, ValueError):
                continue
    except (OSError, ValueError):
        return None
    return None


def _safe_image_roots() -> list[Path]:
    return [
        Path(settings.covers_dir),
        Path(settings.data_dir) / "stills",
        Path(settings.media_root),
    ]


@router.get("/api/stream/{movie_id}")
async def api_stream(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    return get_video_stream(movie["path"], request)


@router.get("/api/media-info/{movie_id}")
async def api_media_info(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    info = get_media_info(movie["path"])
    tracks = movie.get("external_audio_tracks") or []
    if not tracks:
        tracks = find_external_audio_tracks(movie["path"])
    info["external_audio_tracks"] = tracks
    return info


@router.get("/api/cover/{movie_id}")
async def api_cover(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    cover_key = movie.get("cover_local")
    if cover_key and "/" not in cover_key and "\\" not in cover_key:
        p = Path(settings.covers_dir) / f"{cover_key}.jpg"
        if p.exists():
            return FileResponse(p, headers={"Cache-Control": "no-store"})
    cover_path = movie.get("cover_local")
    local_cover = _safe_local_file(cover_path, _safe_image_roots())
    if local_cover:
        return FileResponse(local_cover, headers={"Cache-Control": "no-store"})
    remote = movie.get("cover_remote")
    fetched = await fetch_safe_image(remote, headers={"Referer": "https://www.javdatabase.com", "User-Agent": "Mozilla/5.0"}) if remote else None
    if fetched:
        content, content_type = fetched
        return Response(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": "no-store"},
        )
    generated = generate_video_still(movie["path"], cache_key=f"cover:{movie['path']}", at_seconds=1.0)
    if generated:
        return FileResponse(generated, headers={"Cache-Control": "no-store"})
    return Response(status_code=404, content="No cover available")


@router.get("/api/continue-cover/{movie_id}")
async def api_continue_cover(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not should_use_continue_snapshot(movie):
        raise HTTPException(status_code=404)
    snapshot = get_continue_snapshot(movie["path"])
    if snapshot:
        return FileResponse(snapshot, headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404)


@router.post("/api/continue-cover-reset/{movie_id}")
async def api_continue_cover_reset(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if should_use_continue_snapshot(movie):
        delete_continue_snapshot(movie["path"])
    return {"ok": True}


@router.get("/api/cached-cover/{cache_key}")
async def api_cached_cover(cache_key: str):
    safe_key = cache_key.replace("\\", "/").split("/")[-1].replace("\x00", "")
    if not safe_key or safe_key in (".", ".."):
        raise HTTPException(status_code=404)
    covers_root = Path(settings.covers_dir).resolve()
    p = (covers_root / f"{safe_key}.jpg").resolve()
    if not p.is_relative_to(covers_root) or not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(p)


@router.get("/api/episode-still/{movie_id}")
async def api_episode_still(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    for candidate in (movie.get("episode_still_local"), movie.get("episode_still")):
        if candidate and not str(candidate).startswith(("http://", "https://")):
            local = _safe_local_file(candidate, _safe_image_roots())
            if local:
                return FileResponse(local)
    remote = movie.get("episode_still")
    if remote and str(remote).startswith(("http://", "https://")):
        fetched = await fetch_safe_image(remote)
        if fetched:
            content, content_type = fetched
            return Response(content=content, media_type=content_type)
    local_still = find_local_episode_still(movie["path"])
    if local_still:
        return FileResponse(local_still)
    generated = generate_video_still(movie["path"])
    if generated:
        return FileResponse(generated)
    raise HTTPException(status_code=404)


@router.get("/api/thumbnail/{movie_id}/{index}")
async def api_thumbnail(movie_id: int, index: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    thumbs = movie.get("javdb_thumbnails", [])
    if not thumbs or index >= len(thumbs):
        raise HTTPException(status_code=404)
    fetched = await fetch_safe_image(thumbs[index], headers={"Referer": "https://www.javdatabase.com", "User-Agent": "Mozilla/5.0"})
    if fetched:
        content, content_type = fetched
        return Response(content=content, media_type=content_type)
    raise HTTPException(status_code=404)
