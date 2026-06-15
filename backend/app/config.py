from pydantic_settings import BaseSettings
from pathlib import Path
import base64
import json
import os
import logging
from logging.handlers import RotatingFileHandler

log_dir = None
log_file = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mediatree")

_INTERNAL_SCRAPER_POLICY_DEFAULTS = {
    "javdb_cache_hours": 24,
    "javdb_request_interval": 3.0,
    "tmdb_cache_hours": 168,
    "bangumi_cache_hours": 168,
}
_INTERNAL_SCRAPER_POLICY_KEYS = set(_INTERNAL_SCRAPER_POLICY_DEFAULTS)
_ENV_ONLY_KEYS = {"enable_builtin_scraper_plugins"}


def setup_file_logging(data_dir: str):
    global log_dir, log_file
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mediatree.log"
    try:
        fh = RotatingFileHandler(str(log_file), maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(fh)
        logger.info("File logging initialized")
    except Exception as e:
        logger.warning(f"File logging setup failed: {e}")


class Settings(BaseSettings):
    media_root: str = "/media"
    data_dir: str = str(Path(__file__).parent.parent.parent / "data")
    enable_builtin_scraper_plugins: bool = True

    javdb_enabled: bool = True
    javdb_base_url: str = "https://www.javdatabase.com"
    javdb_cache_hours: int = 24
    javdb_request_interval: float = 3.0
    tmdb_cache_hours: int = 168
    bangumi_cache_hours: int = 168
    tmdb_api_key: str = ""
    tmdb_access_token: str = ""
    scrape_concurrency_per_library: int = 8
    scrape_global_concurrency: int = 16
    scraper_api_concurrency: int = 8
    scraper_http_timeout: float = 10.0

    # Update
    update_check_enabled: bool = True
    update_check_interval_hours: int = 24

    scan_on_startup: bool = True

    auth_user: str = ""
    auth_pass: str = ""
    auth_password_hash: str = ""

    def __init__(self, **values):
        super().__init__(**values)
        self._apply_internal_scraper_policy_defaults()

    def _apply_internal_scraper_policy_defaults(self):
        for key, val in _INTERNAL_SCRAPER_POLICY_DEFAULTS.items():
            setattr(self, key, val)

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / "browser.db")

    @property
    def covers_dir(self) -> str:
        d = str(Path(self.data_dir) / "covers")
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def config_path(self) -> str:
        return str(Path(self.data_dir) / "config.json")

    @property
    def auth_enabled(self) -> bool:
        return self.auth_configured

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth_user and (self.auth_pass or self.auth_password_hash))

    @property
    def auth_token(self) -> str:
        raw = f"{self.auth_user}:{self.auth_pass}"
        return base64.b64encode(raw.encode()).decode()

    def get_all_media_roots(self) -> list[str]:
        base = Path(self.media_root)
        if not base.exists() or not base.is_dir():
            return []
        roots = []
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.'):
                roots.append(str(entry))
        return roots

    def canonical_media_root(self, media_root: str) -> str | None:
        requested = str(media_root or "").strip()
        if not requested:
            return None

        roots = self.get_all_media_roots()
        try:
            requested_path = Path(requested).expanduser().resolve()
            requested_resolved = str(requested_path)
        except (OSError, ValueError):
            requested_path = None
            requested_resolved = requested

        if not roots:
            return requested_resolved if requested_path and requested_path.exists() and requested_path.is_dir() else requested

        if requested in roots or requested_resolved in roots:
            return requested if requested in roots else requested_resolved

        requested_norm = os.path.normcase(os.path.normpath(requested_resolved))
        for root in roots:
            if os.path.normcase(os.path.normpath(root)) == requested_norm:
                return root

        if requested_path is not None:
            for root in roots:
                try:
                    if Path(root).samefile(requested_path):
                        return root
                except (OSError, ValueError):
                    continue

        return None

    def load_persisted_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                for key, val in data.items():
                    if key in _INTERNAL_SCRAPER_POLICY_KEYS or key in _ENV_ONLY_KEYS:
                        continue
                    if hasattr(self, key):
                        if key in ("auth_user", "auth_password_hash") and val:
                            setattr(self, key, val)
                        elif key not in ("auth_user", "auth_pass"):
                            setattr(self, key, val)
        except Exception:
            logger.exception("Failed to load persisted config")

    def save_config(self):
        try:
            Path(self.data_dir).mkdir(parents=True, exist_ok=True)
            data = {
                "javdb_enabled": self.javdb_enabled,
                "javdb_base_url": self.javdb_base_url,
                "tmdb_api_key": self.tmdb_api_key,
                "tmdb_access_token": self.tmdb_access_token,
                "scrape_concurrency_per_library": self.scrape_concurrency_per_library,
                "scrape_global_concurrency": self.scrape_global_concurrency,
                "scraper_api_concurrency": self.scraper_api_concurrency,
                "scraper_http_timeout": self.scraper_http_timeout,
                "update_check_enabled": self.update_check_enabled,
                "update_check_interval_hours": self.update_check_interval_hours,
                "auth_user": self.auth_user,
                "auth_password_hash": self.auth_password_hash,
            }
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            logger.exception("Failed to save config")
        env_file = ".env"
        env_file_encoding = "utf-8"


_SAFE_IMAGE_HOSTS = {
    "image.tmdb.org",
    "www.themoviedb.org",
    "javdatabase.com",
    "www.javdatabase.com",
    "lain.bgm.tv",
    "bangumi.tv",
    "bgm.tv",
    "img.bgm.tv",
}
MAX_REMOTE_IMAGE_BYTES = 8 * 1024 * 1024


def is_safe_image_url(url: str) -> bool:
    if not url:
        return False
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not parsed.scheme:
            return True
        if parsed.scheme not in ("http", "https"):
            return False
        if host in _SAFE_IMAGE_HOSTS:
            return True
        for safe_host in _SAFE_IMAGE_HOSTS:
            if host == safe_host or host.endswith("." + safe_host):
                return True
        logger.warning(f"Blocked image fetch for untrusted host: {host}")
        return False
    except Exception:
        return False


async def fetch_safe_image(url: str, *, headers: dict | None = None, timeout: float = 15.0, max_bytes: int = MAX_REMOTE_IMAGE_BYTES):
    from urllib.parse import urljoin

    if not is_safe_image_url(url):
        return None
    import httpx
    try:
        current_url = url
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for _ in range(5):
                async with client.stream("GET", current_url, headers=headers or {}) as resp:
                    if 300 <= resp.status_code < 400:
                        location = resp.headers.get("location") or ""
                        if not location:
                            return None
                        next_url = urljoin(str(resp.url), location)
                        if not is_safe_image_url(next_url):
                            return None
                        current_url = next_url
                        continue

                    if resp.status_code != 200:
                        return None
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    if not content_type.lower().startswith("image/"):
                        logger.warning(f"Blocked image fetch with non-image content-type: {content_type}")
                        return None
                    data = bytearray()
                    async for chunk in resp.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > max_bytes:
                            logger.warning(f"Blocked oversized image fetch: {current_url}")
                            return None
                    return bytes(data), content_type
            logger.warning(f"Blocked image fetch after too many redirects: {url}")
            return None
    except Exception as exc:
        logger.warning(f"Safe image fetch failed for {url}: {exc}")
        return None


settings = Settings()
settings.load_persisted_config()
logger.info("MediaTree config loaded")
