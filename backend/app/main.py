import asyncio
import json as json_module
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings, logger, setup_file_logging
from .database import (
    init_db, close_db_pool, upsert_movie, get_movies, get_movie_detail,
    get_categories, save_category, delete_category, add_tag, remove_tag,
    delete_movie, search_movies, get_recent_watched,
    get_media_roots, get_folder_tree_from_db,
    get_library_passwords, set_library_password, verify_library_password_v2,
    get_all_library_settings, save_library_settings, has_any_library_setting,
)
from .scanner import scan_media, scrape_for_library, rescrape_movie, rescrape_movie_manual, rescrape_folder, rescrape_folder_manual, search_for_scrape, apply_folder_scrape_result, fetch_search_backdrops, change_folder_cover, change_folder_backdrop, edit_folder_movies, delete_folder_movies
from .javdb import search_javdb
from .stream import get_video_stream
from .subtitles import get_subtitle_tracks, find_external_subtitles, extract_subtitle_stream, convert_external_to_webvtt


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled:
            return await call_next(request)
        path = request.url.path
        if path.startswith("/assets") \
                or path in ("/api/auth/login", "/api/auth/status", "/api/setup/status", "/api/health") \
                or path.startswith("/api/stream/") \
                or path.startswith("/api/cover/") \
                or path.startswith("/api/cached-cover/") \
                or path.startswith("/api/episode-still/") \
                or path.startswith("/api/thumbnail/") \
                or path.startswith("/api/subtitle/") \
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
    startup_task = None
    if settings.scan_on_startup:
        startup_task = asyncio.create_task(run_startup_scan())
    from .watcher import start_file_watcher
    watch_task = asyncio.create_task(start_file_watcher(startup_task))
    logger.info("MediaTree server started")
    yield
    watch_task.cancel()
    await close_db_pool()


async def run_startup_scan():
    try:
        results = scan_media()
        for item in results:
            await upsert_movie(item)
        codes = list(set(r["code"] for r in results))
        from .database import get_db
        db = await get_db()
        await db.execute("DELETE FROM movies WHERE media_root = ''")
        cur = await db.execute("SELECT id, path FROM movies")
        for row in await cur.fetchall():
            if not Path(row["path"]).exists():
                await db.execute("DELETE FROM movies WHERE id=?", (row["id"],))
        await db.commit()

        for root in settings.get_all_media_roots():
            await scrape_for_library(root)

        logger.info(f"Startup scan complete: {len(codes)} unique codes")
    except Exception as e:
        logger.error(f"Startup scan error: {e}")


app = FastAPI(title="MediaTree", lifespan=lifespan)

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# ─── Scan ───

@app.get("/api/scan")
async def api_scan(media_root: str = Query("")):
    results = scan_media(root=media_root) if media_root else scan_media()
    for item in results:
        await upsert_movie(item)
    codes = list(set(r["code"] for r in results))
    roots = [media_root] if media_root else settings.get_all_media_roots()
    for r in roots:
        asyncio.create_task(scrape_for_library(r))
    return {"total": len(results), "codes": codes[:20], "all_codes_count": len(codes)}


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
    if not media_root:
        raise HTTPException(status_code=400, detail="media_root required")
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
    for item in items:
        pwd_hash = None
        if item.get("password"):
            import hashlib
            pwd_hash = hashlib.sha256(item["password"].encode()).hexdigest()
        await save_library_settings({
            "media_root": item["media_root"],
            "scraper": item.get("scraper", "none"),
            "tmdb_key": item.get("tmdb_key", ""),
            "password_hash": pwd_hash,
            "enabled": 1,
        })
    return {"ok": True}


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
async def api_search(q: str = Query(""), media_root: str = Query(""), limit: int = Query(100), offset: int = Query(0)):
    if not q:
        return {"movies": [], "total": 0}
    return await search_movies(q, media_root=media_root, limit=limit, offset=offset)


