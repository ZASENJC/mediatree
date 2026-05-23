"""
MediaTree update checker and Docker-based self-upgrade.

Checks GitHub Releases and DockerHub Tags for newer versions,
and can trigger a Docker container self-update.
"""
import asyncio
import httpx
import os
from pathlib import Path
from .config import settings, logger

# ─── Constants ───

GITHUB_REPO = "ZASENJC/mediatree"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
DOCKERHUB_TAGS_API = "https://hub.docker.com/v2/repositories/zasenjc/mediatree/tags/?page_size=20"

# VERSION file path — try container path first, then development path
_VERSION_CONTAINER = Path(__file__).parent.parent / "VERSION"
_VERSION_DEV = Path(__file__).parent.parent.parent / "VERSION"
VERSION_FILE = _VERSION_CONTAINER if _VERSION_CONTAINER.exists() else _VERSION_DEV

# Docker socket and compose paths
DOCKER_SOCKET = Path("/var/run/docker.sock")
COMPOSE_FILE = os.environ.get("COMPOSE_FILE", "")

# Shell metacharacters to reject in version strings
_FORBIDDEN_CHARS = set(";&|$`\\\n\r")

# ─── Version utilities ───


def get_current_version() -> str:
    """Read current version from VERSION file, with fallback."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "unknown"


def _normalize_version(v: str) -> tuple:
    """Convert version string like 'v1.2.3' or '1.2.3' to comparable tuple."""
    v = (v or "").strip().lstrip("vV")
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
                result.append({
                    "version": (rel.get("tag_name") or "").lstrip("vV"),
                    "display_version": rel.get("tag_name", ""),
                    "name": rel.get("name", ""),
                    "published_at": rel.get("published_at", ""),
                    "html_url": rel.get("html_url", ""),
                    "body": (rel.get("body") or "")[:200],
                    "source": "github",
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


# ─── Fetch full GitHub release body ───


async def fetch_github_release_body(version_tag: str) -> str:
    """Fetch full release body (CHANGELOG) from GitHub for a specific version tag."""
    tag = version_tag if version_tag.lower().startswith("v") else f"v{version_tag}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                f"{GITHUB_API}/tags/{tag}",
                headers={"Accept": "application/vnd.github.v3+json",
                         "User-Agent": "MediaTree-Updater/1.0"},
            )
            resp.raise_for_status()
            return (resp.json().get("body") or "").strip()
    except Exception as e:
        # Try without 'v' prefix if the first attempt failed
        if version_tag.lower().startswith("v"):
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(
                        f"{GITHUB_API}/tags/{version_tag.lstrip('vV')}",
                        headers={"Accept": "application/vnd.github.v3+json",
                                 "User-Agent": "MediaTree-Updater/1.0"},
                    )
                    resp.raise_for_status()
                    return (resp.json().get("body") or "").strip()
            except Exception:
                pass
        logger.warning(f"Failed to fetch GitHub release body for {version_tag}: {e}")
        return ""


# ─── Merged version list ───


async def get_available_versions() -> dict:
    """
    Fetch versions from DockerHub tags.
    Returns list sorted by version descending.
    """
    current = get_current_version()
    versions = await fetch_dockerhub_tags()

    # Sort descending by version
    versions.sort(key=lambda x: _normalize_version(x["version"]), reverse=True)

    # Determine if there is a newer version
    current_norm = _normalize_version(current)
    has_update = any(_normalize_version(v["version"]) > current_norm for v in versions)

    return {
        "current_version": current,
        "has_update": has_update,
        "versions": versions[:4],
    }


# ─── Docker operations ───


def _check_docker_available() -> bool:
    """Check if Docker socket is accessible for self-upgrade."""
    return DOCKER_SOCKET.exists()


async def perform_update(version: str) -> dict:
    """
    Pull the specified Docker image and trigger container restart.

    Steps:
    1. Validate version tag (reject shell metacharacters)
    2. Verify Docker socket is available
    3. Pull the target image: docker pull zasenjc/mediatree:<version>
    4. Generate a temporary compose override file with the target image
    5. Run: docker compose -f <compose_file> up -d
    """
    version_tag = version.lstrip("vV")

    # Security: reject version strings with shell metacharacters
    if not version_tag or any(c in version_tag for c in _FORBIDDEN_CHARS):
        raise ValueError(f"Invalid version tag: {version}")

    # Check Docker availability
    if not _check_docker_available():
        return {
            "ok": False,
            "error": "Docker socket not available. "
                     "Mount /var/run/docker.sock for self-update.",
        }

    # Resolve compose file
    compose_file = COMPOSE_FILE
    if not compose_file:
        for candidate in ["/app/docker-compose.yml", "/docker-compose.yml"]:
            if Path(candidate).exists():
                compose_file = candidate
                break

    if not compose_file or not Path(compose_file).exists():
        return {
            "ok": False,
            "error": "docker-compose.yml not found. "
                     "Set COMPOSE_FILE environment variable.",
        }

    # Read the original compose file
    try:
        original = Path(compose_file).read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Cannot read compose file: {e}"}

    logger.info(f"Starting update to version {version_tag}")

    try:
        # Step 1: Pull the image
        pull_cmd = ["docker", "pull", f"zasenjc/mediatree:{version_tag}"]
        logger.info(f"Running: {' '.join(pull_cmd)}")

        pull_process = await asyncio.create_subprocess_exec(
            *pull_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        pull_stdout, pull_stderr = await asyncio.wait_for(
            pull_process.communicate(), timeout=300
        )

        if pull_process.returncode != 0:
            error_msg = pull_stderr.decode("utf-8", errors="replace")[:500]
            logger.error(f"Docker pull failed: {error_msg}")
            return {"ok": False, "error": f"镜像拉取失败: {error_msg}"}

        logger.info(f"Docker pull succeeded for {version_tag}")

        # Step 2: Generate temporary compose override with pinned image tag
        # Replace build: . with image: zasenjc/mediatree:<tag>
        updated = original
        image_line = f"zasenjc/mediatree:{version_tag}"

        # If the compose has an existing image line, replace it
        if "image:" in updated:
            import re
            updated = re.sub(
                r"image:\s*\S+",
                f"image: {image_line}",
                updated,
            )

        # If compose uses build: ., replace with image (only if no image line)
        if "build:" in updated:
            lines = updated.split("\n")
            new_lines = []
            skip_next = False
            for line in lines:
                if skip_next:
                    skip_next = False
                    continue
                if "build:" in line and "image:" not in line:
                    new_lines.append(f"    image: {image_line}")
                    skip_next = False
                    continue
                new_lines.append(line)
            updated = "\n".join(new_lines)

        temp_compose = Path("/tmp/mediatree-update-compose.yml")
        temp_compose.write_text(updated, encoding="utf-8")

        # Step 3: Recreate container
        up_cmd = ["docker", "compose", "-f", str(temp_compose), "up", "-d"]
        logger.info(f"Running: {' '.join(up_cmd)}")

        up_process = await asyncio.create_subprocess_exec(
            *up_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        up_stdout, up_stderr = await asyncio.wait_for(
            up_process.communicate(), timeout=120
        )

        if up_process.returncode != 0:
            error_msg = up_stderr.decode("utf-8", errors="replace")[:500]
            logger.error(f"Docker compose up failed: {error_msg}")
            return {"ok": False, "error": f"容器重启失败: {error_msg}"}

        logger.info(f"Update to {version_tag} completed, container is restarting")
        return {
            "ok": True,
            "message": f"已更新到 {version_tag}，容器正在重启...",
            "version": version_tag,
        }

    except asyncio.TimeoutError:
        logger.error("Docker operation timed out")
        return {"ok": False, "error": "操作超时（5分钟），请检查网络连接"}
    except Exception as e:
        logger.exception(f"Update failed: {e}")
        return {"ok": False, "error": f"更新失败: {str(e)[:500]}"}
