import asyncio
import json as json_module
import mimetypes
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings, logger, setup_file_logging, is_safe_image_url
from .database import (
    init_db, close_db_pool, upsert_movie, get_movies, get_movie_detail,
    get_categories, save_category, delete_category, add_tag, remove_tag,
    delete_movie, search_movies, get_recent_watched, set_folder_tag,
    get_media_roots, get_folder_tree_from_db,
    get_library_passwords, set_library_password, verify_library_password_v2,
    get_all_library_settings, save_library_settings, has_any_library_setting,
    get_library_settings, save_progress, get_progress,
    get_review_queue, approve_review_item, clear_review_queue,
)
from .scanner import scan_media, scrape_for_library, run_scan_for_root, rescrape_movie, rescrape_movie_manual, rescrape_folder, rescrape_folder_manual, search_for_scrape, apply_folder_scrape_result, fetch_search_backdrops, change_folder_cover, change_folder_backdrop, edit_folder_movies, delete_folder_movies
from .javdb import search_javdb
from .stream import get_video_stream, get_media_info
from .subtitles import get_subtitle_tracks, find_external_subtitles, find_external_audio_tracks, extract_subtitle_stream_raw, load_external_subtitle, list_fonts, install_font, remove_font, get_fonts_dir, resolve_font_path, get_default_subtitle_font_path

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("font/collection", ".ttc")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/System") \
                or path.startswith("/Users") \
                or path.startswith("/Items") \
                or path.startswith("/Videos") \
                or path.startswith("/Sessions") \
                or path.startswith("/Shows") \
                or path.startswith("/Library") \
                or path.startswith("/DisplayPreferences") \
                or path.startswith("/Genres") \
                or path.startswith("/emby"):
            return await call_next(request)
        if not settings.auth_enabled:
            return await call_next(request)
        if path.startswith("/assets") \
                or path in ("/api/auth/login", "/api/auth/status", "/api/setup/status", "/api/health") \
                or path.startswith("/api/stream/") \
                or path.startswith("/api/cover/") \
                or path.startswith("/api/cached-cover/") \
                or path.startswith("/api/episode-still/") \
                or path.startswith("/api/thumbnail/") \
                or path.startswith("/api/subtitle-tracks/") \
                or path.startswith("/api/subtitle/") \
                or path.startswith("/api/subtitle-content/") \
                or path.startswith("/api/subtitle-file/") \
                or path.startswith("/api/external-play/") \
                or path.startswith("/fonts/") \
                or (path == "/api/subtitle-fonts" and request.method in ("GET", "HEAD")) \
                or (path.startswith("/api/subtitle-fonts/") and request.method in ("GET", "HEAD")) \
                or path.startswith("/api/media/"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {settings.auth_token}":
            return await call_next(request)
        if auth.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                user, _, pwd = decoded.partition(":")
                if user == settings.auth_user and pwd == settings.auth_pass:
                    return await call_next(request)
            except Exception:
                pass
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    setup_file_logging(settings.data_dir)
    from .jellyfin_compat import init_jellyfin
    await init_jellyfin()
    startup_task = None
    if settings.scan_on_startup and await has_any_library_setting():
        startup_task = asyncio.create_task(run_startup_scan())
    watch_task = None
    if os.environ.get("FILE_WATCHER_ENABLED", "true").lower() not in {"0", "false", "no"}:
        from .watcher import start_file_watcher
        watch_task = asyncio.create_task(start_file_watcher(startup_task))
    logger.info("MediaTree server started")
    yield
    if watch_task:
        watch_task.cancel()
    await close_db_pool()


async def run_startup_scan():
    try:
        await asyncio.sleep(1)
        if not await has_any_library_setting():
            logger.info("Startup scan skipped: setup has not been completed")
            return
        from .database import get_db, get_all_library_settings, save_library_settings
        db = await get_db()
        await db.execute("DELETE FROM movies WHERE media_root = ''")
        await db.commit()

        roots = settings.get_all_media_roots()
        if roots:
            # Auto-register library_settings for newly discovered media roots
            existing = await get_all_library_settings()
            existing_paths = {str(Path(s["media_root"])) for s in existing}
            for root in roots:
                if root not in existing_paths:
                    await save_library_settings({
                        "media_root": root,
                        "scraper": "auto",
                        "enabled": 1,
                    })
                    logger.info(f"Auto-registered new media root: {root}")

            await asyncio.gather(*(run_scan_for_root(root, trigger="startup") for root in roots))

        logger.info("Startup scan complete")
    except Exception as e:
        logger.error(f"Startup scan error: {e}")


app = FastAPI(title="MediaTree", lifespan=lifespan)

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .jellyfin_compat import router as jellyfin_router, EmbyPathRewriteMiddleware
app.include_router(jellyfin_router)

app.add_middleware(EmbyPathRewriteMiddleware)


# ─── Auth ───

@app.post("/api/auth/login")
async def api_auth_login(data: dict):
    user = data.get("username", "")
    pwd = data.get("password", "")
    if settings.auth_enabled:
        if user == settings.auth_user and pwd == settings.auth_pass:
            return {"token": settings.auth_token, "ok": True}
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": "", "ok": True}


@app.get("/api/auth/status")
async def api_auth_status():
    return {"need_auth": settings.auth_enabled}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def _require_enabled_media_root(media_root: str) -> dict | None:
    if not media_root:
        raise HTTPException(status_code=400, detail="media_root required")
    known_roots = set(settings.get_all_media_roots())
    if known_roots and media_root not in known_roots:
        logger.warning(f"media_root validation failed: unknown media_root='{media_root}'")
        raise HTTPException(status_code=404, detail="media_root not found")
    lib_setting = await get_library_settings(media_root)
    if lib_setting and not bool(lib_setting.get("enabled", 1)):
        logger.warning(f"media_root validation failed: disabled media_root='{media_root}'")
        raise HTTPException(status_code=400, detail="media_root disabled")
    return lib_setting


# ─── Scan ───

@app.get("/api/scan")
async def api_scan(media_root: str = Query("")):
    if media_root:
        await _require_enabled_media_root(media_root)
    roots = [media_root] if media_root else settings.get_all_media_roots()
    results = await asyncio.gather(*(run_scan_for_root(r, trigger="manual") for r in roots))
    total = sum(int(r.get("total") or 0) for r in results)
    return {"total": total, "roots": results, "all_codes_count": total}


@app.get("/api/scan/status")
async def api_scan_status(media_root: str = Query("")):
    from .scanner import _scan_progress
    if media_root and media_root in _scan_progress:
        return {"media_root": media_root, **_scan_progress[media_root]}
    if not media_root:
        return {"roots": {k: v for k, v in _scan_progress.items()}}
    return {"media_root": media_root, "status": "not_found", "done": 0, "total": 0}


@app.get("/api/scan/log")
async def api_scan_log(media_root: str = Query(""), lines: int = Query(100)):
    from pathlib import Path
    log_path = Path(settings.data_dir) / "logs" / "mediatree.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        return {"lines": [], "total": 0}
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        total = len(all_lines)
        if media_root:
            label = Path(media_root).name
            filtered = [l.rstrip() for l in all_lines if label in l]
            result = filtered[-lines:]
        else:
            result = [l.rstrip() for l in all_lines[-lines:]]
        return {"lines": result, "total": total}
    except Exception as e:
        return {"lines": [], "total": 0, "error": str(e)}


@app.post("/api/library/clear")
async def api_library_clear(data: dict):
    media_root = data.get("media_root", "")
    await _require_enabled_media_root(media_root)
    from .scanner import clear_library_scraped_data
    await clear_library_scraped_data(media_root)
    return {"ok": True, "message": f"Cleared scraped data for {media_root}"}


# ─── Setup Wizard ───

@app.get("/api/setup/status")
async def api_setup_status():
    return {"needs_setup": not await has_any_library_setting(), "roots": settings.get_all_media_roots()}


@app.post("/api/setup/save")
async def api_setup_save(data: dict):
    items = data.get("libraries", [])
    tmdb_token = (data.get("tmdb_access_token") or data.get("tmdb_token") or "").strip()
    if tmdb_token:
        settings.tmdb_access_token = tmdb_token.removeprefix("Bearer ").strip()
        settings.save_config()
    for item in items:
        pwd_hash = None
        if item.get("password"):
            from .database import _hash_password
            pwd_hash = _hash_password(item["password"])
        await save_library_settings({
            "media_root": item["media_root"],
            "scraper": item.get("scraper") or "auto",
            "tmdb_key": item.get("tmdb_key", ""),
            "password_hash": pwd_hash,
            "enabled": 1,
        })
    asyncio.create_task(run_startup_scan())
    return {"ok": True, "scan_started": True}


# ─── Library Settings ───

@app.get("/api/library-settings")
async def api_library_settings():
    return await get_all_library_settings()


@app.post("/api/library-settings")
async def api_save_library_setting(data: dict):
    if not data.get("media_root"):
        raise HTTPException(status_code=400, detail="media_root required")
    await save_library_settings(data)
    return {"ok": True}


# ─── Folders / Search / Movies / Favorites / Detail ───

@app.get("/api/folders")
async def api_folders(media_root: str = Query("")):
    return {"tree": await get_folder_tree_from_db(media_root=media_root)}


@app.get("/api/search")
async def api_search(q: str = Query(""), media_root: str = Query(""), limit: int = Query(100), offset: int = Query(0), field: str = Query("")):
    if not q:
        return {"movies": [], "total": 0}
    return await search_movies(q, media_root=media_root, limit=limit, offset=offset, field=field)


@app.get("/api/movies")
async def api_movies(folder: str = Query(""), tag: str = Query(""), code: str = Query(""),
                     actress: str = Query(""), staff: str = Query(""), category_id: int = Query(0), media_root: str = Query(""),
                     sort: str = Query("created_desc"), limit: int = Query(50), offset: int = Query(0)):
    return await get_movies(folder=folder, tag=tag, code=code, actress=actress, staff=staff,
                            media_root=media_root, category_id=category_id, sort=sort,
                            limit=limit, offset=offset)


@app.get("/api/favorites")
async def api_favorites(media_root: str = Query(""), sort: str = Query("created_desc"),
                        limit: int = Query(50), offset: int = Query(0)):
    return await get_movies(tag="favorite", media_root=media_root, sort=sort, limit=limit, offset=offset)


@app.get("/api/detail/{movie_id}")
async def api_detail(movie_id: int):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@app.get("/api/progress/{movie_id}")
async def api_get_progress(movie_id: int):
    return await get_progress(movie_id)


@app.post("/api/progress/{movie_id}")
async def api_save_progress(movie_id: int, data: dict):
    return await save_progress(
        movie_id,
        float(data.get("position") or 0),
        float(data.get("duration") or 0) if data.get("duration") is not None else None,
        bool(data.get("stopped", False)),
    )


# ─── Stream / Cover / Thumbnail ───

@app.get("/api/stream/{movie_id}")
async def api_stream(movie_id: int, request: Request):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    return get_video_stream(movie["path"], request)


@app.get("/api/media-info/{movie_id}")
async def api_media_info(movie_id: int):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    info = get_media_info(movie["path"])
    tracks = movie.get("external_audio_tracks") or []
    if not tracks:
        tracks = find_external_audio_tracks(movie["path"])
    info["external_audio_tracks"] = tracks
    return info


@app.get("/api/cover/{movie_id}")
async def api_cover(movie_id: int):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    cover_key = movie.get("cover_local")
    if cover_key and "/" not in cover_key and "\\" not in cover_key:
        p = Path(settings.covers_dir) / f"{cover_key}.jpg"
        if p.exists():
            return FileResponse(p, headers={"Cache-Control": "no-store"})
    cover_path = movie.get("cover_local")
    if cover_path and Path(cover_path).exists():
        return FileResponse(cover_path, headers={"Cache-Control": "no-store"})
    remote = movie.get("cover_remote")
    if remote and is_safe_image_url(remote):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(remote, headers={"Referer": "https://www.javdatabase.com", "User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    return Response(
                        content=resp.content,
                        media_type=resp.headers.get("content-type", "image/jpeg"),
                        headers={"Cache-Control": "no-store"},
                    )
        except Exception:
            pass
    return Response(status_code=404, content="No cover available")


@app.get("/api/cached-cover/{cache_key}")
async def api_cached_cover(cache_key: str):
    from .config import settings
    p = Path(settings.covers_dir) / f"{cache_key}.jpg"
    if p.exists():
        return FileResponse(p)
    raise HTTPException(status_code=404)


@app.get("/api/episode-still/{movie_id}")
async def api_episode_still(movie_id: int):
    from .covers import find_local_episode_still, generate_video_still

    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    for candidate in (movie.get("episode_still_local"), movie.get("episode_still")):
        if candidate and not str(candidate).startswith(("http://", "https://")):
            local = Path(candidate)
            if local.exists():
                return FileResponse(local)
    remote = movie.get("episode_still")
    if remote and str(remote).startswith(("http://", "https://")):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(remote)
                if resp.status_code == 200:
                    return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
        except Exception:
            pass
    local_still = find_local_episode_still(movie["path"])
    if local_still:
        return FileResponse(local_still)
    generated = generate_video_still(movie["path"])
    if generated:
        return FileResponse(generated)
    raise HTTPException(status_code=404)


@app.get("/api/thumbnail/{movie_id}/{index}")
async def api_thumbnail(movie_id: int, index: int):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    thumbs = movie.get("javdb_thumbnails", [])
    if not thumbs or index >= len(thumbs):
        raise HTTPException(status_code=404)
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(thumbs[index], headers={"Referer": "https://www.javdatabase.com", "User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
    except Exception:
        pass
    raise HTTPException(status_code=404)


# ─── Subtitle ───

@app.get("/api/subtitle-tracks/{movie_id}")
async def api_subtitle_tracks(movie_id: int):
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
            "path": movie["path"],
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
            "path": t["path"],
            "format": fmt,
            "url": f"/api/subtitle/{movie_id}/{idx}",
            "is_external": True,
            "web_supported": t.get("web_supported", False),
        })
    return all_tracks


@app.get("/api/subtitle/{movie_id}/{track_index}")
async def api_subtitle(movie_id: int, track_index: int):
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


@app.get("/api/subtitle-content/{movie_id}/{track_index}")
async def api_subtitle_content(movie_id: int, track_index: int):
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


@app.get("/api/subtitle-file/{movie_id}/{track_index}/{filename}")
async def api_subtitle_file(movie_id: int, track_index: int, filename: str):
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


@app.get("/api/external-play/{movie_id}.m3u")
async def api_external_play_playlist(movie_id: int, request: Request):
    from urllib.parse import quote
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    base = str(request.base_url).rstrip("/")
    if request.url.hostname in {"0.0.0.0", "::", "[::]"}:
        port = f":{request.url.port}" if request.url.port else ""
        base = f"{request.url.scheme}://127.0.0.1{port}"
    stream_url = f"{base}/api/stream/{movie_id}"
    lines = ["#EXTM3U"]
    external = find_external_subtitles(movie["path"])
    for i, sub in enumerate(external):
        idx = 1000 + i
        name = quote(Path(sub["path"]).name)
        sub_url = f"{base}/api/subtitle-file/{movie_id}/{idx}/{name}"
        lines.append(f"#EXTVLCOPT:sub-file={sub_url}")
        lines.append(f"#EXT-X-MPV-OPT:sub-file={sub_url}")
    lines.append(f"#EXTINF:-1,{movie.get('title') or movie.get('code') or Path(movie['path']).name}")
    lines.append(stream_url)
    return Response(
        content="\n".join(lines) + "\n",
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": f'attachment; filename="mediatree-{movie_id}.m3u"'},
    )


@app.get("/api/subtitle-fonts")
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


@app.head("/api/subtitle-fonts/default")
@app.get("/api/subtitle-fonts/default")
async def api_default_subtitle_font():
    p = get_default_subtitle_font_path()
    if not p or not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(p), media_type=_font_media_type(p), headers={"Cache-Control": "public, max-age=86400"})


@app.post("/api/subtitle-fonts/upload")
async def api_upload_font(file: UploadFile = File(...)):
    import tempfile
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


@app.delete("/api/subtitle-fonts/{name}")
async def api_delete_font(name: str):
    if remove_font(name):
        return {"ok": True}
    raise HTTPException(status_code=404)


@app.head("/api/subtitle-fonts/{name:path}")
@app.get("/api/subtitle-fonts/{name:path}")
async def api_serve_font(name: str):
    p = resolve_font_path(name)
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(p), media_type=_font_media_type(p), headers={"Cache-Control": "public, max-age=86400"})