@app.get("/api/movies")
async def api_movies(folder: str = Query(""), tag: str = Query(""), code: str = Query(""),
                     actress: str = Query(""), category_id: int = Query(0), media_root: str = Query(""),
                     sort: str = Query("created_desc"), limit: int = Query(50), offset: int = Query(0)):
    return await get_movies(folder=folder, tag=tag, code=code, actress=actress,
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


# ─── Stream / Cover / Thumbnail ───

@app.get("/api/stream/{movie_id}")
async def api_stream(movie_id: int, request: Request):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    return get_video_stream(movie["path"], request)


@app.get("/api/cover/{movie_id}")
async def api_cover(movie_id: int):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    cover_key = movie.get("cover_local")
    if cover_key and "/" not in cover_key and "\\" not in cover_key:
        p = Path(settings.covers_dir) / f"{cover_key}.jpg"
        if p.exists():
            return FileResponse(p)
    cover_path = movie.get("cover_local")
    if cover_path and Path(cover_path).exists():
        return FileResponse(cover_path)
    remote = movie.get("cover_remote")
    if remote:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(remote, headers={"Referer": "https://www.javdatabase.com", "User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
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
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    local_path = movie.get("episode_still_local") or movie.get("episode_still")
    if not local_path:
        remote = movie.get("episode_still")
        if remote and (remote.startswith("http://") or remote.startswith("https://")):
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(remote)
                    if resp.status_code == 200:
                        return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
            except Exception:
                pass
        raise HTTPException(status_code=404)
    local = Path(local_path)
    if local.exists():
        return FileResponse(local)
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
    all_tracks = []
    for i, t in enumerate(external):
        all_tracks.append({
            "index": 1000 + i,
            "stream_index": -1,
            "codec": Path(t["path"]).suffix.lstrip("."),
            "language": t.get("language", "und"),
            "title": t.get("name", ""),
            "source": "external",
            "path": t["path"],
        })
    return track_list + all_tracks


@app.get("/api/subtitle/{movie_id}/{track_index}")
async def api_subtitle(movie_id: int, track_index: int):
    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)
    if track_index >= 1000:
        ext_idx = track_index - 1000
        ext_subs = find_external_subtitles(movie["path"])
        if ext_idx < len(ext_subs):
            vtt = convert_external_to_webvtt(ext_subs[ext_idx]["path"])
            if vtt:
                return Response(content=vtt, media_type="text/vtt")
        raise HTTPException(status_code=404)
    vtt = extract_subtitle_stream(movie["path"], track_index)
    if vtt:
        return Response(content=vtt, media_type="text/vtt")
    raise HTTPException(status_code=404)


# ─── Config ───

@app.get("/api/config")
async def api_get_config():
    return {
        "javdb_enabled": settings.javdb_enabled,
        "javdb_cache_hours": settings.javdb_cache_hours,
        "javdb_request_interval": settings.javdb_request_interval,
        "tmdb_cache_hours": getattr(settings, 'tmdb_cache_hours', 168),
        "bangumi_cache_hours": getattr(settings, 'bangumi_cache_hours', 168),
        "tmdb_api_key": settings.tmdb_api_key,
        "tmdb_access_token": settings.tmdb_access_token,
        "media_root": settings.media_root,
    }


@app.post("/api/config")
async def api_update_config(data: dict):
    if "javdb_enabled" in data:
        settings.javdb_enabled = data["javdb_enabled"]
    if "javdb_cache_hours" in data:
        settings.javdb_cache_hours = data["javdb_cache_hours"]
    if "javdb_request_interval" in data:
        settings.javdb_request_interval = data["javdb_request_interval"]
    if "tmdb_cache_hours" in data:
        settings.tmdb_cache_hours = data["tmdb_cache_hours"]
    if "bangumi_cache_hours" in data:
        settings.bangumi_cache_hours = data["bangumi_cache_hours"]
    if "tmdb_api_key" in data:
        settings.tmdb_api_key = data["tmdb_api_key"]
    if "tmdb_access_token" in data:
        settings.tmdb_access_token = data["tmdb_access_token"]
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
async def api_change_password(data: dict):
    old_user = data.get("old_username", "")
    old_pass = data.get("old_password", "")
    new_user = data.get("new_username", "")
    new_pass = data.get("new_password", "")

    if settings.auth_enabled:
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
    scraper = data.get("scraper")
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    result = await rescrape_movie_manual(movie_id, query, scraper)
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
    result = await rescrape_folder(folder, media_root)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scrape failed"))
    return result


# ─── Search Scrape ───

@app.post("/api/search-scrape")
async def api_search_scrape(data: dict):
    query = data.get("query", "")
    scraper = data.get("scraper", "tmdb")
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
    result = await delete_folder_movies(folder, media_root)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Delete failed"))
    return result


# ─── Alternative Covers ───

@app.get("/api/movies/{movie_id}/alternative-covers")
async def api_alternative_covers(movie_id: int):
    from .database import get_db
    from .tmdb import fetch_tmdb_detail, search_tmdb

    movie = await get_movie_detail(movie_id)
    if not movie:
        raise HTTPException(status_code=404)

    alternatives = []
    tmdb_id = movie.get("tmdb_id")
    tmdb_type = movie.get("tmdb_type")

    if tmdb_id and tmdb_type:
        detail = await fetch_tmdb_detail(str(tmdb_id), tmdb_type)
        if detail and detail.get("poster_url"):
            alternatives.append({"url": detail["poster_url"], "source": "tmdb_primary"})

        if detail and detail.get("backdrop_url"):
            alternatives.append({"url": detail["backdrop_url"], "source": "tmdb_backdrop"})

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
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files allowed")

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        content = await file.read()
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
            "scraper": ls.get("scraper", "none"),
        })
    if not items:
        items.append({"path": settings.media_root, "label": "media", "movie_count": 0, "locked": False, "scraper": "none"})
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


# ─── Static Media ───

@app.get("/api/media/{file_path:path}")
async def api_media_file(file_path: str):
    full_path = Path(settings.media_root) / file_path
    try:
        real = full_path.resolve()
        root = Path(settings.media_root).resolve()
        if not real.is_relative_to(root) or not real.exists():
            raise HTTPException(status_code=404)
    except (OSError, ValueError):
        raise HTTPException(status_code=404)
    return FileResponse(real)


# ─── SPA ───

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
INDEX_HTML = ""

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    with open(FRONTEND_DIR / "index.html", "r") as f:
        INDEX_HTML = f.read()


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except HTTPException:
            raise
        except Exception:
            import traceback
            traceback.print_exc()
            return Response(content=INDEX_HTML, media_type="text/html")
        if response.status_code == 404 and INDEX_HTML \
                and not request.url.path.startswith("/api") \
                and not request.url.path.startswith("/assets"):
            return Response(content=INDEX_HTML, media_type="text/html")
        if response.status_code == 401 and INDEX_HTML \
                and not request.url.path.startswith("/api") \
                and not request.url.path.startswith("/assets"):
            return Response(content=INDEX_HTML, media_type="text/html")
        return response


if INDEX_HTML:
    app.add_middleware(SPAFallbackMiddleware)
