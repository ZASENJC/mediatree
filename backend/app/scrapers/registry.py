from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

from .auto_scraper import _try_auto_tmdb_id
from .base import BaseScraper, ScraperInfo
from .tmdb_scraper import tmdb_title_search
from ..scraper_plugins import (
    is_builtin_scraper_available_sync,
    load_plugin_scraper,
    list_enabled_plugin_rows_sync,
    refresh_plugin_cache,
)


_registry: dict[str, BaseScraper] = {}
_initialized = False


@dataclass(frozen=True)
class BuiltinScraperManifest:
    name: str
    version: str
    label: str
    description: str
    entrypoint: str
    class_name: str
    supported_media_types: list[str]
    requires_api_key: bool
    enabled: bool
    builtin: bool = True


def builtin_scraper_plugins_root() -> Path:
    return Path(__file__).resolve().parents[1] / "builtin_plugins" / "scrapers"


def register_scraper(scraper: BaseScraper):
    if not scraper.name:
        raise ValueError("Scraper must define a name")
    _registry[scraper.name] = scraper


def get_scraper(name: str) -> BaseScraper:
    ensure_builtin_scrapers()
    normalized = _normalize_name(name)
    scraper = _registry.get(normalized)
    if not scraper:
        plugin = _get_enabled_plugin_scraper(normalized)
        if plugin:
            return plugin
        raise KeyError(f"Unknown scraper: {name}")
    return scraper


def list_scrapers() -> list[ScraperInfo]:
    ensure_builtin_scrapers()
    infos = [scraper.info() for scraper in _registry.values()]
    infos.extend(_load_enabled_plugin_infos())
    return infos


def ensure_builtin_scrapers():
    global _initialized
    if _initialized:
        return
    from ..config import settings
    if not settings.enable_builtin_scraper_plugins:
        _initialized = True
        return
    for manifest in list_builtin_scraper_manifests():
        if not is_builtin_scraper_available_sync(manifest.name):
            continue
        register_scraper(load_builtin_scraper(manifest))
    _initialized = True


def refresh_scraper_plugins() -> None:
    global _initialized
    refresh_plugin_cache()
    _registry.clear()
    _initialized = False
    ensure_builtin_scrapers()


def list_builtin_scraper_manifests() -> list[BuiltinScraperManifest]:
    root = builtin_scraper_plugins_root()
    manifests: list[BuiltinScraperManifest] = []
    seen_names: set[str] = set()
    if not root.exists():
        return manifests
    for path in sorted(root.glob("*/plugin.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = BuiltinScraperManifest(
            name=str(raw.get("name") or "").strip(),
            version=str(raw.get("version") or "").strip(),
            label=str(raw.get("label") or raw.get("name") or "").strip(),
            description=str(raw.get("description") or "").strip(),
            entrypoint=str(raw.get("entrypoint") or "").strip(),
            class_name=str(raw.get("class_name") or "").strip(),
            supported_media_types=[str(item).strip() for item in raw.get("supported_media_types") or [] if str(item).strip()],
            requires_api_key=bool(raw.get("requires_api_key")),
            enabled=bool(raw.get("enabled", True)),
            builtin=bool(raw.get("builtin", True)),
        )
        if not manifest.name or manifest.name != path.parent.name:
            raise RuntimeError(f"Invalid built-in scraper plugin manifest name: {path}")
        if manifest.name in seen_names:
            raise RuntimeError(f"Duplicate built-in scraper plugin name: {manifest.name}")
        seen_names.add(manifest.name)
        manifests.append(manifest)
    return manifests


def load_builtin_scraper(manifest: BuiltinScraperManifest) -> BaseScraper:
    root = builtin_scraper_plugins_root()
    plugin_dir = (root / manifest.name).resolve()
    module_path = (plugin_dir / manifest.entrypoint).resolve()
    if not plugin_dir.is_relative_to(root.resolve()) or not module_path.is_relative_to(plugin_dir) or not module_path.is_file():
        raise RuntimeError(f"Invalid built-in scraper plugin entrypoint: {manifest.name}")

    module_name = f"mediatree_builtin_scraper_plugin_{manifest.name}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load built-in scraper plugin: {manifest.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    scraper_cls = getattr(module, manifest.class_name, None)
    if not scraper_cls or not isinstance(scraper_cls, type) or not issubclass(scraper_cls, BaseScraper):
        raise RuntimeError(f"Built-in scraper plugin class must subclass BaseScraper: {manifest.name}")

    scraper = scraper_cls()
    scraper.name = manifest.name
    scraper.label = manifest.label
    scraper.description = manifest.description
    scraper.supported_media_types = set(manifest.supported_media_types)
    scraper.requires_api_key = manifest.requires_api_key
    scraper.enabled = manifest.enabled
    return scraper


def _load_enabled_plugin_infos() -> list[ScraperInfo]:
    infos: list[ScraperInfo] = []
    try:
        for row in _load_enabled_plugin_rows():
            try:
                scraper = load_plugin_scraper(row)
                infos.append(scraper.info())
            except Exception:
                continue
    except Exception:
        return []
    return infos


def _get_enabled_plugin_scraper(name: str) -> BaseScraper | None:
    try:
        for row in _load_enabled_plugin_rows():
            if row.get("name") != name:
                continue
            try:
                return load_plugin_scraper(row)
            except Exception:
                return None
    except Exception:
        return None
    return None


def _load_enabled_plugin_rows() -> list[dict]:
    return list_enabled_plugin_rows_sync()


def _normalize_name(name: str | None) -> str:
    value = (name or "auto").strip().lower()
    if value == "tmdb":
        return "tmdb_movie"
    return value


ensure_builtin_scrapers()
