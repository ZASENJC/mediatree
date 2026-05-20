import hashlib
import re
import uuid
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from .config import settings, logger
from .database import get_db

SERVER_ID = "mediatree-" + hashlib.md5(settings.data_dir.encode()).hexdigest()[:12]

TOKEN_EXPIRY_HOURS = 720


async def _ensure_jellyfin_tables():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS jellyfin_tokens (
            token TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            user_id TEXT NOT NULL,
            is_admin INTEGER DEFAULT 1,
            client TEXT DEFAULT '',
            device TEXT DEFAULT '',
            device_id TEXT DEFAULT '',
            version TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_jellyfin_tokens_user ON jellyfin_tokens(user_name);

        CREATE TABLE IF NOT EXISTS user_data (
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            playback_position_ticks INTEGER DEFAULT 0,
            play_count INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            played INTEGER DEFAULT 0,
            last_played_date TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, item_id)
        );

        CREATE TABLE IF NOT EXISTS playback_sessions (
            play_session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            client TEXT DEFAULT '',
            device TEXT DEFAULT '',
            device_id TEXT DEFAULT '',
            position_ticks INTEGER DEFAULT 0,
            is_paused INTEGER DEFAULT 0,
            started_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            stopped_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_user_data_item ON user_data(item_id);
        CREATE INDEX IF NOT EXISTS idx_playback_sessions_user ON playback_sessions(user_id);
    """)
    await db.commit()


def _get_user_id(username: str) -> str:
    return hashlib.sha256(username.encode()).hexdigest()[:16]


def _mask_token(token: str) -> str:
    if len(token) > 8:
        return token[:4] + "..." + token[-4:]
    return "***"


def parse_jellyfin_auth(request: Request) -> dict:
    result = {
        "token": None,
        "client": "",
        "device": "",
        "device_id": "",
        "version": "",
        "user_name": "",
        "user_id": "",
        "is_admin": False,
    }

    auth_header = request.headers.get("Authorization", "")
    if auth_header and auth_header.startswith("MediaBrowser "):
        result["token"] = _extract_from_mediabrowser(auth_header, "Token") or ""
        result["client"] = _extract_from_mediabrowser(auth_header, "Client") or ""
        result["device"] = _extract_from_mediabrowser(auth_header, "Device") or ""
        result["device_id"] = _extract_from_mediabrowser(auth_header, "DeviceId") or ""
        result["version"] = _extract_from_mediabrowser(auth_header, "Version") or ""
        if result["token"]:
            return result
    elif auth_header and auth_header.startswith("Bearer "):
        result["token"] = auth_header[7:].strip()
        if result["token"]:
            return result

    for header_name in ("X-Emby-Token", "X-MediaBrowser-Token"):
        val = request.headers.get(header_name, "")
        if val:
            result["token"] = val.strip()
            return result

    api_key = request.query_params.get("api_key") or ""
    if api_key:
        result["token"] = api_key.strip()
        return result

    query_token = request.query_params.get("token") or ""
    if query_token:
        result["token"] = query_token.strip()
        return result

    return result


def _extract_from_mediabrowser(header: str, key: str) -> str | None:
    pattern = rf'{key}\s*=\s*"([^"]*)"'
    match = re.search(pattern, header, re.I)
    if match:
        return match.group(1)
    return None


async def validate_jellyfin_token(token: str) -> dict | None:
    if not token:
        return None
    db = await get_db()
    cur = await db.execute(
        "SELECT token, user_name, user_id, is_admin, client, device, device_id, version FROM jellyfin_tokens WHERE token=?",
        (token,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    await db.execute(
        "UPDATE jellyfin_tokens SET last_seen_at=datetime('now') WHERE token=?",
        (token,),
    )
    await db.commit()
    return {
        "token": row["token"],
        "user_name": row["user_name"],
        "user_id": row["user_id"],
        "is_admin": bool(row["is_admin"]),
        "client": row["client"] or "",
        "device": row["device"] or "",
        "device_id": row["device_id"] or "",
        "version": row["version"] or "",
    }


async def get_jellyfin_user(request: Request) -> dict:
    parsed = parse_jellyfin_auth(request)
    token = parsed["token"]
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_info = await validate_jellyfin_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_info["client"] = user_info.get("client") or parsed.get("client") or ""
    user_info["device"] = user_info.get("device") or parsed.get("device") or ""
    user_info["device_id"] = user_info.get("device_id") or parsed.get("device_id") or ""
    user_info["version"] = user_info.get("version") or parsed.get("version") or ""
    return user_info


async def get_jellyfin_user_optional(request: Request) -> dict | None:
    try:
        return await get_jellyfin_user(request)
    except HTTPException:
        return None


async def create_jellyfin_token(
    username: str,
    client: str = "",
    device: str = "",
    device_id: str = "",
    version: str = "",
) -> str:
    token = hashlib.sha256(
        f"{username}:{uuid.uuid4()}:{datetime.now().isoformat()}".encode()
    ).hexdigest()
    user_id = _get_user_id(username)
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO jellyfin_tokens
           (token, user_name, user_id, is_admin, client, device, device_id, version)
           VALUES (?,?,?,1,?,?,?,?)""",
        (token, username, user_id, client, device, device_id, version),
    )
    await db.commit()
    return token


def get_user_id_from_username(username: str) -> str:
    return _get_user_id(username)


def get_server_id() -> str:
    return SERVER_ID
