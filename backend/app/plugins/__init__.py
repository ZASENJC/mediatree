import importlib.util
import sys
from pathlib import Path
from typing import Protocol


class ScraperPlugin(Protocol):
    name: str
    label: str
    description: str

    async def search(self, query: str) -> list[dict]: ...
    async def get_detail(self, source_id: str) -> dict | None: ...
    async def get_alternative_covers(self, source_id: str) -> list[dict]: ...


_plugin_registry: dict[str, ScraperPlugin] = {}
_plugins_dir = Path(__file__).parent


def get_plugins_dir() -> Path:
    return _plugins_dir


def list_plugins() -> list[dict]:
    return [
        {
            "name": p.name,
            "label": p.label,
            "description": p.description,
            "builtin": True,
            "enabled": True,
        }
        for p in _plugin_registry.values()
    ]


def get_plugin(name: str) -> ScraperPlugin | None:
    return _plugin_registry.get(name)


def register_builtin(name: str, plugin: ScraperPlugin):
    _plugin_registry[name] = plugin


def _validate_plugin_module(module) -> bool:
    return (
        hasattr(module, "name")
        and hasattr(module, "label")
        and hasattr(module, "description")
        and hasattr(module, "search")
        and hasattr(module, "get_detail")
    )


def load_plugin_file(filepath: str) -> dict | None:
    path = Path(filepath)
    if not path.exists() or path.suffix != ".py":
        return None
    name = path.stem
    if name.startswith("_"):
        return None
    try:
        spec = importlib.util.spec_from_file_location(f"plugin_{name}", path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"plugin_{name}"] = module
        spec.loader.exec_module(module)
        if not _validate_plugin_module(module):
            del sys.modules[f"plugin_{name}"]
            return None
        plugin_info = {
            "name": module.name,
            "label": module.label,
            "description": module.description,
            "builtin": False,
            "enabled": True,
            "file": str(path),
        }
        return plugin_info
    except Exception:
        return None


def unload_plugin(name: str):
    _plugin_registry.pop(name, None)
    module_name = f"plugin_{name}"
    sys.modules.pop(module_name, None)
