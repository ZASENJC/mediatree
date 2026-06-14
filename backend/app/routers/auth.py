import secrets
import time

from fastapi import APIRouter, HTTPException, Request

from ..auth import store_auth_credentials, valid_new_auth_credentials, verify_auth_credentials
from ..config import settings
from ..security import (
    MEDIA_TOKEN_TTL_SECONDS,
    create_auth_session_token,
    has_app_auth,
    sign_media_token,
)

router = APIRouter()


@router.post("/api/auth/login")
async def api_auth_login(data: dict):
    user = data.get("username", "")
    pwd = data.get("password", "")
    if not settings.auth_configured:
        raise HTTPException(status_code=409, detail="Authentication is not initialized")
    if verify_auth_credentials(user, pwd):
        return {"token": create_auth_session_token(), "ok": True}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/api/auth/setup")
async def api_auth_setup(data: dict):
    if settings.auth_configured:
        raise HTTPException(status_code=409, detail="Authentication is already initialized")
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    valid, reason = valid_new_auth_credentials(username, password)
    if not valid:
        raise HTTPException(status_code=400, detail=reason)
    store_auth_credentials(username, password)
    return {"token": create_auth_session_token(), "ok": True}


@router.get("/api/auth/status")
async def api_auth_status():
    return {"need_auth": True, "auth_configured": settings.auth_configured}


@router.post("/api/media-token")
async def api_media_token(request: Request):
    if not has_app_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    expiry = int(time.time()) + MEDIA_TOKEN_TTL_SECONDS
    nonce = secrets.token_urlsafe(18)
    return {"token": sign_media_token(expiry, nonce), "expires_at": expiry}
