from __future__ import annotations

import importlib.util
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .config import logger, settings
from .scrapers.base import BaseScraper, ScraperInfo

PLUGIN_ROOT_NAME = "scraper_plugins"
MAX_PLUGIN_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_PLUGIN_FILES = 32
MAX_PLUGIN_UNCOMPRESSED_BYTES = 4 * 1024 * 1024
PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
PLUGIN_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
BUILTIN_SCRAPER_PLUGIN_NAMES = frozenset({
    "auto",
    "none",
    "tmdb_movie",
    "tmdb_tv",
    "tmdb_collection",
    "bangumi",
    "javdatabase",
})
RESERVED_SCRAPER_ALIASES = frozenset({
    "tmdb",
    "tmdb_tv_search",
    "tmdb_movie_search",
})

_plugin_instance_cache: dict[str, BaseScraper] = {}


@dataclass(frozen=True)
class ScraperPluginManifest:
    name: str
    version: str
    label: str
    description: str
    entrypoint: str
    class_name: str
    supported_media_types: list[str]


def plugin_root() -> Path:
    return Path(settings.data_dir) / PLUGIN_ROOT_NAME


def _safe_text(value: Any, limit: int = 512) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _decode_supported_media_types(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        media_type = str(item or "").strip().lower()
        if media_type and re.fullmatch(r"[a-z0-9_-]{1,32}", media_type):
            result.append(media_type)
    return sorted(set(result))


def _plugin_public_row(row: dict) -> dict:
    return {
        "name": row.get("name") or "",
        "version": row.get("version") or "",
        "label": row.get("label") or row.get("name") or "",
        "description": row.get("description") or "",
        "supported_media_types": _decode_supported_media_types(row.get("supported_media_types")),
        "enabled": bool(row.get("enabled")),
        "builtin": bool(row.get("builtin")),
        "installed_at": row.get("installed_at"),
        "updated_at": row.get("updated_at"),
        "error": row.get("error") or "",
    }


def serialize_scraper_info(info: ScraperInfo, *, builtin: bool = False) -> dict:
    return {
        "name": info.name,
        "label": info.label,
        "description": info.description,
        "supported_media_types": list(info.supported_media_types),
        "requires_api_key": bool(info.requires_api_key),
        "enabled": bool(info.enabled),
        "builtin": builtin,
    }


def is_builtin_scraper_name(name: str) -> bool:
    return bool(settings.enable_builtin_scraper_plugins and name in BUILTIN_SCRAPER_PLUGIN_NAMES)


def is_reserved_plugin_name(name: str) -> bool:
    if name in RESERVED_SCRAPER_ALIASES:
        return True
    return bool(settings.enable_builtin_scraper_plugins and name in BUILTIN_SCRAPER_PLUGIN_NAMES)


def validate_manifest(raw: Any) -> ScraperPluginManifest:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="plugin.json must be an object")

    name = _safe_text(raw.get("name"), 64).lower()
    version = _safe_text(raw.get("version"), 64)
    label = _safe_text(raw.get("label") or name, 96)
    description = _safe_text(raw.get("description"), 512)
    entrypoint = _safe_text(raw.get("entrypoint"), 160)
    class_name = _safe_text(raw.get("class_name"), 96)
    supported_media_types = _decode_supported_media_types(raw.get("supported_media_types"))

    if not PLUGIN_NAME_PATTERN.fullmatch(name):
        raise HTTPException(status_code=400, detail="Invalid plugin name")
    if is_reserved_plugin_name(name):
        raise HTTPException(status_code=400, detail="Plugin name is reserved")
    if not version or not PLUGIN_VERSION_PATTERN.fullmatch(version):
        raise HTTPException(status_code=400, detail="Invalid plugin version")
    if not label:
        raise HTTPException(status_code=400, detail="Plugin label required")
    if not entrypoint or Path(entrypoint).is_absolute() or ".." in Path(entrypoint).parts:
        raise HTTPException(status_code=400, detail="Invalid plugin entrypoint")
    if Path(entrypoint).suffix != ".py":
        raise HTTPException(status_code=400, detail="Plugin entrypoint must be a Python file")
    if not class_name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,95}", class_name):
        raise HTTPException(status_code=400, detail="Invalid plugin class_name")
    if not supported_media_types:
        raise HTTPException(status_code=400, detail="supported_media_types required")

    return ScraperPluginManifest(
        name=name,
        version=version,
        label=label,
        description=description,
        entrypoint=entrypoint,
        class_name=class_name,
        supported_media_types=supported_media_types,
    )


