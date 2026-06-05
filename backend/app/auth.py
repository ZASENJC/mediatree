import hmac
import os

from .config import settings
from .database import _hash_password, _verify_password


def auth_secret() -> str:
    secret_material = settings.auth_password_hash or settings.auth_pass
    secret = f"{settings.auth_user}:{secret_material}"
    if secret == ":":
        return os.environ.get("MEDIATREE_MEDIA_TOKEN_SECRET", "") or "mediatree-uninitialized-token-secret"
    return secret


def verify_auth_credentials(username: str, password: str) -> bool:
    if not settings.auth_configured:
        return False
    if not hmac.compare_digest(username or "", settings.auth_user or ""):
        return False
    if settings.auth_password_hash:
        valid, upgraded = _verify_password(password or "", settings.auth_password_hash)
        if valid and upgraded:
            settings.auth_password_hash = upgraded
            settings.auth_pass = ""
            settings.save_config()
        return valid
    return hmac.compare_digest(password or "", settings.auth_pass or "")


def store_auth_credentials(username: str, password: str) -> None:
    settings.auth_user = username
    settings.auth_pass = ""
    settings.auth_password_hash = _hash_password(password)
    settings.save_config()


def valid_new_auth_credentials(username: str, password: str) -> tuple[bool, str]:
    if not (username or "").strip():
        return False, "username required"
    if len(password or "") < 8:
        return False, "password must be at least 8 characters"
    return True, ""