# ─── Config ───

def _mask_sensitive(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return value[:2] + "***"
    return value[:4] + "***" + value[-4:]


@app.get("/api/config")
async def api_get_config():
    return {
        "javdb_enabled": settings.javdb_enabled,
        "javdb_base_url": settings.javdb_base_url,
        "javdb_cache_hours": settings.javdb_cache_hours,
        "javdb_request_interval": settings.javdb_request_interval,
        "tmdb_cache_hours": getattr(settings, 'tmdb_cache_hours', 168),
        "bangumi_cache_hours": getattr(settings, 'bangumi_cache_hours', 168),
        "tmdb_api_key": _mask_sensitive(settings.tmdb_api_key),
        "tmdb_access_token": _mask_sensitive(settings.tmdb_access_token),
        "scrape_concurrency_per_library": settings.scrape_concurrency_per_library,
        "scrape_global_concurrency": settings.scrape_global_concurrency,
        "scraper_api_concurrency": settings.scraper_api_concurrency,
        "scraper_http_timeout": settings.scraper_http_timeout,
        "media_root": settings.media_root,
    }


@app.post("/api/config")
async def api_update_config(data: dict):
    if "javdb_enabled" in data:
        settings.javdb_enabled = data["javdb_enabled"]
    if "javdb_base_url" in data:
        settings.javdb_base_url = data["javdb_base_url"]
    if "javdb_cache_hours" in data:
        settings.javdb_cache_hours = data["javdb_cache_hours"]
    if "javdb_request_interval" in data:
        settings.javdb_request_interval = data["javdb_request_interval"]
    if "tmdb_cache_hours" in data:
        settings.tmdb_cache_hours = data["tmdb_cache_hours"]
    if "bangumi_cache_hours" in data:
        settings.bangumi_cache_hours = data["bangumi_cache_hours"]
    if "tmdb_api_key" in data:
        val = data["tmdb_api_key"]
        if val and "***" not in val:
            settings.tmdb_api_key = val
    if "tmdb_access_token" in data:
        val = data["tmdb_access_token"]
        if val and "***" not in val:
            settings.tmdb_access_token = val
    if "scrape_concurrency_per_library" in data:
        settings.scrape_concurrency_per_library = int(data["scrape_concurrency_per_library"])
    if "scrape_global_concurrency" in data:
        settings.scrape_global_concurrency = int(data["scrape_global_concurrency"])
    if "scraper_api_concurrency" in data:
        settings.scraper_api_concurrency = int(data["scraper_api_concurrency"])
    if "scraper_http_timeout" in data:
        settings.scraper_http_timeout = float(data["scraper_http_timeout"])
    settings.save_config()
    return {"ok": True}


# ─── Backup / Restore ───

@app.get("/api/backup")
async def api_backup(backup_type: str = Query("core")):
    import sqlite3
    from pathlib import Path

    db_path = Path(settings.db_path)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    backup_dir = Path(settings.data_dir) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")

    if backup_type == "full":
        import tarfile
        import io
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(db_path), arcname="browser.db")
            covers_dir = Path(settings.covers_dir)
            if covers_dir.exists():
                tar.add(str(covers_dir), arcname="covers")
            stills_dir = Path(settings.data_dir) / "stills"
            if stills_dir.exists():
                tar.add(str(stills_dir), arcname="stills")
        buf.seek(0)
        from fastapi.responses import Response
        return Response(
            content=buf.getvalue(),
            media_type="application/gzip",
            headers={"Content-Disposition": f"attachment; filename=mediatree_full_{timestamp}.tar.gz"},
        )

    backup_path = backup_dir / f"mediatree_backup_{timestamp}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return FileResponse(
        str(backup_path),
        media_type="application/octet-stream",
        filename=f"mediatree_backup_{timestamp}.db",
    )


