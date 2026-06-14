import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response

from ..config import logger
from ..database import get_movie_detail
from ..security import require_media_access
from ..subtitles import (
    extract_subtitle_stream_raw,
    find_external_subtitles,
    get_default_subtitle_font_path,
    get_subtitle_tracks,
    install_font,
    list_fonts,
    load_external_subtitle,
    remove_font,
    resolve_font_path,
)

router = APIRouter()


@router.get("/api/subtitle-tracks/{movie_id}")
async def api_subtitle_tracks(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    track_list = get_subtitle_tracks(movie["path"])
    external = find_external_subtitles(movie["path"])
    logger.info(
        f"Subtitle tracks count: movie_id={movie_id} embedded={len(track_list)} "
        f"external={len(external)} total={len(track_list) + len(external)}"
    )
    all_tracks = []
    for t in track_list:
        idx = t.get("index")
        codec = t.get("codec") or "unknown"
        all_tracks.append({
            **t,
            "format": t.get("format") or codec,
            "url": f"/api/subtitle/{movie_id}/{idx}",
            "source": "embedded",
            "is_external": False,
            "web_supported": codec.lower() in {"ass", "ssa", "srt", "subrip", "webvtt", "vtt", "mov_text"},
        })
    for i, t in enumerate(external):
        idx = 1000 + i
        fmt = t.get("format") or Path(t["path"]).suffix.lstrip(".")
        language = t.get("language", "und")
        logger.info(
            f"Subtitle track external: movie_id={movie_id} index={idx} "
            f"format={fmt} language={language} path='{t['path']}'"
        )
        all_tracks.append({
            "index": idx,
            "stream_index": -1,
            "codec": t.get("codec") or Path(t["path"]).suffix.lstrip("."),
            "language": language,
            "title": t.get("name", ""),
            "name": t.get("name", ""),
            "source": "external",
            "format": fmt,
            "url": f"/api/subtitle/{movie_id}/{idx}",
            "is_external": True,
            "web_supported": t.get("web_supported", False),
        })
    return all_tracks


@router.get("/api/subtitle/{movie_id}/{track_index}")
async def api_subtitle(movie_id: int, track_index: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    if track_index >= 1000:
        ext_idx = track_index - 1000
        ext_subs = find_external_subtitles(movie["path"])
        if ext_idx < len(ext_subs):
            content, media_type = load_external_subtitle(ext_subs[ext_idx]["path"])
            if content:
                return Response(
                    content=content, media_type=f"{media_type}; charset=utf-8",
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            logger.warning(f"Subtitle load failed for movie_id={movie_id} path={ext_subs[ext_idx]['path']}")
        raise HTTPException(status_code=404)
    track_list = get_subtitle_tracks(movie["path"])
    matching = [t for t in track_list if t["index"] == track_index]
    if matching:
        content, media_type = extract_subtitle_stream_raw(
            movie["path"], matching[0]["stream_index"], matching[0].get("codec", "")
        )
        if content:
            return Response(
                content=content, media_type=f"{media_type}; charset=utf-8",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        logger.warning(f"Embedded subtitle extraction failed for movie_id={movie_id} track={track_index}")
    raise HTTPException(status_code=404)


@router.get("/api/subtitle-content/{movie_id}/{track_index}")
async def api_subtitle_content(movie_id: int, track_index: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    if track_index >= 1000:
        ext_idx = track_index - 1000
        ext_subs = find_external_subtitles(movie["path"])
        if ext_idx < len(ext_subs):
            content, media_type = load_external_subtitle(ext_subs[ext_idx]["path"])
            if content:
                return Response(
                    content=content, media_type=f"{media_type}; charset=utf-8",
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            logger.warning(f"Subtitle content load failed for movie_id={movie_id} path={ext_subs[ext_idx]['path']}")
        raise HTTPException(status_code=404)
    track_list = get_subtitle_tracks(movie["path"])
    matching = [t for t in track_list if t["index"] == track_index]
    if matching:
        content, media_type = extract_subtitle_stream_raw(
            movie["path"], matching[0]["stream_index"], matching[0].get("codec", "")
        )
        if content:
            return Response(content=content, media_type=f"{media_type}; charset=utf-8")
        logger.warning(f"Embedded subtitle content extraction failed for movie_id={movie_id} track={track_index}")
    raise HTTPException(status_code=404)


@router.get("/api/subtitle-file/{movie_id}/{track_index}/{filename}")
async def api_subtitle_file(movie_id: int, track_index: int, filename: str, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    if track_index < 1000:
        raise HTTPException(status_code=404)
    ext_idx = track_index - 1000
    ext_subs = find_external_subtitles(movie["path"])
    if ext_idx >= len(ext_subs):
        raise HTTPException(status_code=404)
    p = Path(ext_subs[ext_idx]["path"])
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(p), filename=p.name, headers={"Access-Control-Allow-Origin": "*"})


@router.get("/api/external-play/{movie_id}.m3u")
async def api_external_play_playlist(movie_id: int, request: Request):
    require_media_access(request)
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    base = str(request.base_url).rstrip("/")
    if request.url.hostname in {"0.0.0.0", "::", "[::]"}:
        port = f":{request.url.port}" if request.url.port else ""
        base = f"{request.url.scheme}://127.0.0.1{port}"
    token_param = ""
    token = request.query_params.get("token") or ""
    if token:
        token_param = f"?token={quote(token)}"
    stream_url = f"{base}/api/stream/{movie_id}{token_param}"
    lines = ["#EXTM3U"]
    external = find_external_subtitles(movie["path"])
    for i, sub in enumerate(external):
        idx = 1000 + i
        name = quote(Path(sub["path"]).name)
        sub_url = f"{base}/api/subtitle-file/{movie_id}/{idx}/{name}{token_param}"
        lines.append(f"#EXTVLCOPT:sub-file={sub_url}")
        lines.append(f"#EXT-X-MPV-OPT:sub-file={sub_url}")
    lines.append(f"#EXTINF:-1,{movie.get('title') or movie.get('code') or Path(movie['path']).name}")
    lines.append(stream_url)
    return Response(
        content="\n".join(lines) + "\n",
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": f'attachment; filename="mediatree-{movie_id}.m3u"'},
    )


@router.get("/api/subtitle-fonts")
async def api_list_fonts():
    return {"fonts": list_fonts()}


def _font_media_type(path: Path) -> str | None:
    return {
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".ttc": "font/collection",
    }.get(path.suffix.lower())


@router.head("/api/subtitle-fonts/default")
@router.get("/api/subtitle-fonts/default")
async def api_default_subtitle_font():
    p = get_default_subtitle_font_path()
    if not p or not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(p), media_type=_font_media_type(p), headers={"Cache-Control": "public, max-age=86400"})


@router.post("/api/subtitle-fonts/upload")
async def api_upload_font(file: UploadFile = File(...)):
    if not file.filename or Path(file.filename).suffix.lower() not in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
        raise HTTPException(status_code=400, detail="Only font files allowed (.ttf, .otf, .ttc, .woff, .woff2)")
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = install_font(tmp_path)
        return {"ok": True, **result}
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass


@router.delete("/api/subtitle-fonts/{name}")
async def api_delete_font(name: str):
    if remove_font(name):
        return {"ok": True}
    raise HTTPException(status_code=404)


@router.head("/api/subtitle-fonts/{name:path}")
@router.get("/api/subtitle-fonts/{name:path}")
async def api_serve_font(name: str):
    p = resolve_font_path(name)
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(p), media_type=_font_media_type(p), headers={"Cache-Control": "public, max-age=86400"})