def _safe_zip_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > MAX_PLUGIN_FILES:
        raise HTTPException(status_code=400, detail="Plugin archive has too many files")

    total_size = 0
    seen_names: set[str] = set()
    safe_infos: list[zipfile.ZipInfo] = []
    for info in infos:
        name = (info.filename or "").replace("\\", "/")
        path = Path(name)
        mode = (info.external_attr >> 16) & 0o170000
        if not name or name.startswith("/") or path.is_absolute() or ".." in path.parts:
            raise HTTPException(status_code=400, detail="Invalid plugin archive path")
        if mode == 0o120000:
            raise HTTPException(status_code=400, detail="Unsupported plugin archive member type")
        if info.is_dir():
            continue
        if name in seen_names:
            raise HTTPException(status_code=400, detail="Duplicate plugin archive path")
        seen_names.add(name)
        if int(info.file_size or 0) > MAX_PLUGIN_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=400, detail="Plugin archive member is too large")
        total_size += int(info.file_size or 0)
        if total_size > MAX_PLUGIN_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=400, detail="Plugin archive is too large")
        safe_infos.append(info)
    return safe_infos


async def install_plugin_archive(filename: str, content: bytes) -> dict:
    suffix = Path(filename or "").suffix.lower()
    if suffix != ".zip":
        raise HTTPException(status_code=400, detail="Only .zip scraper plugins are supported")
    if not content:
        raise HTTPException(status_code=400, detail="Plugin archive is empty")
    if len(content) > MAX_PLUGIN_ARCHIVE_BYTES:
        raise HTTPException(status_code=400, detail="Plugin archive is too large")

    import io

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            safe_infos = _safe_zip_members(zf)
            if "plugin.json" not in {info.filename.replace("\\", "/") for info in safe_infos}:
                raise HTTPException(status_code=400, detail="plugin.json required")
            try:
                raw_manifest = json.loads(zf.read("plugin.json").decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                raise HTTPException(status_code=400, detail="Invalid plugin.json")
            manifest = validate_manifest(raw_manifest)
            if manifest.entrypoint not in {info.filename.replace("\\", "/") for info in safe_infos}:
                raise HTTPException(status_code=400, detail="Plugin entrypoint not found")

            target_root = (plugin_root() / manifest.name / manifest.version).resolve()
            data_plugins_root = plugin_root().resolve()
            try:
                if not target_root.is_relative_to(data_plugins_root):
                    raise HTTPException(status_code=400, detail="Invalid plugin install path")
            except (OSError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid plugin install path")

            if target_root.exists():
                shutil.rmtree(target_root)
            target_root.mkdir(parents=True, exist_ok=True)
            for info in safe_infos:
                member_name = info.filename.replace("\\", "/")
                target = (target_root / member_name).resolve()
                try:
                    if not target.is_relative_to(target_root):
                        raise HTTPException(status_code=400, detail="Invalid plugin archive path")
                except (OSError, ValueError):
                    raise HTTPException(status_code=400, detail="Invalid plugin archive path")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip archive")

    await upsert_plugin_manifest(manifest, str(target_root), enabled=False, error="")
    refresh_plugin_cache()
    return await get_plugin(manifest.name) or {}


async def upsert_plugin_manifest(
    manifest: ScraperPluginManifest,
    installed_path: str,
    *,
    enabled: bool,
    error: str = "",
) -> None:
    from .database import get_db

    db = await get_db()
    await db.execute(
        """
        INSERT INTO scraper_plugins (
            name, version, label, description, supported_media_types,
            entrypoint, class_name, installed_path, enabled, builtin, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(name) DO UPDATE SET
            version=excluded.version,
            label=excluded.label,
            description=excluded.description,
            supported_media_types=excluded.supported_media_types,
            entrypoint=excluded.entrypoint,
            class_name=excluded.class_name,
            installed_path=excluded.installed_path,
            enabled=excluded.enabled,
            builtin=0,
            error=excluded.error,
            updated_at=datetime('now')
        """,
        (
            manifest.name,
            manifest.version,
            manifest.label,
            manifest.description,
            json.dumps(manifest.supported_media_types),
            manifest.entrypoint,
            manifest.class_name,
            installed_path,
            1 if enabled else 0,
            error,
        ),
    )
    await db.commit()


async def list_plugins() -> list[dict]:
    from .database import get_db

    db = await get_db()
    cur = await db.execute("SELECT * FROM scraper_plugins ORDER BY builtin DESC, name")
    return [_plugin_public_row(dict(row)) for row in await cur.fetchall()]


def list_enabled_plugin_rows_sync() -> list[dict]:
    db_path = Path(settings.db_path)
    if not db_path.exists():
        return []
    try:
        import sqlite3
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM scraper_plugins WHERE enabled=1 ORDER BY name")
            return [dict(row) for row in cur.fetchall()]
    except sqlite3.Error:
        return []


def is_enabled_plugin_name_sync(name: str) -> bool:
    if not name:
        return False
    for row in list_enabled_plugin_rows_sync():
        if row.get("name") == name:
            return True
    return False


async def get_plugin(name: str) -> dict | None:
    from .database import get_db

    db = await get_db()
    cur = await db.execute("SELECT * FROM scraper_plugins WHERE name=?", (name,))
    row = await cur.fetchone()
    return _plugin_public_row(dict(row)) if row else None


async def set_plugin_enabled(name: str, enabled: bool) -> dict:
    from .database import get_db

    db = await get_db()
    cur = await db.execute("SELECT * FROM scraper_plugins WHERE name=?", (name,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plugin not found")
    raw = dict(row)
    if enabled:
        load_plugin_scraper(raw)
        error = ""
    else:
        error = raw.get("error") or ""
    await db.execute(
        "UPDATE scraper_plugins SET enabled=?, error=?, updated_at=datetime('now') WHERE name=?",
        (1 if enabled else 0, error, name),
    )
    await db.commit()
    refresh_plugin_cache()
    plugin = await get_plugin(name)
    return plugin or {}


async def record_plugin_error(name: str, error: str) -> dict:
    from .database import get_db

    message = _safe_text(error, 512)
    db = await get_db()
    await db.execute(
        "UPDATE scraper_plugins SET error=?, updated_at=datetime('now') WHERE name=?",
        (message, name),
    )
    await db.commit()
    refresh_plugin_cache()
    plugin = await get_plugin(name)
    return plugin or {}


async def delete_plugin(name: str) -> None:
    from .database import get_all_library_settings, get_db

    for setting in await get_all_library_settings():
        if (setting.get("scraper") or "") == name:
            raise HTTPException(status_code=409, detail="Plugin is used by a library")

    db = await get_db()
    cur = await db.execute("SELECT installed_path FROM scraper_plugins WHERE name=?", (name,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plugin not found")
    installed_path = row["installed_path"]
    await db.execute("DELETE FROM scraper_plugins WHERE name=?", (name,))
    await db.commit()

    try:
        path = Path(installed_path).resolve()
        root = plugin_root().resolve()
        if path.is_relative_to(root) and path.exists():
            shutil.rmtree(path)
    except Exception as exc:
        logger.warning(f"Failed to remove scraper plugin files for {name}: {exc}")
    refresh_plugin_cache()


def load_plugin_scraper(row: dict) -> BaseScraper:
    name = row.get("name") or ""
    cached = _plugin_instance_cache.get(name)
    if cached is not None:
        return cached

    installed_path = Path(row.get("installed_path") or "")
    entrypoint = row.get("entrypoint") or ""
    class_name = row.get("class_name") or ""
    module_path = (installed_path / entrypoint).resolve()
    try:
        if not module_path.is_relative_to(installed_path.resolve()):
            raise ValueError("entrypoint escapes plugin directory")
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid plugin entrypoint: {exc}") from exc
    if not module_path.exists() or not module_path.is_file():
        raise RuntimeError("Plugin entrypoint not found")

    module_name = f"mediatree_scraper_plugin_{name}_{row.get('version', '').replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load plugin module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    scraper_cls = getattr(module, class_name, None)
    if not scraper_cls or not isinstance(scraper_cls, type) or not issubclass(scraper_cls, BaseScraper):
        raise RuntimeError("Plugin class must subclass BaseScraper")
    scraper = scraper_cls()
    scraper.name = name
    scraper.label = row.get("label") or name
    scraper.description = row.get("description") or ""
    scraper.supported_media_types = set(_decode_supported_media_types(row.get("supported_media_types")))
    scraper.requires_api_key = False
    scraper.enabled = bool(row.get("enabled"))
    _plugin_instance_cache[name] = scraper
    return scraper


def refresh_plugin_cache() -> None:
    _plugin_instance_cache.clear()