@app.post("/api/restore")
async def api_restore(data: dict):
    import shutil
    from pathlib import Path

    file_path = data.get("path", "")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=400, detail="Backup file not found")

    backup_source = Path(file_path)
    suffix = backup_source.suffix

    if suffix == ".gz":
        import tarfile
        await close_db_pool()
        try:
            with tarfile.open(str(backup_source), "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name == "browser.db":
                        tar.extract(member, str(Path(settings.data_dir)))
                    elif member.name.startswith("covers"):
                        covers_dir = Path(settings.covers_dir)
                        covers_dir.mkdir(parents=True, exist_ok=True)
                        tar.extract(member, str(Path(settings.data_dir)))
                    elif member.name.startswith("stills"):
                        stills_dir = Path(settings.data_dir) / "stills"
                        stills_dir.mkdir(parents=True, exist_ok=True)
                        tar.extract(member, str(Path(settings.data_dir)))
        finally:
            from . import database as db_module
            db_module._db_pool = None
            await init_db()
        return {"ok": True, "message": "Full backup restored successfully"}

    if suffix == ".db":
        await close_db_pool()
        shutil.copy2(str(backup_source), str(Path(settings.db_path)))
        from . import database as db_module
        db_module._db_pool = None
        await init_db()
        return {"ok": True, "message": "Database restored successfully"}

    raise HTTPException(status_code=400, detail="Invalid backup file")


@app.post("/api/restore/upload")
async def api_restore_upload(file: UploadFile = None):
    import shutil
    import tempfile
    from pathlib import Path

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    suffix = Path(file.filename).suffix
    if suffix not in (".db", ".gz"):
        raise HTTPException(status_code=400, detail="Invalid file type, expected .db or .tar.gz")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if suffix == ".gz":
            import tarfile
            await close_db_pool()
            try:
                with tarfile.open(tmp_path, "r:gz") as tar:
                    for member in tar.getmembers():
                        if member.name == "browser.db":
                            tar.extract(member, str(Path(settings.data_dir)))
                        elif member.name.startswith("covers") and not member.isdir():
                            tar.extract(member, str(Path(settings.data_dir)))
                        elif member.name.startswith("stills") and not member.isdir():
                            stills_dir = Path(settings.data_dir) / "stills"
                            stills_dir.mkdir(parents=True, exist_ok=True)
                            tar.extract(member, str(Path(settings.data_dir)))
            finally:
                from . import database as db_module
                db_module._db_pool = None
                await init_db()
        elif suffix == ".db":
            await close_db_pool()
            shutil.copy2(tmp_path, str(Path(settings.db_path)))
            from . import database as db_module
            db_module._db_pool = None
            await init_db()
    finally:
        try: Path(tmp_path).unlink()
        except Exception: pass

    return {"ok": True, "message": "Backup restored successfully"}


# ─── Recent Watched ───

@app.get("/api/recent-watched")
async def api_recent_watched(media_root: str = Query(""), limit: int = Query(200), offset: int = Query(0)):
    return await get_recent_watched(media_root=media_root, limit=limit, offset=offset)


# ─── Auth Change Password ───

@app.post("/api/auth/change-password")
async def api_change_password(request: Request, data: dict):
    old_user = data.get("old_username", "")
    old_pass = data.get("old_password", "")
    new_user = data.get("new_username", "")
    new_pass = data.get("new_password", "")

    if settings.auth_enabled:
        # Verify both token and old password to prevent token-only attacks
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.auth_token}" and not (
            auth.startswith("Basic ") and old_user == settings.auth_user and old_pass == settings.auth_pass
        ):
            logger.warning("Change password rejected: invalid auth or old credentials")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if old_user != settings.auth_user or old_pass != settings.auth_pass:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    settings.auth_user = new_user
    settings.auth_pass = new_pass
    settings.save_config()
    return {"ok": True}


