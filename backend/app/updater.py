"""MediaTree update checker and self-upgrade helpers.

The default path installs a small application package into the data volume
and asks the entrypoint to restart the Python process. The Docker image
replacement path is retained for base runtime changes and explicit advanced
updates.
"""
import asyncio
import hashlib
import httpx
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import tarfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from .config import settings, logger

# ─── Constants ───

GITHUB_REPO = "ZASENJC/mediatree"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
DOCKERHUB_TAGS_API = "https://hub.docker.com/v2/repositories/zasenjc/mediatree/tags/?page_size=20"
DOCKERHUB_LATEST_TAG_API = "https://hub.docker.com/v2/repositories/zasenjc/mediatree/tags/latest"
DOCKER_REGISTRY_TOKEN_API = "https://auth.docker.io/token"
DOCKER_REGISTRY_API = "https://registry-1.docker.io/v2/zasenjc/mediatree"
DOCKER_REPOSITORY = "zasenjc/mediatree"

# VERSION file path — try container path first, then development path
_VERSION_CONTAINER = Path(__file__).parent.parent / "VERSION"
_VERSION_DEV = Path(__file__).parent.parent.parent / "VERSION"
VERSION_FILE = _VERSION_CONTAINER if _VERSION_CONTAINER.exists() else _VERSION_DEV

DOCKER_SOCKET = Path("/var/run/docker.sock")
BASE_API_VERSION = 1
BASE_APP_DIR = Path(os.environ.get("MEDIATREE_BASE_DIR", "/opt/mediatree/base"))
APP_SOURCE = os.environ.get("MEDIATREE_APP_SOURCE", "")
APP_DIR = Path(os.environ.get("MEDIATREE_APP_DIR", ""))
DATA_DIR = Path(settings.data_dir)
RELEASES_DIR = DATA_DIR / "releases"
UPDATES_DIR = DATA_DIR / "updates"
UPDATE_STATUS_FILE = UPDATES_DIR / "status.json"
UPDATE_PLATFORM = os.environ.get("MEDIATREE_UPDATE_PLATFORM", "docker").strip().lower() or "docker"

# Shell metacharacters to reject in version strings
_FORBIDDEN_CHARS = set(";&|$`\\\n\r")
_APP_PACKAGE_DIR_RE = re.compile(r"^v?\d+(?:\.\d+){1,3}(?:[-_][A-Za-z0-9][A-Za-z0-9._-]*)?$")
_SENSITIVE_ENV_MARKERS = (
    "PASS",
    "PASSWORD",
    "TOKEN",
    "SECRET",
    "API_KEY",
    "ACCESS_KEY",
    "PRIVATE_KEY",
    "AUTH",
)
_DOCKER_MANIFEST_ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))
_DOCKER_VERSION_LABELS = (
    "org.opencontainers.image.version",
    "org.label-schema.version",
    "mediatree.version",
)


def _is_sensitive_key(key: str) -> bool:
    upper = (key or "").upper()
    return any(marker in upper for marker in _SENSITIVE_ENV_MARKERS)


def _redact_text(text: str) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if not _is_sensitive_key(key):
            return match.group(0)
        quote = match.group(3) or ""
        return f"{key}={quote}***{quote}"

    return re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)(=)(['\"]?)([^'\"\s,;]+)(['\"]?)", repl, text)


def _redact_arg(arg: str) -> str:
    if "=" not in arg:
        return arg
    key, value = arg.split("=", 1)
    return f"{key}=***" if _is_sensitive_key(key) and value else arg


def _format_command_for_logs(cmd: list[str]) -> str:
    return " ".join(shlex.quote(_redact_arg(part)) for part in cmd)


def _redact_logs(logs: list[str]) -> list[str]:
    return [_redact_text(line) for line in logs]

# ─── Version utilities ───


def _get_running_image_tag() -> str | None:
    """Get Docker image tag of the running container via docker inspect.

    Returns the image tag (without v prefix), or None if detection fails.
    Falls back to VERSION file path — get_current_version() handles that.
    """
    cid: str | None = None
    try:
        cgroup_text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
        for pattern in (r"/docker-([0-9a-f]{64})\.scope", r"/docker/([0-9a-f]{64})"):
            match = re.search(pattern, cgroup_text)
            if match:
                cid = match.group(1)[:12]
                break
    except Exception:
        pass

    if not cid:
        cid = socket.gethostname()

    if cid:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.Config.Image}}", cid],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                image = result.stdout.strip()
                if ":" in image:
                    tag = image.split(":", 1)[-1]
                    if tag and tag != "latest":
                        return tag.lstrip("vV")
        except Exception:
            pass
    return None


def get_current_version() -> str:
    """Read current application version from the active app directory."""
    for candidate in (APP_DIR / "VERSION", VERSION_FILE, BASE_APP_DIR / "VERSION"):
        try:
            if candidate.exists():
                value = candidate.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            pass
    return "unknown"


def get_base_version() -> str:
    """Read the built-in version shipped inside the current image."""
    for candidate in (BASE_APP_DIR / "VERSION", VERSION_FILE):
        try:
            if candidate.exists():
                value = candidate.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            pass
    return "unknown"


def get_current_source() -> str:
    """Return where the currently running application code came from."""
    if APP_SOURCE in {"base", "app-package", "docker-image"}:
        return APP_SOURCE
    if (APP_DIR / "VERSION").exists() and str(APP_DIR).startswith(str(RELEASES_DIR)):
        return "app-package"
    if _get_running_image_tag():
        return "docker-image"
    return "base"


def get_version_state() -> dict:
    """Describe the user-visible version state and underlying sources."""
    runtime_version = get_current_version()
    base_version = get_base_version()
    current_source = get_current_source()
    overlay_active = current_source == "app-package"
    effective_version = runtime_version
    if _normalize_version(base_version) > _normalize_version(effective_version):
        effective_version = base_version
    overlay_is_outdated = (
        overlay_active
        and _normalize_version(base_version) > _normalize_version(runtime_version)
    )

    status_note = ""
    if overlay_is_outdated:
        status_note = (
            f"当前已更新到 {effective_version}。"
            f"运行中的应用包仍是 {runtime_version}，镜像内置版本是 {base_version}。"
        )
    elif overlay_active and base_version != "unknown" and _normalize_version(runtime_version) > _normalize_version(base_version):
        status_note = (
            f"当前已更新到 {effective_version}。"
            f"镜像内置版本为 {base_version}。"
        )
    elif overlay_active and base_version != "unknown":
        status_note = f"当前已更新到 {effective_version}。"
    elif current_source in {"base", "docker-image"} and effective_version != "unknown":
        status_note = f"当前已更新到 {effective_version}。"

    return {
        "current_version": effective_version,
        "runtime_version": runtime_version,
        "current_source": current_source,
        "base_version": base_version,
        "effective_version": effective_version,
        "overlay_active": overlay_active,
        "overlay_is_outdated": overlay_is_outdated,
        "status_note": status_note,
    }


