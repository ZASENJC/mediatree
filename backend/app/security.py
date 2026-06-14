import base64
import hmac
import secrets
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import auth_secret, verify_auth_credentials
from .config import settings

PUBLIC_FRONTEND_FILES = frozenset({"login-logo.png", "site-logo.png"})
PUBLIC_FRONTEND_PATHS = frozenset(f"/{name}" for name in PUBLIC_FRONTEND_FILES)

MEDIA_TOKEN_TTL_SECONDS = 6 * 60 * 60
AUTH_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
MEDIA_ROUTE_PREFIXES = (
    "/api/stream/",
    "/api/cover/",
    "/api/episode-still/",
    "/api/thumbnail/",
    "/api/subtitle-tracks/",
    "/api/subtitle/",
    "/api/subtitle-content/",
    "/api/subtitle-file/",
    "/api/external-play/",
    "/api/media-info/",
    "/api/media/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/assets") \
                or path in PUBLIC_FRONTEND_PATHS \
                or path in ("/api/auth/login", "/api/auth/setup", "/api/auth/status", "/api/health", "/api/version") \
                or path.startswith("/api/cached-cover/") \
                or path.startswith("/fonts/") \
                or (path == "/api/subtitle-fonts" and request.method in ("GET", "HEAD")) \
                or (path.startswith("/api/subtitle-fonts/") and request.method in ("GET", "HEAD")):
            return await call_next(request)
        if _is_media_route(path):
            if has_media_access(request):
                return await call_next(request)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        if has_app_auth(request):
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})


def _is_media_route(path: str) -> bool:
    return path.startswith(MEDIA_ROUTE_PREFIXES)


def _auth_secret() -> str:
    return auth_secret()


def _sign_token(kind: str, expiry: int, nonce: str) -> str:
    payload = f"{kind}:{expiry}:{nonce}"
    signature = hmac.new(_auth_secret().encode(), payload.encode(), "sha256").hexdigest()
    return f"{payload}:{signature}"


def _verify_signed_token(token: str, kind: str) -> bool:
    parts = (token or "").split(":")
    if len(parts) != 4:
        return False
    token_kind, expiry_raw, nonce, signature = parts
    if not hmac.compare_digest(token_kind, kind):
        return False
    try:
        expiry = int(expiry_raw)
    except ValueError:
        return False
    if expiry < int(time.time()) or not nonce:
        return False
    expected = _sign_token(kind, expiry, nonce).rsplit(":", 1)[-1]
    return hmac.compare_digest(signature, expected)


def create_auth_session_token() -> str:
    expiry = int(time.time()) + AUTH_SESSION_TTL_SECONDS
    nonce = secrets.token_urlsafe(18)
    return _sign_token("auth", expiry, nonce)


def _verify_auth_session_token(token: str) -> bool:
    if not settings.auth_configured:
        return False
    return _verify_signed_token(token, "auth")


def sign_media_token(expiry: int, nonce: str) -> str:
    return _sign_token("media", expiry, nonce)


def _verify_media_token(token: str) -> bool:
    return _verify_signed_token(token, "media")


def has_app_auth(request: Request) -> bool:
    if not settings.auth_configured:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and _verify_auth_session_token(auth[7:]):
        return True
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            user, _, pwd = decoded.partition(":")
            return verify_auth_credentials(user, pwd)
        except Exception:
            return False
    return False


def require_media_access(request: Request) -> None:
    if has_media_access(request):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def has_media_access(request: Request) -> bool:
    if has_app_auth(request):
        return True
    token = request.query_params.get("token") or request.headers.get("X-MediaTree-Media-Token", "")
    if token and _verify_media_token(token):
        return True
    return False