# ─── Movie Rescrape ───

@app.post("/api/movies/{movie_id}/rescrape")
async def api_movie_rescrape(movie_id: int):
    result = await rescrape_movie(movie_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scrape failed"))
    return result


@app.post("/api/movies/{movie_id}/manual-scrape")
async def api_movie_manual_scrape(movie_id: int, data: dict):
    query = data.get("query", "")
    source_id = data.get("source_id", "")
    media_type = data.get("media_type", "movie")
    scraper = data.get("scraper")
    if not query and not source_id:
        raise HTTPException(status_code=400, detail="query or source_id required")
    result = await rescrape_movie_manual(movie_id, query, scraper, source_id, media_type)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scrape failed"))
    return result


# ─── Folder Rescrape ───

@app.post("/api/rescrape-folder")
async def api_rescrape_folder(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    if not folder:
        raise HTTPException(status_code=400, detail="folder required")
    await _require_enabled_media_root(media_root)
    logger.info(f"rescrape-folder request: folder='{folder}' media_root='{media_root}'")
    result = await rescrape_folder(folder, media_root)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scrape failed"))
    return result


# ─── Search Scrape ───

@app.post("/api/search-scrape")
async def api_search_scrape(data: dict):
    query = data.get("query", "")
    scraper = data.get("scraper", "tmdb_movie")
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    results = await search_for_scrape(query, scraper)
    return {"results": results}


# ─── Folder Manual Rescrape ───

@app.post("/api/rescrape-folder-manual")
async def api_rescrape_folder_manual(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    query = data.get("query", "")
    scraper = data.get("scraper", "")
    if not folder or not query:
        raise HTTPException(status_code=400, detail="folder and query required")
    await _require_enabled_media_root(media_root)
    logger.info(
        f"rescrape-folder-manual request: folder='{folder}' media_root='{media_root}' "
        f"scraper='{scraper or 'library-default'}' query='{query}'"
    )
    result = await rescrape_folder_manual(folder, media_root, query, scraper)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scrape failed"))
    return result


# ─── Apply Folder Scrape Result ───

@app.post("/api/apply-folder-scrape")
async def api_apply_folder_scrape(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    source_id = str(data.get("source_id", ""))
    source = data.get("source", "tmdb")
    media_type = data.get("media_type", "movie")
    logger.info(f"apply-folder-scrape: folder='{folder}' media_root='{media_root}' source_id='{source_id}' source='{source}' media_type='{media_type}'")
    if not folder or not source_id:
        raise HTTPException(status_code=400, detail="folder and source_id required")
    await _require_enabled_media_root(media_root)
    result = await apply_folder_scrape_result(folder, media_root, source_id, source, media_type)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Apply failed"))
    return result


# ─── Search Backdrops ───

@app.post("/api/search-backdrops")
async def api_search_backdrops(data: dict):
    results = data.get("results", [])
    if not results:
        return {"backdrops": []}
    backdrops = await fetch_search_backdrops(results)
    return {"backdrops": backdrops}


# ─── Folder Backdrop ───

@app.post("/api/folder/backdrop")
async def api_folder_backdrop(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    url = data.get("url", "")
    if not folder:
        raise HTTPException(status_code=400, detail="folder required")
    await _require_enabled_media_root(media_root)
    result = await change_folder_backdrop(folder, media_root, url)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed"))
    return result


# ─── Folder Cover ───

@app.post("/api/folder/cover")
async def api_folder_cover(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    cover_url = data.get("url", "")
    if not folder or not cover_url:
        raise HTTPException(status_code=400, detail="folder and url required")
    await _require_enabled_media_root(media_root)
    result = await change_folder_cover(folder, media_root, cover_url)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Cover change failed"))
    return result


# ─── Folder Edit ───

@app.put("/api/folder/edit")
async def api_folder_edit(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    fields = data.get("fields", {})
    if not folder:
        raise HTTPException(status_code=400, detail="folder required")
    await _require_enabled_media_root(media_root)
    result = await edit_folder_movies(folder, media_root, fields)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Edit failed"))
    return result


# ─── Folder Delete ───

@app.post("/api/folder/delete")
async def api_folder_delete(data: dict):
    folder = data.get("folder", "")
    media_root = data.get("media_root", "")
    if not folder:
        raise HTTPException(status_code=400, detail="folder required")
    await _require_enabled_media_root(media_root)
    result = await delete_folder_movies(folder, media_root)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Delete failed"))
    return result


# ─── Folder Watched ───

@app.post("/api/folder/watched")
async def api_folder_watched(data: dict):
    path = data.get("folder", "")
    media_root = data.get("media_root", "")
    watched = data.get("watched", True)
    if not path:
        raise HTTPException(status_code=400, detail="folder required")
    if media_root:
        await _require_enabled_media_root(media_root)
    await set_folder_tag(path, "watched", watched, media_root)
    return {"ok": True}


# ─── Alternative Covers ───

@app.get("/api/movies/{movie_id}/alternative-covers")
async def api_alternative_covers(movie_id: int):
    from .database import get_db
    from .tmdb import fetch_tmdb_detail, fetch_tmdb_images, search_tmdb

    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)

    alternatives = []
    tmdb_id = movie.get("tmdb_id")
    tmdb_type = movie.get("tmdb_type")

    if tmdb_id and tmdb_type:
        # Fetch all TMDB posters
        images = await fetch_tmdb_images(int(tmdb_id), tmdb_type)
        if images and images.get("posters"):
            lang_priority = {"zh": 0, "en": 1, "ja": 2, "ko": 3}
            def _sort_key(p):
                lang = p.get("language") or ""
                return (lang_priority.get(lang, 99), -(p.get("vote_count") or 0))
            for p in sorted(images["posters"], key=_sort_key):
                alternatives.append({
                    "url": p["url"],
                    "source": "tmdb_poster",
                    "width": p.get("width"),
                    "height": p.get("height"),
                    "language": p.get("language"),
                    "vote_count": p.get("vote_count"),
                })

        # Backdrops
        if images and images.get("backdrops"):
            for b in images["backdrops"][:5]:
                alternatives.append({
                    "url": b["url"],
                    "source": "tmdb_backdrop",
                    "width": b.get("width"),
                    "height": b.get("height"),
                })

    if movie.get("cover_remote"):
        alternatives.append({"url": movie["cover_remote"], "source": "current"})

    return {"covers": alternatives}


# ─── Change Cover ───

@app.post("/api/movies/{movie_id}/cover")
async def api_movie_change_cover(movie_id: int, data: dict = None, file: UploadFile = File(None)):
    from .database import get_db
    from .covers import download_and_compress_cover
    import hashlib

    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)

    new_cover_url = None
    if data and data.get("url"):
        new_cover_url = data["url"]

    if file and file.filename:
        import tempfile
        cover_dir = Path(settings.covers_dir)
        cover_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        try:
            from PIL import Image
            img = Image.open(tmp_path).convert("RGB")
            cache_key = hashlib.md5(content).hexdigest()[:16]
            out_path = cover_dir / f"{cache_key}.jpg"
            img.save(str(out_path), "JPEG", quality=80)
            db = await get_db()
            await db.execute(
                "UPDATE movies SET cover_local=?, cover_remote=NULL, updated_at=datetime('now') WHERE id=?",
                (cache_key, movie_id)
            )
            await db.commit()
        finally:
            try: Path(tmp_path).unlink()
            except: pass
        return {"ok": True, "cover_local": cache_key}

    if new_cover_url:
        cache_key = hashlib.md5(new_cover_url.encode()).hexdigest()[:16]
        cached = await download_and_compress_cover(new_cover_url, cache_key)
        db = await get_db()
        await db.execute(
            "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE id=?",
            (new_cover_url, cached or "", movie_id)
        )
        await db.commit()
        return {"ok": True, "cover_local": cached, "cover_remote": new_cover_url}

    raise HTTPException(status_code=400, detail="No cover source provided")


# ─── Edit Movie ───

@app.put("/api/movies/{movie_id}")
async def api_edit_movie(movie_id: int, data: dict):
    from .database import get_db
    db = await get_db()
    fields = ["title", "code", "actress", "release_date", "duration"]
    updates = []
    params = []
    for f in fields:
        if f in data:
            updates.append(f"{f}=?")
            params.append(data[f])
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at=datetime('now')")
    params.append(movie_id)
    await db.execute(
        f"UPDATE movies SET {', '.join(updates)} WHERE id=?",
        params
    )
    await db.commit()
    return {"ok": True}


# ─── Plugins ───

@app.get("/api/plugins/list")
async def api_plugins_list():
    from .plugins.manager import get_installed_plugins
    return {"plugins": get_installed_plugins()}


@app.post("/api/plugins/upload")
async def api_plugins_upload(file: UploadFile = File(...)):
    import tempfile
    import re
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files allowed")

    content = await file.read()
    if len(content) > 100 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 100KB)")

    text = content.decode("utf-8", errors="replace")
    blocked = ("os.system", "subprocess.", "shutil.rmtree", "shutil.move", "__import__(",
               "exec(", "eval(", "compile(", "ctypes.", "multiprocessing.")
    for pattern in blocked:
        if pattern in text:
            raise HTTPException(status_code=400, detail=f"Blocked pattern: {pattern}")

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from .plugins.manager import install_plugin
        result = install_plugin(tmp_path)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Install failed"))
        return result
    finally:
        try: Path(tmp_path).unlink()
        except: pass


@app.delete("/api/plugins/{name}")
async def api_plugins_delete(name: str):
    from .plugins.manager import remove_plugin
    if remove_plugin(name):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Plugin not found")


# ─── Media Roots ───

@app.get("/api/media-roots")
async def api_media_roots():
    roots = settings.get_all_media_roots()
    stats = await get_media_roots()
    passwords = await get_library_passwords()
    lib_settings = {s["media_root"]: s for s in await get_all_library_settings()}
    locked_set = {p["media_root"] for p in passwords}
    items = []
    for r in roots:
        ls = lib_settings.get(r, {})
        items.append({
            "path": r,
            "label": Path(r).name,
            "movie_count": next((s["movie_count"] for s in stats if s["path"] == r), 0),
            "locked": r in locked_set or bool(ls.get("password_hash")),
            "scraper": ls.get("scraper", "auto"),
        })
    if not items:
        items.append({"path": settings.media_root, "label": "media", "movie_count": 0, "locked": False, "scraper": "auto"})
    return {"items": items}


# ─── Library Passwords ───

@app.get("/api/library-passwords")
async def api_library_passwords():
    return await get_library_passwords()


@app.post("/api/library-passwords")
async def api_set_library_password(data: dict):
    mr = data.get("media_root", "")
    if not mr:
        raise HTTPException(status_code=400)
    await set_library_password(mr, data.get("password", ""))
    return {"ok": True}


@app.post("/api/library-verify")
async def api_verify_library(data: dict):
    mr = data.get("media_root", "")
    if not mr:
        raise HTTPException(status_code=400)
    return {"ok": await verify_library_password_v2(mr, data.get("password", ""))}


# ─── JavDB ───

@app.post("/api/javdb/fetch")
async def api_javdb_fetch(code: str = Query(...)):
    data = await search_javdb(code)
    return data if data else {"error": "Not found"}


# ─── Categories ───

@app.get("/api/categories")
async def api_categories():
    return await get_categories()


@app.post("/api/categories")
async def api_create_category(data: dict):
    return await save_category(data)


@app.put("/api/categories/{cat_id}")
async def api_update_category(cat_id: int, data: dict):
    data["id"] = cat_id
    return await save_category(data)


@app.delete("/api/categories/{cat_id}")
async def api_delete_category(cat_id: int):
    await delete_category(cat_id)
    return {"ok": True}


# ─── Tags ───

@app.post("/api/movies/{movie_id}/tags")
async def api_add_tag(movie_id: int, data: dict):
    tag = data.get("tag", "")
    if not tag:
        raise HTTPException(status_code=400)
    await add_tag(movie_id, tag)
    return {"ok": True}


@app.delete("/api/movies/{movie_id}/tags/{tag}")
async def api_remove_tag(movie_id: int, tag: str):
    await remove_tag(movie_id, tag)
    return {"ok": True}


@app.delete("/api/movies/{movie_id}")
async def api_delete_movie(movie_id: int):
    await delete_movie(movie_id)
    return {"ok": True}


# ─── Review Queue ───

@app.get("/api/review-queue")
async def api_review_queue(limit: int = 50, offset: int = 0):
    """List movies pending review (relaxed accept results)."""
    return await get_review_queue(limit=limit, offset=offset)


@app.post("/api/review-queue/{movie_id}/approve")
async def api_approve_review(movie_id: int):
    """Approve a single pending review item (clears the flag)."""
    await approve_review_item(movie_id)
    return {"ok": True}


@app.post("/api/review-queue/clear")
async def api_clear_review_queue():
    """Clear all pending review flags at once."""
    await clear_review_queue()
    return {"ok": True}


# ─── Static Media ───

@app.get("/api/media/{file_path:path}")
async def api_media_file(file_path: str, request: Request):
    full_path = Path(settings.media_root) / file_path
    try:
        real = full_path.resolve()
        root = Path(settings.media_root).resolve()
        if not real.is_relative_to(root) or not real.exists():
            raise HTTPException(status_code=404)
    except (OSError, ValueError):
        raise HTTPException(status_code=404)
    # Check library password protection for files under media roots
    from .database import get_library_passwords, verify_library_password_v2
    for lib in await get_library_passwords():
        lib_root = Path(lib["media_root"]).resolve()
        try:
            if real.is_relative_to(lib_root) or str(real).startswith(str(lib_root)):
                # Check for library password - if set, require auth
                auth = request.headers.get("Authorization", "")
                valid = False
                if auth == f"Bearer {settings.auth_token}":
                    valid = True
                elif auth.startswith("Basic "):
                    import base64
                    try:
                        decoded = base64.b64decode(auth[6:]).decode()
                        user, _, pwd = decoded.partition(":")
                        if user == settings.auth_user and pwd == settings.auth_pass:
                            valid = True
                    except Exception:
                        pass
                # If auth is not valid, check library-specific password via query param or header
                if not valid:
                    lib_pwd = request.query_params.get("pwd") or request.headers.get("X-Library-Password", "")
                    if not lib_pwd or not await verify_library_password_v2(lib["media_root"], lib_pwd):
                        raise HTTPException(status_code=401, detail="Library password required")
                break
        except HTTPException:
            raise
        except (ValueError, AttributeError):
            pass
    return FileResponse(real)




# ─── TMDB API Endpoints ───


@app.get("/api/folder-backdrops")
async def api_folder_backdrops(path: str = Query(""), media_root: str = Query("")):
    """Return TMDB backdrops for a folder using its scraped tmdb_id."""
    from .tmdb import fetch_tmdb_images
    from .database import get_db
    import re
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    if not path:
        return {"backdrops": []}
    db = await get_db()
    mr_where = " AND media_root=?" if media_root else ""
    mr_params = [media_root] if media_root else []
    # Try exact match first, then prefix match (for child folder movies)
    cur = await db.execute(
        f"SELECT tmdb_id, tmdb_type, folder_levels FROM movies WHERE folder_levels=?{mr_where} AND tmdb_id IS NOT NULL LIMIT 1",
        [path] + mr_params
    )
    row = await cur.fetchone()
    if not row:
        cur = await db.execute(
            f"SELECT tmdb_id, tmdb_type, folder_levels FROM movies WHERE folder_levels LIKE ?{mr_where} AND tmdb_id IS NOT NULL LIMIT 1",
            [path + "/%"] + mr_params
        )
        row = await cur.fetchone()
    # Fallback: parse [tmdbid=NNN] from folder_levels if tmdb_id column is NULL
    if not row or not row["tmdb_id"]:
        cur = await db.execute(
            f"SELECT folder_levels FROM movies WHERE (folder_levels=? OR folder_levels LIKE ?){mr_where} LIMIT 1",
            [path, path + "/%"] + mr_params
        )
        row2 = await cur.fetchone()
        if row2:
            m = re.search(r'\[tmdbid=(\d+)\]', row2["folder_levels"] or "", re.IGNORECASE)
            if m:
                tmdb_type = "tv" if re.search(r'\[tmdbtype=tv\]', row2["folder_levels"] or "", re.IGNORECASE) else "movie"
                result = await fetch_tmdb_images(int(m.group(1)), tmdb_type)
                return {"backdrops": (result or {}).get("backdrops", [])}
        return {"backdrops": []}
    result = await fetch_tmdb_images(row["tmdb_id"], row["tmdb_type"] or "movie")
    return {"backdrops": (result or {}).get("backdrops", [])}


@app.get("/api/tmdb-images/{tmdb_id}")
async def api_tmdb_images(tmdb_id: int, media_type: str = Query("movie")):
    """Return all posters, backdrops, logos for a movie or TV series."""
    from .tmdb import fetch_tmdb_images
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_tmdb_images(tmdb_id, media_type)
    return result or {"posters": [], "backdrops": [], "logos": []}


@app.get("/api/tmdb-videos/{tmdb_id}")
async def api_tmdb_videos(tmdb_id: int, media_type: str = Query("movie")):
    """Return trailers, clips, behind-the-scenes videos."""
    from .tmdb import fetch_tmdb_videos
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_tmdb_videos(tmdb_id, media_type)
    return result or {"results": []}


@app.get("/api/person/{person_id}")
async def api_person_detail(person_id: int):
    """Return person biography, birthday, external IDs."""
    from .tmdb import fetch_person_detail
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_person_detail(person_id)
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@app.get("/api/person/{person_id}/credits")
async def api_person_credits(person_id: int):
    """Return combined movie + TV credits for a person."""
    from .tmdb import fetch_person_credits
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_person_credits(person_id)
    return result or {"cast": [], "crew": []}


@app.get("/api/person-images/{person_id}")
async def api_person_images(person_id: int):
    """Return profile photos for a person."""
    from .tmdb import fetch_person_images
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_person_images(person_id)
    return result or {"profiles": []}


@app.get("/api/tmdb-reviews/{tmdb_id}")
async def api_tmdb_reviews(tmdb_id: int, media_type: str = Query("movie"), page: int = Query(1)):
    """Return user reviews for a movie or TV series."""
    from .tmdb import fetch_tmdb_reviews
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_tmdb_reviews(tmdb_id, media_type, page=page)
    return result or {"results": [], "page": 1, "total_pages": 0, "total_results": 0}


@app.get("/api/tmdb-keywords/{tmdb_id}")
async def api_tmdb_keywords(tmdb_id: int, media_type: str = Query("movie")):
    """Return keyword list for a movie or TV series."""
    from .tmdb import fetch_tmdb_keywords
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_tmdb_keywords(tmdb_id, media_type)
    return result or {"keywords": []}


@app.get("/api/release-dates/{tmdb_id}")
async def api_release_dates(tmdb_id: int):
    """Return release dates and certifications by country for a movie."""
    from .tmdb import fetch_release_dates
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_release_dates(tmdb_id)
    return result or {"results": []}


@app.get("/api/season-images/{series_id}/{season_num}")
async def api_season_images(series_id: int, season_num: int):
    """Return poster images for a TV season."""
    from .tmdb import fetch_season_images
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_season_images(series_id, season_num)
    return result or {"posters": []}


@app.get("/api/episode-images/{series_id}/{season_num}/{ep_num}")
async def api_episode_images(series_id: int, season_num: int, ep_num: int):
    """Return still images for a TV episode."""
    from .tmdb import fetch_episode_images
    if not settings.tmdb_access_token and not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDB not configured")
    result = await fetch_episode_images(series_id, season_num, ep_num)
    return result or {"stills": []}


# ─── SPA ───

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
INDEX_HTML = ""

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    fonts_dir = FRONTEND_DIR / "fonts"
    if fonts_dir.exists():
        app.mount("/fonts", StaticFiles(directory=str(fonts_dir)), name="fonts")
    with open(FRONTEND_DIR / "index.html", "r") as f:
        INDEX_HTML = f.read()


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except HTTPException:
            raise
        except Exception:
            if request.url.path.startswith("/api"):
                raise
            import traceback
            logger.warning(f"SPA fallback: unhandled error on non-API route {request.url.path}:\n{traceback.format_exc()}")
            return Response(content=INDEX_HTML, media_type="text/html")
        if response.status_code == 404 and INDEX_HTML \
                and not request.url.path.startswith("/api") \
                and not request.url.path.startswith("/assets") \
                and not request.url.path.startswith("/fonts"):
            return Response(content=INDEX_HTML, media_type="text/html")
        if response.status_code == 401 and INDEX_HTML \
                and not request.url.path.startswith("/api") \
                and not request.url.path.startswith("/assets") \
                and not request.url.path.startswith("/fonts"):
            return Response(content=INDEX_HTML, media_type="text/html")
        return response


if INDEX_HTML:
    app.add_middleware(SPAFallbackMiddleware)