def _normalize_version(v: str) -> tuple:
    """Convert version string like 'v1.2.3' or '1.2.3-test' to comparable tuple."""
    v = (v or "").strip().lstrip("vV")
    v = v.split("-")[0]  # strip pre-release suffix (-test, -beta, etc.)
    try:
        parts = v.split(".")
        return tuple(int(p) for p in parts[:3])
    except Exception:
        return (0, 0, 0)


# ─── GitHub Releases ───


async def fetch_github_releases(max_count: int = 4) -> list[dict]:
    """Fetch releases from GitHub Releases API."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                GITHUB_API,
                headers={"Accept": "application/vnd.github.v3+json",
                         "User-Agent": "MediaTree-Updater/1.0"},
            )
            resp.raise_for_status()
            releases = resp.json()
            result = []
            for rel in releases[:max_count]:
                tag = rel.get("tag_name", "")
                result.append({
                    "version": (tag or "").lstrip("vV"),
                    "display_version": tag,
                    "name": rel.get("name", ""),
                    "published_at": rel.get("published_at", ""),
                    "html_url": rel.get("html_url", ""),
                    "body": (rel.get("body") or "")[:200],
                    "source": "github",
                    "assets": rel.get("assets") or [],
                })
            return result
    except Exception as e:
        logger.warning(f"Failed to fetch GitHub releases: {e}")
        return []


# ─── DockerHub Tags ───


async def fetch_dockerhub_tags(max_count: int = 4) -> list[dict]:
    """Fetch tags from DockerHub Tags API."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(DOCKERHUB_TAGS_API)
            resp.raise_for_status()
            data = resp.json()
            tags = data.get("results", [])
            result = []
            for tag in tags[:max_count]:
                name = tag.get("name", "")
                if name == "latest":
                    continue
                result.append({
                    "version": name.lstrip("vV"),
                    "display_version": name,
                    "name": name,
                    "published_at": tag.get("last_updated", ""),
                    "html_url": f"https://hub.docker.com/r/zasenjc/mediatree/tags?name={name}",
                    "body": "",
                    "source": "dockerhub",
                })
            return result
    except Exception as e:
        logger.warning(f"Failed to fetch DockerHub tags: {e}")
        return []


def _clean_remote_version(value: str) -> str:
    version = (value or "").strip()
    if not version or version.lower() in {"latest", "unknown"}:
        return ""
    return version.lstrip("vV")


def _extract_version_from_image_config(config: dict) -> str:
    """Extract the MediaTree version baseline from a Docker image config."""
    image_config = config.get("config") or {}
    labels = image_config.get("Labels") or {}
    for key in _DOCKER_VERSION_LABELS:
        version = _clean_remote_version(labels.get(key, ""))
        if version:
            return version

    for env in image_config.get("Env") or []:
        if not isinstance(env, str) or "=" not in env:
            continue
        key, value = env.split("=", 1)
        if key == "MEDIATREE_VERSION":
            version = _clean_remote_version(value)
            if version:
                return version
    return ""


def _select_registry_manifest(manifests: list[dict]) -> dict | None:
    if not manifests:
        return None
    for preferred in (("linux", "amd64"), ("linux", "arm64")):
        for manifest in manifests:
            platform = manifest.get("platform") or {}
            if platform.get("os") == preferred[0] and platform.get("architecture") == preferred[1]:
                return manifest
    for manifest in manifests:
        platform = manifest.get("platform") or {}
        if platform.get("os") == "linux":
            return manifest
    return manifests[0]


