"""
MediaTree update checker and Docker-based self-upgrade.

Checks DockerHub Tags for newer versions and triggers a Docker
container self-update.  The update flow uses a helper container
(docker:cli) to run docker compose up -d, so the compose process
survives when the main container is stopped (cgroup isolation).
"""
import asyncio
import httpx
import os
import shutil
import subprocess
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


def _check_docker_available() -> str | None:
    """Check if Docker socket and CLI are available. Returns error message or None if OK."""
    if not DOCKER_SOCKET.exists():
        return ("Docker socket not available. "
                "Mount /var/run/docker.sock for self-update.")
    if shutil.which("docker") is None:
        return ("Docker CLI not found in container. "
                "Rebuild your image with the latest Dockerfile that includes docker-ce-cli.")
    return None


async def _get_compose_project_name() -> str | None:
    """Get docker compose project name from the running container."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker", "inspect", "mediatree",
            "--format", '{{index .Config.Labels "com.docker.compose.project"}}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        name = stdout.decode().strip()
        return name if name else None
    except Exception:
        return None


def _build_temp_compose(original: str, version_tag: str) -> str:
    """Generate a clean compose-only-override with the target image tag.

    - Replaces image: line with the target version
    - Strips the compose-file bind mount (avoid relative-path /tmp resolution bug)
    - Strips container_name (avoid cross-project name conflicts)
    - Strips env_file (avoid relative path issues from /tmp)
    - Strips build: section (force using the pulled image)
    """
    import re

    # 1. Replace image tag
    updated = re.sub(
        r"image:\s*\S+",
        f"image: zasenjc/mediatree:{version_tag}",
        original,
        count=1,
    )

    lines = updated.split("\n")
    result = []
    in_build = False
    in_envfile = False

    for line in lines:
        stripped = line.strip()

        # Strip container_name
        if stripped.startswith("container_name:"):
            continue

        # Strip compose-file bind mount (avoid relative-path /tmp resolution bug)
        if "docker-compose.yml" in stripped and "/compose.yml" in stripped:
            continue

        # Strip build: section (both inline "build: ." and multi-line)
        if stripped.startswith("build:"):
            if stripped != "build:":
                # Inline: "build: ." — skip this line
                continue
            in_build = True
            continue
        if in_build:
            # build: is followed by an indented value (e.g. "build: .")
            # If this line is less indented or at service level, we're out
            if line and not line[0].isspace():
                in_build = False
                result.append(line)
            # Otherwise skip (the build value, e.g. just ".")
            continue

        # Strip env_file: section
        if stripped.startswith("env_file:"):
            if stripped != "env_file:":
                # Inline: env_file: path
                continue
            in_envfile = True
            continue
        if in_envfile:
            if stripped.startswith("-"):
                continue
            in_envfile = False
            result.append(line)
            continue

        result.append(line)

    return "\n".join(result)


async def perform_update(version: str) -> dict:
    """
    Pull a Docker image and restart the container with the new version.

    Uses a helper container (docker:cli) to run docker compose up -d.
    The helper runs in its own cgroup, so it survives when the main
    container is stopped during the compose operation.

    Flow:
    1. Validate version + check Docker availability
    2. docker pull zasenjc/mediatree:<version>
    3. Generate temp compose YAML in memory
    4. Ensure docker:cli helper image is available
    5. Pipe compose YAML to a helper container that runs compose up -d
    """
    version_tag = version.lstrip("vV")

    if not version_tag or any(c in version_tag for c in _FORBIDDEN_CHARS):
        raise ValueError(f"Invalid version tag: {version}")

    docker_error = _check_docker_available()
    if docker_error:
        return {"ok": False, "error": docker_error}

    compose_file = COMPOSE_FILE
    if compose_file and not Path(compose_file).is_file():
        compose_file = ""  # ENV points to missing file, fall through to candidates
    if not compose_file:
        for candidate in ["/app/docker-compose.yml", "/docker-compose.yml", "/app/data/docker-compose.yml"]:
            if Path(candidate).is_file():
                compose_file = candidate
                break
    if not compose_file or not Path(compose_file).is_file():
        return {"ok": False, "error": "docker-compose.yml not found. "
                "Set COMPOSE_FILE environment variable."}

    try:
        original = Path(compose_file).read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Cannot read compose file: {e}"}

    # Persist compose content to data volume so the next container can find it
    # even though the compose-file bind mount is stripped from the temp compose.
    try:
        data_compose = Path("/app/data/docker-compose.yml")
        data_compose.parent.mkdir(parents=True, exist_ok=True)
        data_compose.write_text(original, encoding="utf-8")
    except Exception:
        pass  # Non-critical, fallback to other paths on next update

    logger.info(f"Starting update to version {version_tag}")

    try:
        # ── Step 1: Pull new mediatree image ──
        pull_cmd = ["docker", "pull", f"zasenjc/mediatree:{version_tag}"]
        logger.info(f"Running: {' '.join(pull_cmd)}")
        pull_process = await asyncio.create_subprocess_exec(
            *pull_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, pull_stderr = await asyncio.wait_for(pull_process.communicate(), timeout=300)
        if pull_process.returncode != 0:
            error_msg = pull_stderr.decode("utf-8", errors="replace")[:500]
            logger.error(f"Docker pull failed: {error_msg}")
            return {"ok": False, "error": f"镜像拉取失败: {error_msg}"}

        logger.info(f"Docker pull succeeded for {version_tag}")

        # ── Step 2: Build temp compose YAML in memory ──
        # The compose-file bind mount is stripped — it causes a directory to be
        # created at /compose.yml when the helper runs compose from /tmp.
        # Compose content is persisted to /app/data/docker-compose.yml instead.
        temp_yaml = _build_temp_compose(original, version_tag)
        logger.info("Temp compose YAML generated (compose-file mount stripped)")

        # ── Step 3: Get compose project name ──
        project_name = await _get_compose_project_name() or "mediatree"

        # ── Step 4: Ensure docker:cli helper image is available ──
        check_cli = await asyncio.create_subprocess_exec(
            "docker", "image", "inspect", "docker:cli",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await check_cli.wait()
        if check_cli.returncode != 0:
            logger.info("Pulling docker:cli helper image...")
            cli_pull = await asyncio.create_subprocess_exec(
                "docker", "pull", "docker:cli",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, cli_stderr = await asyncio.wait_for(cli_pull.communicate(), timeout=120)
            if cli_pull.returncode != 0:
                error_msg = cli_stderr.decode("utf-8", errors="replace")[:500]
                return {"ok": False, "error": f"无法拉取 helper 镜像: {error_msg}"}

        # ── Step 5: Run compose up -d inside a helper container ──
        # The helper container has its own cgroup (not part of our compose
        # project), so it survives when docker compose stops the main container.
        # Compose YAML is piped via stdin — no shared filesystem needed.
        up_cmd = [
            "docker", "run", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-i",
            "docker:cli",
            "sh", "-c",
            f"cat > /tmp/c.yml && docker compose -f /tmp/c.yml --project-name {project_name} up -d"
        ]
        logger.info(f"Launching helper container for compose up (project={project_name})")

        # Fire-and-forget: write compose to stdin then detach.
        # Our process may die when compose stops the main container,
        # but the helper container continues independently.
        process = subprocess.Popen(
            up_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            process.stdin.write(temp_yaml.encode("utf-8"))
            process.stdin.close()
        except Exception:
            pass  # Process may already be gone, helper handles it

        logger.info(f"Update to {version_tag} triggered via helper container")
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
