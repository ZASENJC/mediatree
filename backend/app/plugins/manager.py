import os
from pathlib import Path
from . import _plugin_registry, _plugins_dir, list_plugins, load_plugin_file

CUSTOM_PLUGINS_DIR = _plugins_dir / "custom"

_loaded_files: dict[str, str] = {}


def ensure_custom_dir():
    CUSTOM_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)


def get_installed_plugins() -> list[dict]:
    plugins = list_plugins()
    ensure_custom_dir()
    for f in sorted(CUSTOM_PLUGINS_DIR.glob("*.py")):
        name = f.stem
        if name.startswith("_"):
            continue
        if any(p["name"] == name for p in plugins):
            continue
        plugins.append({
            "name": name,
            "label": name,
            "description": f"Custom plugin: {name}",
            "builtin": False,
            "enabled": True,
            "file": str(f),
        })
    return plugins


def install_plugin(filepath: str) -> dict:
    path = Path(filepath)
    if not path.exists():
        return {"ok": False, "error": "File not found"}
    if path.suffix != ".py":
        return {"ok": False, "error": "Only .py files allowed"}

    ensure_custom_dir()
    dest = CUSTOM_PLUGINS_DIR / path.name
    import shutil
    shutil.copy2(str(path), str(dest))

    info = load_plugin_file(str(dest))
    if info:
        _loaded_files[info["name"]] = str(dest)
        return {"ok": True, "plugin": info}
    return {"ok": False, "error": "Invalid plugin: missing required interface"}


def remove_plugin(name: str) -> bool:
    _plugin_registry.pop(name, None)
    _loaded_files.pop(name, None)
    plugin_file = CUSTOM_PLUGINS_DIR / f"{name}.py"
    if plugin_file.exists():
        try:
            plugin_file.unlink()
            return True
        except Exception:
            return False
    return False
