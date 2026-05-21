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

    scan_on_startup: bool = True

    auth_user: str = ""
    auth_pass: str = ""

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
        return bool(self.auth_user)

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
                        if key == "auth_user" and val:
                            setattr(self, key, val)
                        elif key not in ("auth_user", "auth_pass"):
                            setattr(self, key, val)
        except Exception:
            pass

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
                "auth_user": self.auth_user,
            }
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
settings.load_persisted_config()
logger.info("MediaTree config loaded")