async def _fetch_registry_json(client: httpx.AsyncClient, reference: str, token: str, accept: str) -> dict:
    resp = await client.get(
        f"{DOCKER_REGISTRY_API}/{reference}",
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "User-Agent": "MediaTree-Updater/1.0",
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _fetch_docker_registry_token(client: httpx.AsyncClient) -> str:
    resp = await client.get(
        DOCKER_REGISTRY_TOKEN_API,
        params={
            "service": "registry.docker.io",
            "scope": f"repository:{DOCKER_REPOSITORY}:pull",
        },
        headers={"User-Agent": "MediaTree-Updater/1.0"},
    )
    resp.raise_for_status()
    return resp.json().get("token", "")


async def _fetch_dockerhub_latest_tag_metadata(client: httpx.AsyncClient) -> dict:
    resp = await client.get(DOCKERHUB_LATEST_TAG_API, headers={"User-Agent": "MediaTree-Updater/1.0"})
    resp.raise_for_status()
    data = resp.json()
    return {
        "published_at": data.get("last_updated", ""),
        "digest": data.get("digest", ""),
    }


async def _fetch_docker_registry_latest_version(client: httpx.AsyncClient) -> str:
    token = await _fetch_docker_registry_token(client)
    if not token:
        return ""

    manifest = await _fetch_registry_json(client, "manifests/latest", token, _DOCKER_MANIFEST_ACCEPT)
    if manifest.get("manifests"):
        selected = _select_registry_manifest(manifest.get("manifests") or [])
        digest = selected.get("digest", "") if selected else ""
        if not digest:
            return ""
        manifest = await _fetch_registry_json(client, f"manifests/{digest}", token, _DOCKER_MANIFEST_ACCEPT)

    config_digest = (manifest.get("config") or {}).get("digest", "")
    if not config_digest:
        return ""
    config = await _fetch_registry_json(client, f"blobs/{config_digest}", token, "application/octet-stream")
    return _extract_version_from_image_config(config)


async def fetch_dockerhub_latest_baseline() -> dict:
    """Fetch the version baseline currently published as DockerHub latest."""
    result = {
        "version": "",
        "display_version": "latest",
        "published_at": "",
        "html_url": "https://hub.docker.com/r/zasenjc/mediatree/tags?name=latest",
        "source": "dockerhub-latest",
        "status": "unknown",
        "reason": "",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                result.update(await _fetch_dockerhub_latest_tag_metadata(client))
            except Exception as tag_error:
                result["reason"] = f"DockerHub latest 元数据读取失败: {tag_error}"
            version = await _fetch_docker_registry_latest_version(client)
            if version:
                result["version"] = version
                result["status"] = "ok"
            else:
                result["reason"] = result["reason"] or "DockerHub latest 镜像未提供版本基线 label。"
    except Exception as e:
        result["reason"] = f"DockerHub latest 基线读取失败: {e}"
        logger.warning(result["reason"])
    return result


def _parse_remote_timestamp(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _is_app_package_release(entry: dict | None) -> bool:
    if not entry:
        return False
    return entry.get("update_type") == "app-package" and not bool(entry.get("requires_image_update"))


def _build_latest_sync_warning(latest_entry: dict | None, dockerhub_latest: dict | None) -> dict | None:
    if not _is_app_package_release(latest_entry) or not dockerhub_latest:
        return None

    release_version = (latest_entry.get("version") or "").lstrip("vV")
    release_display = latest_entry.get("display_version") or release_version
    docker_version = (dockerhub_latest.get("version") or "").lstrip("vV")
    should_warn = False
    evidence = "version"

    if release_version and docker_version:
        should_warn = _normalize_version(release_version) > _normalize_version(docker_version)
    elif release_version:
        release_time = _parse_remote_timestamp(latest_entry.get("published_at", ""))
        docker_time = _parse_remote_timestamp(dockerhub_latest.get("published_at", ""))
        should_warn = bool(release_time and docker_time and release_time > docker_time)
        evidence = "timestamp"

    if not should_warn:
        return None

    docker_display = docker_version or "未知基线"
    action = f"请维护者在本地执行 scripts/push-docker-release.sh {release_version}，刷新 zasenjc/mediatree:latest。"
    message = (
        f"GitHub 最新应用包 release {release_display} 已发布，但 DockerHub latest 仍指向 {docker_display}。"
        "新安装用户可能还拿不到这个版本。"
    )
    return {
        "type": "dockerhub-latest-outdated",
        "severity": "warning",
        "release_version": release_version,
        "release_display_version": release_display,
        "release_published_at": latest_entry.get("published_at", ""),
        "dockerhub_latest_version": docker_version,
        "dockerhub_latest_updated_at": dockerhub_latest.get("published_at", ""),
        "evidence": evidence,
        "message": message,
        "action": action,
    }


# ─── Fetch full GitHub release body ───


async def fetch_github_release_body(version_tag: str) -> str:
    """Fetch full release body (CHANGELOG) from GitHub for a specific version tag."""
    tag = (version_tag or "").strip()
    candidates = []
    if tag:
        candidates.append(tag)
        stripped = tag.lstrip("vV")
        candidates.append(stripped if tag.lower().startswith("v") else f"v{stripped}")

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for candidate in dict.fromkeys(candidates):
            try:
                resp = await client.get(
                    f"{GITHUB_API}/tags/{candidate}",
                    headers={"Accept": "application/vnd.github.v3+json",
                             "User-Agent": "MediaTree-Updater/1.0"},
                )
                resp.raise_for_status()
                return (resp.json().get("body") or "").strip()
            except Exception as e:
                last_error = e
    logger.warning(f"Failed to fetch GitHub release body for {version_tag}: {last_error}")
    return ""


# ─── App package update operations ───


def _ensure_update_dirs() -> None:
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)


def _read_pointer(name: str) -> str:
    try:
        pointer = RELEASES_DIR / name
        if pointer.exists():
            return pointer.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _write_pointer(name: str, value: str) -> None:
    _ensure_update_dirs()
    (RELEASES_DIR / name).write_text(value.strip() + "\n", encoding="utf-8")


def _is_valid_app_dir(path: Path) -> bool:
    return (
        (path / "app" / "main.py").is_file()
        and (path / "frontend" / "dist" / "index.html").is_file()
        and (path / "VERSION").is_file()
    )


def _read_version_file(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
        return value.lstrip("vV")
    except Exception:
        return ""


def _is_app_package_release_dir(path: Path) -> bool:
    name = path.name
    if name.endswith(".staging"):
        name = name.removesuffix(".staging")
    return path.is_dir() and bool(_APP_PACKAGE_DIR_RE.match(name))


def _cleanup_old_app_packages(current_version: str) -> dict[str, list[str]]:
    """Remove stale app-package directories and archives after a successful update."""
    keep_versions = {
        (current_version or "").strip().lstrip("vV"),
        _read_pointer("current").lstrip("vV"),
    }
    previous = _read_pointer("previous").lstrip("vV")
    if previous and previous != "__base__" and _is_valid_app_dir(RELEASES_DIR / previous):
        keep_versions.add(previous)
    keep_versions.discard("")

    removed: dict[str, list[str]] = {"release_dirs": [], "archives": []}
    try:
        for path in RELEASES_DIR.iterdir():
            if path.name in {"current", "previous"}:
                continue
            if not _is_app_package_release_dir(path):
                continue
            package_version = path.name.removesuffix(".staging").lstrip("vV")
            if path.name.endswith(".staging") or package_version not in keep_versions:
                shutil.rmtree(path, ignore_errors=True)
                removed["release_dirs"].append(path.name)
    except FileNotFoundError:
        pass

    try:
        for archive in UPDATES_DIR.glob("mediatree-app-*.tar.gz"):
            archive_version = archive.name.removeprefix("mediatree-app-").removesuffix(".tar.gz").lstrip("vV")
            if archive_version not in keep_versions:
                try:
                    archive.unlink()
                    removed["archives"].append(archive.name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass

    removed["release_dirs"].sort()
    removed["archives"].sort()
    return removed


def _log_app_package_cleanup(removed: dict[str, list[str]]) -> None:
    if removed["release_dirs"] or removed["archives"]:
        logger.info(
            "Cleaned old app packages after update: "
            f"release_dirs={removed['release_dirs']} archives={removed['archives']}"
        )


def can_rollback() -> bool:
    previous = _read_pointer("previous")
    if previous == "__base__":
        return _is_valid_app_dir(BASE_APP_DIR)
    return bool(previous and _is_valid_app_dir(RELEASES_DIR / previous))


def _get_rollback_version() -> str:
    previous = _read_pointer("previous")
    if previous == "__base__":
        return _read_version_file(BASE_APP_DIR / "VERSION")
    if previous and _is_valid_app_dir(RELEASES_DIR / previous):
        return previous
    return ""


def _read_existing_update_status() -> dict:
    try:
        if UPDATE_STATUS_FILE.exists():
            return json.loads(UPDATE_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_update_status(
    status: str,
    version: str = "",
    downloaded: int = 0,
    total: int = 0,
    message: str = "",
    update_type: str = "",
    logs: list[str] | None = None,
) -> dict:
    _ensure_update_dirs()
    existing = _read_existing_update_status()
    payload = {
        "status": status,
        "version": version,
        "downloaded": downloaded,
        "total": total,
        "message": message,
        "update_type": update_type or existing.get("update_type", ""),
        "logs": [] if status == "idle" else (logs if logs is not None else existing.get("logs", [])),
        "can_rollback": can_rollback(),
        "rollback_version": _get_rollback_version(),
        "updated_at": int(time.time()),
    }
    tmp = UPDATE_STATUS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(UPDATE_STATUS_FILE)
    return payload


def get_update_status() -> dict:
    try:
        if UPDATE_STATUS_FILE.exists():
            payload = json.loads(UPDATE_STATUS_FILE.read_text(encoding="utf-8"))
            if payload.get("status") == "error" and payload.get("version"):
                current = get_version_state().get("current_version", "")
                if _normalize_version(current) >= _normalize_version(payload.get("version", "")):
                    return _write_update_status(
                        "success",
                        current,
                        message="更新已完成。",
                        update_type=payload.get("update_type", ""),
                        logs=[],
                    )
            payload["can_rollback"] = can_rollback()
            payload["rollback_version"] = _get_rollback_version()
            return payload
    except Exception:
        pass
    return _write_update_status("idle", message="")


def mark_update_success_after_restart() -> None:
    """Mark a previously requested restart as completed after app startup."""
    try:
        if not UPDATE_STATUS_FILE.exists():
            return
        payload = json.loads(UPDATE_STATUS_FILE.read_text(encoding="utf-8"))
        if payload.get("status") == "restarting":
            current_version = get_current_version()
            _write_update_status(
                "success",
                current_version,
                message="更新已完成。",
                update_type=payload.get("update_type", ""),
                logs=payload.get("logs", []),
            )
            if payload.get("update_type") == "app-package":
                try:
                    _log_app_package_cleanup(_cleanup_old_app_packages(current_version))
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean old app packages: {cleanup_error}")
    except Exception as e:
        logger.warning(f"Failed to mark update success after restart: {e}")


def _find_asset(assets: list[dict], version: str, suffix: str) -> dict | None:
    expected = f"mediatree-app-{version}{suffix}"
    expected_v = f"mediatree-app-v{version}{suffix}"
    for asset in assets:
        name = asset.get("name", "")
        if name in {expected, expected_v}:
            return asset
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith(suffix):
            return asset
    return None


def _find_windows_full_update_asset(assets: list[dict], version: str) -> dict | None:
    version = version.lstrip("vV")
    preferred_names = (
        f"MediaTree-Windows-{version}.exe",
        f"MediaTree-Windows-v{version}.exe",
        f"MediaTree-Windows-{version}-portable.zip",
        f"MediaTree-Windows-v{version}-portable.zip",
        f"MediaTree-Windows-{version}.appinstaller",
        f"MediaTree-Windows-v{version}.appinstaller",
        f"MediaTree-Windows-{version}.msix",
        f"MediaTree-Windows-v{version}.msix",
    )
    for expected in preferred_names:
        for asset in assets:
            if asset.get("name", "") == expected:
                return asset

    for suffix in (".exe", "-portable.zip", ".appinstaller", ".msix", ".zip"):
        for asset in assets:
            name = asset.get("name", "")
            if name.startswith("MediaTree-Windows-") and name.endswith(suffix):
                return asset
    return None


def _windows_full_update_reason(entry: dict) -> str:
    return (
        entry.get("windows_reason")
        or entry.get("reason")
        or "该版本需要下载新版 Windows 桌面版完整安装包。"
    )


async def _fetch_json_url(url: str) -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={"Accept": "application/json", "User-Agent": "MediaTree-Updater/1.0"},
        )
        resp.raise_for_status()
        return resp.json()


async def _build_release_entry(release: dict) -> dict:
    version = release.get("version", "")
    assets = release.get("assets") or []
    manifest_asset = _find_asset(assets, version, ".manifest.json")
    archive_asset = _find_asset(assets, version, ".tar.gz")
    sha_asset = _find_asset(assets, version, ".sha256")
    windows_asset = _find_windows_full_update_asset(assets, version)
    manifest = {}
    reason = ""

    if manifest_asset and manifest_asset.get("browser_download_url"):
        try:
            manifest = await _fetch_json_url(manifest_asset["browser_download_url"])
        except Exception as e:
            reason = f"应用包 manifest 读取失败: {e}"
    else:
        reason = "此版本没有应用包产物，请使用完整镜像更新。"

    requires_image = bool(manifest.get("requires_image_update")) if manifest else True
    requires_windows_base = bool(manifest.get("requires_windows_base_update")) if manifest else False
    if not reason:
        reason = manifest.get("reason", "")
    windows_reason = manifest.get("windows_reason", "") if manifest else ""
    base_api = int(manifest.get("base_api") or BASE_API_VERSION)
    base_api_requires_full = base_api > BASE_API_VERSION
    if base_api_requires_full:
        requires_image = True
        reason = "该应用包需要更新的基础镜像版本，请使用完整镜像更新。"
    missing_archive = archive_asset is None
    if not requires_image and missing_archive:
        requires_image = True
        reason = "release 中缺少应用包 tar.gz，请使用完整镜像更新。"
    update_type = "docker-image-required" if requires_image else "app-package"
    if UPDATE_PLATFORM == "windows":
        windows_full_required = requires_windows_base or base_api_requires_full or missing_archive or not manifest
        update_type = "windows-full-required" if windows_full_required else "app-package"
        if windows_full_required:
            reason = windows_reason or "该版本需要下载新版 Windows 桌面版完整安装包。"
        else:
            reason = windows_reason or "应用包更新；可在软件内完成。"

    return {
        "version": version,
        "display_version": release.get("display_version") or version,
        "name": release.get("name", ""),
        "published_at": release.get("published_at", ""),
        "html_url": release.get("html_url", ""),
        "body": release.get("body", ""),
        "source": "github-release",
        "update_type": update_type,
        "size": int(manifest.get("size") or archive_asset.get("size") or 0) if archive_asset else int(manifest.get("size") or 0),
        "requires_image_update": requires_image,
        "requires_windows_base_update": requires_windows_base,
        "reason": reason,
        "windows_reason": windows_reason,
        "manifest": manifest,
        "manifest_url": manifest_asset.get("browser_download_url") if manifest_asset else "",
        "archive_url": archive_asset.get("browser_download_url") if archive_asset else "",
        "sha256_url": sha_asset.get("browser_download_url") if sha_asset else "",
        "windows_download_url": windows_asset.get("browser_download_url") if windows_asset else "",
        "sha256": manifest.get("sha256", ""),
        "base_api": base_api,
    }


def _public_release_entry(entry: dict) -> dict:
    """Return only the stable API fields used by the frontend."""
    requires_image_update = bool(entry.get("requires_image_update"))
    required_image_version = entry.get("required_image_version", "")
    if UPDATE_PLATFORM == "windows":
        requires_image_update = False
        required_image_version = ""
    return {
        "version": entry.get("version", ""),
        "display_version": entry.get("display_version", ""),
        "published_at": entry.get("published_at", ""),
        "html_url": entry.get("html_url", ""),
        "source": entry.get("source", "github-release"),
        "update_type": entry.get("update_type", "docker-image-required"),
        "size": entry.get("size", 0),
        "requires_image_update": requires_image_update,
        "requires_windows_base_update": bool(entry.get("requires_windows_base_update")),
        "required_image_version": required_image_version,
        "reason": entry.get("reason", ""),
        "windows_reason": entry.get("windows_reason", ""),
        "windows_download_url": entry.get("windows_download_url", ""),
    }


def _find_blocking_image_release(
    entries: list[dict],
    base_version: str,
    target_version: str,
) -> dict | None:
    """Find image-required releases between the installed image and target app."""
    base_norm = _normalize_version(base_version)
    target_norm = _normalize_version(target_version)
    if not target_norm or target_norm <= base_norm:
        return None

    blocking = [
        entry
        for entry in entries
        if entry.get("requires_image_update")
        and base_norm < _normalize_version(entry.get("version", "")) <= target_norm
    ]
    if not blocking:
        return None
    return max(blocking, key=lambda entry: _normalize_version(entry.get("version", "")))


def _image_gate_reason(base_version: str, target_entry: dict, blocking_entry: dict) -> str:
    target_display = target_entry.get("display_version") or target_entry.get("version", "")
    blocking_display = blocking_entry.get("display_version") or blocking_entry.get("version", "")
    blocking_reason = blocking_entry.get("reason", "")
    reason = (
        f"从当前镜像内置版本 {base_version or 'unknown'} 升级到 {target_display} "
        f"会跨过需要完整镜像更新的 {blocking_display}，请先执行完整镜像更新。"
    )
    if blocking_reason:
        reason += f" {blocking_reason}"
    return reason


def _find_blocking_windows_full_release(
    entries: list[dict],
    base_version: str,
    target_version: str,
) -> dict | None:
    """Find Windows full-update releases between the bundled base and target app."""
    base_norm = _normalize_version(base_version)
    target_norm = _normalize_version(target_version)
    if not target_norm or target_norm <= base_norm:
        return None

    blocking = [
        entry
        for entry in entries
        if (
            entry.get("requires_windows_base_update")
            or entry.get("update_type") == "windows-full-required"
        )
        and base_norm < _normalize_version(entry.get("version", "")) <= target_norm
    ]
    if not blocking:
        return None
    return max(blocking, key=lambda entry: _normalize_version(entry.get("version", "")))


def _windows_full_gate_reason(base_version: str, target_entry: dict, blocking_entry: dict) -> str:
    target_display = target_entry.get("display_version") or target_entry.get("version", "")
    blocking_display = blocking_entry.get("display_version") or blocking_entry.get("version", "")
    blocking_reason = blocking_entry.get("windows_reason") or blocking_entry.get("reason", "")
    reason = (
        f"从当前安装包内置版本 {base_version or 'unknown'} 升级到 {target_display} "
        f"会跨过需要 Windows 全量更新的 {blocking_display}，请先下载安装新的 Windows 完整包。"
    )
    if blocking_reason:
        reason += f" {blocking_reason}"
    return reason


def _apply_image_update_gate(entries: list[dict], base_version: str) -> list[dict]:
    """Mark app-package releases as image-required when an older image is installed."""
    gated_entries: list[dict] = []
    for entry in entries:
        gated = dict(entry)
        if UPDATE_PLATFORM == "windows":
            if not gated.get("requires_windows_base_update") and gated.get("update_type") == "app-package":
                blocking = _find_blocking_windows_full_release(entries, base_version, gated.get("version", ""))
                if blocking:
                    gated["requires_windows_base_update"] = True
                    gated["update_type"] = "windows-full-required"
                    gated["windows_download_url"] = (
                        gated.get("windows_download_url") or blocking.get("windows_download_url", "")
                    )
                    gated["windows_reason"] = _windows_full_gate_reason(base_version, gated, blocking)
                    gated["reason"] = gated["windows_reason"]
            gated_entries.append(gated)
            continue

        if not gated.get("requires_image_update"):
            blocking = _find_blocking_image_release(entries, base_version, gated.get("version", ""))
            if blocking:
                gated["requires_image_update"] = True
                gated["update_type"] = "docker-image-required"
                gated["required_image_version"] = blocking.get("version", "")
                gated["reason"] = _image_gate_reason(base_version, gated, blocking)
        gated_entries.append(gated)
    return gated_entries


async def _get_release_entries(max_count: int = 30) -> list[dict]:
    releases = await fetch_github_releases(max_count=max_count)
    entries = await asyncio.gather(*(_build_release_entry(release) for release in releases))
    entries.sort(key=lambda x: _normalize_version(x["version"]), reverse=True)
    return entries


async def _get_release_entry(version: str) -> dict | None:
    version = version.lstrip("vV")
    entries = await _get_release_entries()
    base_version = get_base_version()
    for entry in _apply_image_update_gate(entries, base_version):
        if entry.get("version", "").lstrip("vV") == version:
            return entry
    return None


async def get_available_versions(include_registry_sync: bool = False) -> dict:
    """Fetch app package versions from GitHub Releases."""
    version_state = get_version_state()
    current = version_state["current_version"]
    effective = version_state["effective_version"]
    entries = await _get_release_entries()
    entries = _apply_image_update_gate(entries, version_state["base_version"])
    effective_norm = _normalize_version(effective)
    has_update = any(_normalize_version(v["version"]) > effective_norm for v in entries)
    latest_entry = entries[0] if entries else None
    dockerhub_latest = None
    latest_sync_warning = None
    if UPDATE_PLATFORM != "windows" and include_registry_sync and _is_app_package_release(latest_entry):
        dockerhub_latest = await fetch_dockerhub_latest_baseline()
        latest_sync_warning = _build_latest_sync_warning(latest_entry, dockerhub_latest)

    return {
        "current_version": current,
        "current_source": version_state["current_source"],
        "base_version": version_state["base_version"],
        "effective_version": effective,
        "overlay_active": version_state["overlay_active"],
        "overlay_is_outdated": version_state["overlay_is_outdated"],
        "status_note": version_state["status_note"],
        "has_update": has_update,
        "dockerhub_latest": dockerhub_latest,
        "latest_sync_warning": latest_sync_warning,
        "versions": [_public_release_entry(entry) for entry in entries[:4]],
    }


async def _read_remote_sha256(url: str) -> str:
    if not url:
        return ""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "MediaTree-Updater/1.0"})
        resp.raise_for_status()
        text = resp.text.strip()
    return text.split()[0] if text else ""


async def _download_file_with_status(url: str, path: Path, version: str) -> str:
    sha = hashlib.sha256()
    downloaded = 0
    total = 0
    async with httpx.AsyncClient(timeout=1800, follow_redirects=True) as client:
        async with client.stream("GET", url, headers={"User-Agent": "MediaTree-Updater/1.0"}) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0) or 0)
            _write_update_status("downloading", version, 0, total, "正在下载应用包...", update_type="app-package")
            with path.open("wb") as f:
                async for chunk in resp.aiter_bytes(1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
                    sha.update(chunk)
                    downloaded += len(chunk)
                    _write_update_status("downloading", version, downloaded, total, "正在下载应用包...", update_type="app-package")
    return sha.hexdigest()


def _safe_extract_tar(archive: Path, target: Path) -> None:
    target_root = target.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = (target / member.name).resolve()
            try:
                member_path.relative_to(target_root)
            except ValueError as exc:
                raise ValueError(f"Archive member escapes target directory: {member.name}") from exc
        tar.extractall(target)


def _request_process_restart(
    version: str,
    message: str = "更新成功，正在重启服务...",
    update_type: str = "app-package",
    logs: list[str] | None = None,
) -> None:
    _write_update_status("restarting", version, message=message, update_type=update_type, logs=logs)

    def _restart() -> None:
        time.sleep(1.0)
        os._exit(0)

    threading.Thread(target=_restart, name="mediatree-restart", daemon=True).start()


async def perform_app_package_update(version: str) -> dict:
    version_tag = version.lstrip("vV")
    if not version_tag or any(c in version_tag for c in _FORBIDDEN_CHARS):
        raise ValueError(f"Invalid version tag: {version}")

    entry = await _get_release_entry(version_tag)
    if not entry:
        return {"ok": False, "error": f"未找到版本 {version_tag} 的 release。"}
    if UPDATE_PLATFORM == "windows" and (
        entry.get("requires_windows_base_update")
        or entry.get("update_type") == "windows-full-required"
    ):
        return {
            "ok": False,
            "error": _windows_full_update_reason(entry),
            "requires_windows_base_update": True,
        }
    if UPDATE_PLATFORM != "windows" and entry.get("requires_image_update"):
        reason = entry.get("reason") or "该版本需要完整镜像更新。"
        return {"ok": False, "error": reason, "requires_image_update": True}
    if int(entry.get("base_api") or 0) > BASE_API_VERSION:
        if UPDATE_PLATFORM == "windows":
            return {
                "ok": False,
                "error": _windows_full_update_reason(entry),
                "requires_windows_base_update": True,
            }
        return {
            "ok": False,
            "error": "该应用包需要更新的基础镜像版本，请使用完整镜像更新。",
            "requires_image_update": True,
        }
    if not entry.get("archive_url"):
        return {"ok": False, "error": "release 中缺少应用包 tar.gz。"}

    _ensure_update_dirs()
    archive_path = UPDATES_DIR / f"mediatree-app-{version_tag}.tar.gz"
    staging_dir = RELEASES_DIR / f"{version_tag}.staging"
    final_dir = RELEASES_DIR / version_tag

    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        actual_sha = await _download_file_with_status(entry["archive_url"], archive_path, version_tag)
        expected_sha = entry.get("sha256") or await _read_remote_sha256(entry.get("sha256_url", ""))
        _write_update_status("verifying", version_tag, archive_path.stat().st_size, archive_path.stat().st_size, "正在校验应用包...", update_type="app-package")
        if expected_sha and actual_sha.lower() != expected_sha.lower():
            raise ValueError("应用包 sha256 校验失败。")

        _write_update_status("installing", version_tag, message="正在安装应用包...", update_type="app-package")
        _safe_extract_tar(archive_path, staging_dir)
        if not _is_valid_app_dir(staging_dir):
            raise ValueError("应用包结构无效，缺少 app/main.py、frontend/dist/index.html 或 VERSION。")

        package_version = (staging_dir / "VERSION").read_text(encoding="utf-8").strip().lstrip("vV")
        if package_version and package_version != version_tag:
            raise ValueError(f"应用包版本不匹配: {package_version} != {version_tag}")

        current = _read_pointer("current")
        if current and current != version_tag and _is_valid_app_dir(RELEASES_DIR / current):
            _write_pointer("previous", current)
        elif get_current_source() == "base" and get_current_version() != version_tag:
            _write_pointer("previous", "__base__")

        if final_dir.exists():
            shutil.rmtree(final_dir)
        staging_dir.replace(final_dir)
        _write_pointer("current", version_tag)

        _request_process_restart(version_tag, update_type="app-package")
        return {
            "ok": True,
            "message": f"已安装应用包 {version_tag}，服务正在重启...",
            "version": version_tag,
            "update_type": "app-package",
        }
    except Exception as e:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        _write_update_status("error", version_tag, message=str(e), update_type="app-package")
        logger.exception(f"App package update failed: {e}")
        return {"ok": False, "error": str(e)}


async def rollback_app_package() -> dict:
    previous = _read_pointer("previous")
    current = _read_pointer("current")
    if previous == "__base__":
        base_version = _read_version_file(BASE_APP_DIR / "VERSION") or get_current_version()
        if current:
            _write_pointer("previous", current)
        try:
            (RELEASES_DIR / "current").unlink()
        except FileNotFoundError:
            pass
        _request_process_restart(base_version, "已切换到镜像内置版本，正在重启服务...", update_type="app-package")
        return {"ok": True, "message": "已回滚到镜像内置版本，服务正在重启...", "version": base_version}
    if not previous or not _is_valid_app_dir(RELEASES_DIR / previous):
        return {"ok": False, "error": "没有可回滚的上一版本。"}
    if current:
        _write_pointer("previous", current)
    _write_pointer("current", previous)
    _request_process_restart(previous, "已切换到上一版本，正在重启服务...", update_type="app-package")
    return {"ok": True, "message": f"已回滚到 {previous}，服务正在重启...", "version": previous}


def _trim_update_logs(logs: list[str], limit: int = 120) -> list[str]:
    return _redact_logs(logs[-limit:])


async def _run_command_with_update_logs(
    cmd: list[str],
    version: str,
    status: str,
    message: str,
    timeout: int,
    logs: list[str],
) -> tuple[int, list[str]]:
    logs.append("$ " + _format_command_for_logs(cmd))
    _write_update_status(status, version, message=message, update_type="docker-image", logs=_trim_update_logs(logs))
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def consume(stream: asyncio.StreamReader | None) -> None:
        if not stream:
            return
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace").replace("\r", "\n")
            for line in text.splitlines():
                line = line.strip()
                if line:
                    logs.append(_redact_text(line))
            _write_update_status(status, version, message=message, update_type="docker-image", logs=_trim_update_logs(logs))

    try:
        await asyncio.wait_for(
            asyncio.gather(consume(process.stdout), consume(process.stderr), process.wait()),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        logs.append("操作超时。")
        _write_update_status("error", version, message="操作超时。", update_type="docker-image", logs=_trim_update_logs(logs))
        raise
    return process.returncode or 0, _trim_update_logs(logs)


# ─── Docker operations ───


def _check_docker_available() -> str | None:
    """Check if Docker socket and CLI are available. Returns error message or None if OK."""
    if not DOCKER_SOCKET.exists():
        return (
            "当前容器未挂载 Docker socket（/var/run/docker.sock），无法在设置页执行完整镜像更新。"
            "请在宿主机重新创建容器并挂载该 socket，或直接在宿主机执行 docker compose pull && docker compose up -d。"
        )
    if shutil.which("docker") is None:
        return (
            "当前镜像未包含 Docker CLI，无法在设置页内执行完整镜像更新。"
            "请在宿主机执行 docker compose pull && docker compose up -d（或按你原来的 docker run 方式重建容器）；"
            "如果希望以后在设置页直接完成完整镜像更新，请用 INCLUDE_DOCKER_CLI=true 重新构建镜像。"
        )
    return None


def _get_container_ids() -> list[str]:
    """Get possible container identifiers to try with docker inspect.

    Returns a list of candidates in priority order:
    1. Container ID from /proc/self/cgroup (most reliable)
    2. Hostname (Docker sets it to the short container ID by default)
    3. "mediatree" (the most common container name)
    """
    ids: list[str] = []

    # Method 1: Extract container ID from cgroup (works with most Docker setups)
    try:
        cgroup_text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
        # cgroup v2: 0::/system.slice/docker-<64-char-id>.scope
        # cgroup v1: <num>:<subsystem>:/docker/<64-char-id>
        for pattern in (r"/docker-([0-9a-f]{64})\.scope", r"/docker/([0-9a-f]{64})"):
            match = re.search(pattern, cgroup_text)
            if match:
                cid = match.group(1)
                # Docker inspect can use short ID (first 12 chars)
                ids.append(cid[:12])
                ids.append(cid)
                break
    except Exception:
        pass

    # Method 2: HOSTNAME (Docker default = short container ID)
    hostname = socket.gethostname()
    if hostname:
        ids.append(hostname)

    # Method 3: fallback — most common container name
    ids.append("mediatree")

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


def _inspect_container_config(container_id: str) -> dict | None:
    """Extract container runtime configuration via docker inspect.

    Returns a dict with keys: name, env, port_bindings, restart_policy,
    binds, mounts, network_mode, privileged, cap_add, labels,
    is_compose_managed, compose_project, compose_service.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", container_id],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        if not data:
            return None
        info = data[0]
        config = info.get("Config", {})
        host_config = info.get("HostConfig", {})
        labels = config.get("Labels") or {}
        compose_project = labels.get("com.docker.compose.project", "")

        return {
            "name": (info.get("Name") or "").lstrip("/"),
            "env": config.get("Env") or [],
            "port_bindings": host_config.get("PortBindings") or {},
            "restart_policy": host_config.get("RestartPolicy") or {},
            "binds": host_config.get("Binds") or [],
            "mounts": info.get("Mounts") or [],
            "network_mode": host_config.get("NetworkMode") or "",
            "privileged": host_config.get("Privileged", False),
            "cap_add": host_config.get("CapAdd") or [],
            "labels": labels,
            "is_compose_managed": bool(compose_project),
            "compose_project": compose_project,
            "compose_service": labels.get("com.docker.compose.service", ""),
        }
    except Exception:
        return None


def _yaml_dq(value: str) -> str:
    """Escape a string for inclusion inside a YAML double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_compose_yaml(config: dict, version_tag: str) -> str:
    """Build a minimal docker-compose.yml from container inspect config.

    Skips: compose-file bind mounts (/compose.yml), COMPOSE_FILE env var.
    """
    lines: list[str] = []
    service = config.get("compose_service") or config.get("name") or "mediatree"

    lines.append("services:")
    lines.append(f"  {service}:")
    lines.append(f"    image: zasenjc/mediatree:{version_tag}")

    name = config.get("name", "")
    if name:
        lines.append(f'    container_name: "{_yaml_dq(name)}"')

    restart = config.get("restart_policy", {})
    restart_name = restart.get("Name", "")
    if restart_name:
        lines.append(f'    restart: "{_yaml_dq(restart_name)}"')

    # Ports
    port_bindings = config.get("port_bindings", {})
    if port_bindings:
        lines.append("    ports:")
        for container_port, host_bindings in port_bindings.items():
            port_num = container_port.split("/")[0]
            for binding in host_bindings:
                host_ip = binding.get("HostIp", "")
                host_port = binding.get("HostPort", "")
                if host_ip:
                    lines.append(f'      - "{host_ip}:{host_port}:{port_num}"')
                else:
                    lines.append(f'      - "{host_port}:{port_num}"')

    # Volumes
    mounts = config.get("mounts", [])
    vol_lines: list[str] = []
    for mount in mounts:
        if mount.get("Type") != "bind":
            continue
        src = mount.get("Source", "")
        dst = mount.get("Destination", "")
        if not src or not dst:
            continue
        if dst == "/compose.yml":
            continue
        mode = mount.get("Mode", "")
        vol_spec = f"{src}:{dst}"
        if mode and mode != "rw":
            vol_spec += f":{mode}"
        vol_lines.append(f'      - "{_yaml_dq(vol_spec)}"')

    if vol_lines:
        lines.append("    volumes:")
        lines.extend(vol_lines)

    # Environment
    env_vars = config.get("env", [])
    env_lines: list[str] = []
    for env in env_vars:
        if env.startswith("COMPOSE_FILE="):
            continue
        env_lines.append(f'      - "{_yaml_dq(env)}"')

    if env_lines:
        lines.append("    environment:")
        lines.extend(env_lines)

    # Network mode (skip default bridge)
    network_mode = config.get("network_mode", "")
    if network_mode and network_mode not in ("", "bridge", "default"):
        lines.append(f'    network_mode: "{_yaml_dq(network_mode)}"')

    # Privileged
    if config.get("privileged"):
        lines.append("    privileged: true")

    # Capabilities
    cap_add = config.get("cap_add", [])
    if cap_add:
        lines.append("    cap_add:")
        for cap in cap_add:
            lines.append(f"      - {cap}")

    return "\n".join(lines) + "\n"


def _build_docker_run_cmd(config: dict, version_tag: str) -> list[str]:
    """Build a 'docker run' command from inspect config that replays the
    current container configuration with a new image tag.

    All container labels are preserved so management tools can still
    identify the container.  Compose-file bind mounts and COMPOSE_FILE
    env var are skipped.
    """
    cmd = ["docker", "run", "-d"]

    # Container name
    name = config.get("name", "")
    if name:
        cmd.extend(["--name", name])

    # Restart policy
    restart = config.get("restart_policy", {})
    restart_name = restart.get("Name", "")
    if restart_name:
        cmd.extend(["--restart", restart_name])

    # Ports
    port_bindings = config.get("port_bindings", {})
    for container_port, host_bindings in port_bindings.items():
        port_num = container_port.split("/")[0]
        for binding in host_bindings:
            host_ip = binding.get("HostIp", "")
            host_port = binding.get("HostPort", "")
            if host_ip:
                cmd.extend(["-p", f"{host_ip}:{host_port}:{port_num}"])
            else:
                cmd.extend(["-p", f"{host_port}:{port_num}"])

    # Volumes
    mounts = config.get("mounts", [])
    for mount in mounts:
        if mount.get("Type") != "bind":
            continue
        src = mount.get("Source", "")
        dst = mount.get("Destination", "")
        if not src or not dst:
            continue
        if dst == "/compose.yml":
            continue
        mode = mount.get("Mode", "")
        vol_spec = f"{src}:{dst}"
        if mode and mode != "rw":
            vol_spec += f":{mode}"
        cmd.extend(["-v", vol_spec])

    # Environment variables
    for env in config.get("env", []):
        if env.startswith("COMPOSE_FILE="):
            continue
        cmd.extend(["-e", env])

    # Network mode (skip default bridge)
    network_mode = config.get("network_mode", "")
    if network_mode and network_mode not in ("", "bridge", "default"):
        cmd.extend(["--network", network_mode])

    # Privileged mode
    if config.get("privileged"):
        cmd.append("--privileged")

    # Capabilities
    for cap in config.get("cap_add", []):
        cmd.extend(["--cap-add", cap])

    # Container labels (preserve compose project association for management tools)
    for key, value in config.get("labels", {}).items():
        cmd.extend(["-l", f"{key}={value}"])

    # Image
    cmd.append(f"zasenjc/mediatree:{version_tag}")

    return cmd


async def perform_docker_update(version: str) -> dict:
    """
    Pull a Docker image and restart the container with the new version.

    For compose-managed containers (detected via labels) it reconstructs a
    minimal compose YAML and uses docker compose up -d so management tools
    keep tracking.  For plain docker-run containers it rebuilds via docker run.

    Flow:
    1. Validate version + check Docker availability
    2. docker inspect own container for runtime config
    3. docker pull zasenjc/mediatree:<version>
    4. If compose-managed: compose up -d (via helper)
       Else: stop + rm + run (via helper)
    """
    version_tag = version.lstrip("vV")

    if not version_tag or any(c in version_tag for c in _FORBIDDEN_CHARS):
        raise ValueError(f"Invalid version tag: {version}")

    logs: list[str] = []
    _write_update_status(
        "installing",
        version_tag,
        message="正在准备完整镜像更新...",
        update_type="docker-image",
        logs=logs,
    )

    docker_error = _check_docker_available()
    if docker_error:
        logs.append(docker_error)
        _write_update_status(
            "error",
            version_tag,
            message=docker_error,
            update_type="docker-image",
            logs=_trim_update_logs(logs),
        )
        return {"ok": False, "error": docker_error}

    # Try each possible container identifier until one works
    config = None
    for cid in _get_container_ids():
        config = _inspect_container_config(cid)
        if config:
            logger.info(f"Inspected container via identifier: {cid}")
            break
        logger.debug(f"Inspect failed for {cid}, trying next candidate")

    if not config:
        error = ("Cannot inspect running container. "
                 "Ensure docker.sock is mounted and the container is running.")
        logs.append(error)
        _write_update_status(
            "error",
            version_tag,
            message=error,
            update_type="docker-image",
            logs=_trim_update_logs(logs),
        )
        return {"ok": False, "error": error}

    container_name = config.get("name", "mediatree")
    is_compose = config.get("is_compose_managed", False)
    compose_project = config.get("compose_project", "")

    logger.info(
        f"Starting update to version {version_tag} "
        f"(container: {container_name}, compose: {is_compose})"
    )

    try:
        # ── Step 1: Pull new mediatree image ──
        pull_cmd = ["docker", "pull", f"zasenjc/mediatree:{version_tag}"]
        logger.info(f"Running: {' '.join(pull_cmd)}")
        pull_code, logs = await _run_command_with_update_logs(
            pull_cmd,
            version_tag,
            "downloading",
            f"正在拉取 Docker 镜像 zasenjc/mediatree:{version_tag}...",
            300,
            logs,
        )
        if pull_code != 0:
            error_msg = "\n".join(logs[-8:])[:500]
            logger.error(f"Docker pull failed: {error_msg}")
            _write_update_status(
                "error",
                version_tag,
                message=f"镜像拉取失败: {error_msg}",
                update_type="docker-image",
                logs=_trim_update_logs(logs),
            )
            return {"ok": False, "error": f"镜像拉取失败: {error_msg}"}

        logger.info(f"Docker pull succeeded for {version_tag}")
        logs.append(f"镜像 zasenjc/mediatree:{version_tag} 拉取完成。")
        _write_update_status(
            "installing",
            version_tag,
            message="正在准备 Docker helper...",
            update_type="docker-image",
            logs=_trim_update_logs(logs),
        )

        # ── Step 2: Ensure docker:cli helper image is available ──
        check_cli = await asyncio.create_subprocess_exec(
            "docker", "image", "inspect", "docker:cli",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await check_cli.wait()
        if check_cli.returncode != 0:
            logger.info("Pulling docker:cli helper image...")
            cli_code, logs = await _run_command_with_update_logs(
                ["docker", "pull", "docker:cli"],
                version_tag,
                "downloading",
                "正在拉取 Docker helper 镜像...",
                120,
                logs,
            )
            if cli_code != 0:
                error_msg = "\n".join(logs[-8:])[:500]
                _write_update_status(
                    "error",
                    version_tag,
                    message=f"无法拉取 helper 镜像: {error_msg}",
                    update_type="docker-image",
                    logs=_trim_update_logs(logs),
                )
                return {"ok": False, "error": f"无法拉取 helper 镜像: {error_msg}"}
        else:
            logs.append("Docker helper 镜像已存在。")

        # ── Step 3: Execute update ──
        if is_compose and compose_project:
            # ── Compose path: reconstruct compose YAML + compose up -d ──
            compose_yaml = _build_compose_yaml(config, version_tag)
            project_q = shlex.quote(compose_project)
            compose_script = (
                f"cat > /tmp/c.yml && "
                f"docker compose -f /tmp/c.yml --project-name {project_q} up -d"
            )
            logger.info(f"Compose update — project={compose_project}")

            up_cmd = [
                "docker", "run", "--rm",
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "-i",
                "docker:cli", "sh", "-c", compose_script,
            ]
            logger.info(f"Launching helper container for compose up")
            logs.append("正在通过 docker compose 启动新版本容器。")
            logs.append("$ " + _format_command_for_logs(up_cmd))
            _write_update_status(
                "restarting",
                version_tag,
                message="正在执行 Docker Compose 更新，服务将短暂重启...",
                update_type="docker-image",
                logs=_trim_update_logs(logs),
            )

            # Fire-and-forget with stdin pipe for compose YAML
            process = subprocess.Popen(
                up_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                process.stdin.write(compose_yaml.encode("utf-8"))
                process.stdin.close()
            except Exception:
                pass
        else:
            # ── Docker run path: stop + rm + run ──
            run_cmd = _build_docker_run_cmd(config, version_tag)
            run_cmd_str = _format_command_for_logs(run_cmd)
            name_q = shlex.quote(container_name)
            script = (
                f"docker stop {name_q} 2>/dev/null; "
                f"docker rm -f {name_q} 2>/dev/null; "
                f"{run_cmd_str}"
            )
            logger.info(f"Docker run update — cmd: {run_cmd_str[:200]}...")

            up_cmd = [
                "docker", "run", "--rm",
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "docker:cli", "sh", "-c", script,
            ]
            logger.info("Launching helper container for docker run")
            logs.append("正在通过 docker run 启动新版本容器。")
            logs.append("$ " + _format_command_for_logs(up_cmd))
            _write_update_status(
                "restarting",
                version_tag,
                message="正在执行 Docker 容器替换，服务将短暂重启...",
                update_type="docker-image",
                logs=_trim_update_logs(logs),
            )

            subprocess.Popen(
                up_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        logger.info(f"Update to {version_tag} triggered via helper container")
        return {
            "ok": True,
            "message": f"已更新到 {version_tag}，容器正在重启...",
            "version": version_tag,
            "update_type": "docker-image",
        }

    except asyncio.TimeoutError:
        logger.error("Docker operation timed out")
        _write_update_status(
            "error",
            version_tag,
            message="操作超时（5分钟），请检查网络连接",
            update_type="docker-image",
            logs=_trim_update_logs(logs),
        )
        return {"ok": False, "error": "操作超时（5分钟），请检查网络连接"}
    except Exception as e:
        logger.exception(f"Update failed: {e}")
        logs.append(_redact_text(str(e)))
        _write_update_status(
            "error",
            version_tag,
            message=f"更新失败: {str(e)[:500]}",
            update_type="docker-image",
            logs=_trim_update_logs(logs),
        )
        return {"ok": False, "error": f"更新失败: {str(e)[:500]}"}


async def perform_update(version: str, mode: str = "auto") -> dict:
    """Default update entrypoint.

    App-package updates are the default. Docker image replacement is retained
    only when the caller explicitly requests mode="docker-image".
    """
    mode = (mode or "auto").strip()
    if mode == "docker-image":
        return await perform_docker_update(version)
    if mode not in {"auto", "app-package"}:
        return {"ok": False, "error": f"Unsupported update mode: {mode}"}
    return await perform_app_package_update(version)
