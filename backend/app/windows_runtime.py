from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppChoice:
    app_dir: Path
    source: str
    version: str


def default_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "MediaTree" / "data"
    return Path.home() / "AppData" / "Roaming" / "MediaTree" / "data"


def default_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal_base = exe_dir / "_internal" / "base"
        if internal_base.exists():
            return internal_base
        return exe_dir / "base"
    return Path(__file__).resolve().parents[2]


def default_bin_dir(base_dir: Path | None = None) -> Path:
    root = base_dir or default_base_dir()
    return root / "bin"


def _read_pointer(releases_dir: Path, name: str) -> str:
    try:
        pointer = releases_dir / name
        if pointer.exists():
            return pointer.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _write_pointer(releases_dir: Path, name: str, value: str) -> None:
    releases_dir.mkdir(parents=True, exist_ok=True)
    (releases_dir / name).write_text(value.strip() + "\n", encoding="utf-8")


def _read_version(app_dir: Path) -> str:
    try:
        return (app_dir / "VERSION").read_text(encoding="utf-8").strip().lstrip("vV")
    except OSError:
        return ""


def _normalize_version(version: str) -> tuple[int, int, int]:
    value = (version or "").strip().lstrip("vV").split("-", 1)[0]
    parts = value.split(".")
    try:
        nums = [int(part) for part in parts[:3]]
    except ValueError:
        return (0, 0, 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def is_valid_app_dir(app_dir: Path) -> bool:
    return (
        (app_dir / "app" / "main.py").is_file()
        and (app_dir / "frontend" / "dist" / "index.html").is_file()
        and (app_dir / "VERSION").is_file()
    )


def choose_app_dir(data_dir: Path, base_dir: Path) -> AppChoice:
    releases_dir = data_dir / "releases"
    base_version = _read_version(base_dir)

    current = _read_pointer(releases_dir, "current")
    if current:
        current_dir = releases_dir / current
        if is_valid_app_dir(current_dir):
            current_version = _read_version(current_dir)
            if base_version and _normalize_version(base_version) > _normalize_version(current_version):
                return AppChoice(base_dir, "base", base_version)
            return AppChoice(current_dir, "app-package", current_version or current)

    previous = _read_pointer(releases_dir, "previous")
    if previous and previous != "__base__":
        previous_dir = releases_dir / previous
        if is_valid_app_dir(previous_dir):
            previous_version = _read_version(previous_dir)
            if base_version and _normalize_version(base_version) > _normalize_version(previous_version):
                return AppChoice(base_dir, "base", base_version)
            _write_pointer(releases_dir, "current", previous)
            return AppChoice(previous_dir, "app-package", previous_version or previous)

    return AppChoice(base_dir, "base", base_version)


def prepare_environment(
    *,
    data_dir: Path | None = None,
    base_dir: Path | None = None,
    bin_dir: Path | None = None,
    media_root: Path | None = None,
) -> AppChoice:
    resolved_data_dir = (data_dir or default_data_dir()).resolve()
    resolved_base_dir = (base_dir or default_base_dir()).resolve()
    resolved_bin_dir = (bin_dir or default_bin_dir(resolved_base_dir)).resolve()
    resolved_media_root = (media_root or (resolved_data_dir.parent / "media")).resolve()
    choice = choose_app_dir(resolved_data_dir, resolved_base_dir)

    resolved_data_dir.mkdir(parents=True, exist_ok=True)
    resolved_media_root.mkdir(parents=True, exist_ok=True)
    os.environ["DATA_DIR"] = str(resolved_data_dir)
    os.environ["MEDIA_ROOT"] = str(resolved_media_root)
    os.environ["MEDIATREE_BASE_DIR"] = str(resolved_base_dir)
    os.environ["MEDIATREE_APP_DIR"] = str(choice.app_dir)
    os.environ["MEDIATREE_APP_SOURCE"] = choice.source
    os.environ["MEDIATREE_UPDATE_PLATFORM"] = "windows"
    os.environ["MEDIATREE_RUNTIME"] = "windows"
    os.environ["MEDIATREE_FRONTEND_DIR"] = str(choice.app_dir / "frontend" / "dist")
    os.environ.setdefault("FILE_WATCHER_ENABLED", "true")
    os.environ.setdefault("SCAN_ON_STARTUP", "true")

    current_path = os.environ.get("PATH", "")
    if resolved_bin_dir.exists():
        os.environ["PATH"] = str(resolved_bin_dir) + os.pathsep + current_path
    else:
        os.environ["PATH"] = str(resolved_bin_dir) + os.pathsep + current_path

    app_path = str(choice.app_dir)
    if app_path not in sys.path:
        sys.path.insert(0, app_path)
    for module_name in list(sys.modules):
        if module_name.startswith("app.") and module_name not in {"app.windows_entry", "app.windows_runtime"}:
            sys.modules.pop(module_name, None)
    app_package = sys.modules.get("app")
    if app_package is not None and hasattr(app_package, "__path__"):
        app_package.__path__ = [str(choice.app_dir / "app")]

    return choice
