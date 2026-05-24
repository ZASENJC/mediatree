"""
MediaTree update checker and Docker-based self-upgrade.

Checks DockerHub Tags for newer versions and triggers a Docker
container self-update.  The update flow uses docker inspect to
extract the running container's configuration.

For compose-managed containers (detected via labels) it reconstructs
a minimal compose YAML and uses docker compose up -d so management
tools like dpanel/Portainer keep tracking the container.  For plain
docker-run containers it rebuilds via docker run.

The actual restart is executed inside a helper container
(docker:cli) so the process survives when the main container
is stopped (cgroup isolation).
"""
import asyncio
import httpx
import json
import re
import shlex
import shutil
import socket
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

DOCKER_SOCKET = Path("/var/run/docker.sock")

# Shell metacharacters to reject in version strings
_FORBIDDEN_CHARS = set(";&|$`\\\n\r")

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
    """Read current version — Docker image tag preferred, VERSION file fallback."""
    tag = _get_running_image_tag()
    if tag:
        return tag

    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "unknown"


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


async def perform_update(version: str) -> dict:
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

    docker_error = _check_docker_available()
    if docker_error:
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
        return {"ok": False, "error": "Cannot inspect running container. "
                "Ensure docker.sock is mounted and the container is running."}

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

        # ── Step 2: Ensure docker:cli helper image is available ──
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
            run_cmd_str = ' '.join(shlex.quote(arg) for arg in run_cmd)
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
        }

    except asyncio.TimeoutError:
        logger.error("Docker operation timed out")
        return {"ok": False, "error": "操作超时（5分钟），请检查网络连接"}
    except Exception as e:
        logger.exception(f"Update failed: {e}")
        return {"ok": False, "error": f"更新失败: {str(e)[:500]}"}
