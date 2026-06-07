from pydantic_settings import BaseSettings
from pathlib import Path
import base64
import json
import os
import logging
from logging.handlers import RotatingFileHandler

log_dir = None
log_file = None
_file_handler = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mediatree")


def setup_file_logging(data_dir: str):
    global log_dir, log_file, _file_handler
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mediatree.log"
    try:
        if _file_handler is not None:
            current = Path(getattr(_file_handler, "baseFilename", ""))
            if current == log_file:
                return
            close_file_logging()
        fh = RotatingFileHandler(str(log_file), maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(fh)
        _file_handler = fh
        logger.info("File logging initialized")
    except Exception as e:
        logger.warning(f"File logging setup failed: {e}")


def close_file_logging():
    global _file_handler
    if _file_handler is None:
        return
    try:
        logger.removeHandler(_file_handler)
        _file_handler.close()
    finally:
        _file_handler = None


class Settings(BaseSettings):
    media_root: str = "/media"
    data_dir: str = str(Path(__file__).parent.parent.parent / "data")

    javdb_enabled: bool = True
    javdb_base_url: str = "https://www.javdatabase.com"
    javdb_cache_hours: int = 24
    javdb_request_interval: float = 1.0
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

    def load_persisted_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                for key, val in data.items():
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
                "javdb_cache_hours": self.javdb_cache_hours,
                "javdb_request_interval": self.javdb_request_interval,
                "tmdb_cache_hours": self.tmdb_cache_hours,
                "bangumi_cache_hours": self.bangumi_cache_hours,
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
