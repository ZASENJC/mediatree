import io
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from ..config import settings
from ..database import close_db_pool, init_db

router = APIRouter()


@router.get("/api/backup")
async def api_backup(backup_type: str = Query("core")):
    db_path = Path(settings.db_path)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    backup_dir = Path(settings.data_dir) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if backup_type == "full":
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


def _validate_backup_path(file_path: str, allowed_suffixes: set | None = None) -> Path:
    """Validate a backup file path is within the data directory."""
    if not file_path:
        raise HTTPException(status_code=400, detail="Backup file path required")
    p = Path(file_path)
    if allowed_suffixes and p.suffix.lower() not in allowed_suffixes:
        raise HTTPException(status_code=400, detail=f"Invalid backup file type: {p.suffix}")
    try:
        real = p.resolve()
        data_root = Path(settings.data_dir).resolve()
        if not real.is_relative_to(data_root):
            raise HTTPException(status_code=400, detail="Backup file path is outside data directory")
        return real
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid backup file path")


def _safe_restore_members(tar, data_root: Path):
    data_root_resolved = data_root.resolve()
    for member in tar.getmembers():
        name = (member.name or "").replace("\\", "/")
        target = (data_root_resolved / name).resolve()
        if member.issym() or member.islnk() or member.isdev():
            raise HTTPException(status_code=400, detail="Unsupported backup member type")
        try:
            if not target.is_relative_to(data_root_resolved):
                raise HTTPException(status_code=400, detail="Invalid backup archive path")
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid backup archive path")
        if name == "browser.db" or name.startswith("covers/") or name.startswith("stills/"):
            yield member


async def _reset_database_pool() -> None:
    from .. import database as db_module

    db_module._db_pool = None
    await init_db()


@router.post("/api/restore")
async def api_restore(data: dict):
    file_path = data.get("path", "")
    if not file_path:
        raise HTTPException(status_code=400, detail="Backup file path required")

    backup_source = _validate_backup_path(file_path, allowed_suffixes={".db", ".gz"})
    if not backup_source.exists():
        raise HTTPException(status_code=400, detail="Backup file not found")

    suffix = backup_source.suffix.lower()

    if suffix == ".gz":
        await close_db_pool()
        data_root_resolved = Path(settings.data_dir).resolve()
        try:
            with tarfile.open(str(backup_source), "r:gz") as tar:
                for member in _safe_restore_members(tar, data_root_resolved):
                    if member.name == "browser.db":
                        tar.extract(member, str(data_root_resolved))
                    elif member.name.startswith("covers"):
                        covers_dir = Path(settings.covers_dir)
                        covers_dir.mkdir(parents=True, exist_ok=True)
                        tar.extract(member, str(data_root_resolved))
                    elif member.name.startswith("stills"):
                        stills_dir = Path(settings.data_dir) / "stills"
                        stills_dir.mkdir(parents=True, exist_ok=True)
                        tar.extract(member, str(data_root_resolved))
        finally:
            await _reset_database_pool()
        return {"ok": True, "message": "Full backup restored successfully"}

    if suffix == ".db":
        await close_db_pool()
        shutil.copy2(str(backup_source), str(Path(settings.db_path)))
        await _reset_database_pool()
        return {"ok": True, "message": "Database restored successfully"}

    raise HTTPException(status_code=400, detail="Invalid backup file")


@router.post("/api/restore/upload")
async def api_restore_upload(file: UploadFile = None):
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
            await close_db_pool()
            data_root_resolved = Path(settings.data_dir).resolve()
            try:
                with tarfile.open(tmp_path, "r:gz") as tar:
                    for member in _safe_restore_members(tar, data_root_resolved):
                        if member.name == "browser.db":
                            tar.extract(member, str(data_root_resolved))
                        elif member.name.startswith("covers") and not member.isdir():
                            tar.extract(member, str(data_root_resolved))
                        elif member.name.startswith("stills") and not member.isdir():
                            stills_dir = Path(settings.data_dir) / "stills"
                            stills_dir.mkdir(parents=True, exist_ok=True)
                            tar.extract(member, str(data_root_resolved))
            finally:
                await _reset_database_pool()
        elif suffix == ".db":
            await close_db_pool()
            shutil.copy2(tmp_path, str(Path(settings.db_path)))
            await _reset_database_pool()
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass

    return {"ok": True, "message": "Backup restored successfully"}
