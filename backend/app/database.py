import aiosqlite
import json
import sqlite3
from pathlib import Path
from .config import settings, logger
from .scraper_cache_policy import should_bypass_scraper_cache

_db_pool = None
WEB_USER_ID = "web"
WATCHED_THRESHOLD = 0.9
CONTINUE_WATCHING_MIN_SECONDS = 60
CONTENT_ROLE_MAIN = "main"
CONTENT_ROLE_SPECIAL = "special"
MAIN_CONTENT_WHERE = "COALESCE(content_role, 'main') != 'special'"
MAIN_CONTENT_WHERE_M = "COALESCE(m.content_role, 'main') != 'special'"

MOVIE_RESPONSE_COLUMNS = (
    "id, path, code, title, original_title, overview, actress, release_date, duration, "
    "cover_local, cover_remote, javdb_score, javdb_likes, folder_levels, created_at, updated_at, "
    "media_root, tmdb_id, tmdb_type, tmdb_season, tmdb_episode, episode_title, episode_overview, "
    "episode_still, episode_still_local, clean_title, episode_number, display_title, "
    "external_audio_tracks, genre, content_rating, \"cast\", crew, content_role, special_parent_levels"
)

MOVIE_RESPONSE_COLUMNS_M = (
    "m.id, m.path, m.code, m.title, m.original_title, m.overview, m.actress, m.release_date, m.duration, "
    "m.cover_local, m.cover_remote, m.javdb_score, m.javdb_likes, m.folder_levels, m.created_at, m.updated_at, "
    "m.media_root, m.tmdb_id, m.tmdb_type, m.tmdb_season, m.tmdb_episode, m.episode_title, m.episode_overview, "
    "m.episode_still, m.episode_still_local, m.clean_title, m.episode_number, m.display_title, "
    "m.external_audio_tracks, m.genre, m.content_rating, m.\"cast\", m.crew, m.content_role, m.special_parent_levels"
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _folder_descendant_like(folder_levels: str) -> str:
    return f"{_escape_like(folder_levels)}/%"


def _display_media_count_expr(prefix: str = "") -> str:
    col = lambda name: f"{prefix}.{name}" if prefix else name
    is_tv = (
        f"({col('tmdb_type')} = 'tv' "
        f"OR {col('tmdb_episode')} IS NOT NULL "
        f"OR {col('episode_number')} IS NOT NULL)"
    )
    identity = (
        "CASE "
        f"WHEN {col('tmdb_id')} IS NOT NULL THEN 'tmdb:' || CAST({col('tmdb_id')} AS TEXT) "
        f"WHEN COALESCE({col('source_id')}, '') != '' THEN 'source:' || COALESCE({col('scraper_source')}, '') || ':' || {col('source_id')} "
        f"WHEN COALESCE({col('bangumi_id')}, '') != '' THEN 'bangumi:' || {col('bangumi_id')} "
        f"ELSE 'folder:' || COALESCE({col('folder_levels')}, '') "
        "END"
    )
    season = f"COALESCE(CAST({col('tmdb_season')} AS TEXT), 'folder')"
    return (
        "COUNT(DISTINCT CASE "
        f"WHEN {is_tv} THEN 'tv|' || COALESCE({col('media_root')}, '') || '|' || {identity} || '|season:' || {season} "
        f"ELSE 'movie|' || CAST({col('id')} AS TEXT) "
        "END)"
    )


def _file_title_from_path(path: str | None) -> str:
    name = str(path or "").replace("\\", "/").rsplit("/", 1)[-1]
    return Path(name).stem or name


async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
        _db_pool = await aiosqlite.connect(settings.db_path)
        _db_pool.row_factory = aiosqlite.Row
        await _db_pool.execute("PRAGMA journal_mode=WAL")
        await _db_pool.execute("PRAGMA foreign_keys=ON")
        await _db_pool.execute("PRAGMA busy_timeout=5000")
    return _db_pool


async def close_db_pool():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None


async def get_db():
    return await get_db_pool()


def _is_expected_migration_error(exc: Exception) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).lower()
    return (
        "duplicate column name" in message
        or "no such table: movies" in message
        or "no such table: tags" in message
    )


async def init_db():
    db = await get_db()

    # Run migrations first on existing tables
    migrations = [
        "ALTER TABLE movies ADD COLUMN media_root TEXT DEFAULT ''",
        "ALTER TABLE movies ADD COLUMN created_at TEXT DEFAULT (datetime('now'))",
        "ALTER TABLE movies ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))",
        "ALTER TABLE movies ADD COLUMN local_metadata TEXT DEFAULT '{}'",
        "ALTER TABLE movies ADD COLUMN tmdb_id INTEGER",
        "ALTER TABLE movies ADD COLUMN tmdb_type TEXT",
        "ALTER TABLE movies ADD COLUMN tmdb_season INTEGER",
        "ALTER TABLE movies ADD COLUMN tmdb_episode INTEGER",
        "ALTER TABLE movies ADD COLUMN episode_title TEXT",
        "ALTER TABLE movies ADD COLUMN episode_overview TEXT",
        "ALTER TABLE movies ADD COLUMN episode_still TEXT",
        "ALTER TABLE movies ADD COLUMN episode_still_local TEXT",
        "ALTER TABLE movies ADD COLUMN clean_title TEXT",
        "ALTER TABLE movies ADD COLUMN episode_number INTEGER",
        "ALTER TABLE movies ADD COLUMN display_title TEXT",
        "ALTER TABLE movies ADD COLUMN external_audio_tracks TEXT DEFAULT '[]'",
        "ALTER TABLE movies ADD COLUMN \"cast\" TEXT DEFAULT '[]'",
        "ALTER TABLE movies ADD COLUMN crew TEXT DEFAULT '[]'",
        "ALTER TABLE movies ADD COLUMN scraper_source TEXT",
        "ALTER TABLE movies ADD COLUMN source_id TEXT",
        "ALTER TABLE movies ADD COLUMN bangumi_id TEXT",
        "ALTER TABLE movies ADD COLUMN javdb_id TEXT",
        "ALTER TABLE movies ADD COLUMN original_title TEXT",
        "ALTER TABLE movies ADD COLUMN overview TEXT",
        "ALTER TABLE movies ADD COLUMN scraper_raw TEXT",
        "ALTER TABLE movies ADD COLUMN pending_review INTEGER DEFAULT 0",
        "ALTER TABLE movies ADD COLUMN review_candidates TEXT",
        "ALTER TABLE movies ADD COLUMN genre TEXT",
        "ALTER TABLE movies ADD COLUMN keywords TEXT",
        "ALTER TABLE movies ADD COLUMN studios TEXT",
        "ALTER TABLE movies ADD COLUMN tagline TEXT",
        "ALTER TABLE movies ADD COLUMN status TEXT",
        "ALTER TABLE movies ADD COLUMN content_rating TEXT",
        "ALTER TABLE movies ADD COLUMN content_role TEXT DEFAULT 'main'",
        "ALTER TABLE movies ADD COLUMN special_parent_levels TEXT",
    ]
    for mig in migrations:
        try:
            await db.execute(mig)
        except Exception as exc:
            if not _is_expected_migration_error(exc):
                logger.exception("Database migration failed: %s", mig)
                raise
    await db.commit()

    # Ensure tags table has created_at column
    try:
        await db.execute("ALTER TABLE tags ADD COLUMN created_at TEXT")
        await db.execute("UPDATE tags SET created_at = datetime('now') WHERE created_at IS NULL")
    except Exception as exc:
        if not _is_expected_migration_error(exc):
            logger.exception("Database migration failed: tags.created_at")
            raise
    await db.commit()

    await db.executescript("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            code TEXT NOT NULL,
            title TEXT,
            actress TEXT,
            release_date TEXT,
            duration INTEGER,
            cover_local TEXT,
            cover_remote TEXT,
            fanart_local TEXT,
            javdb_url TEXT,
            javdb_score REAL,
            javdb_likes INTEGER,
            javdb_thumbnails TEXT,
            folder_levels TEXT,
            local_metadata TEXT DEFAULT '{}',
            tmdb_id INTEGER,
            tmdb_type TEXT,
            tmdb_season INTEGER,
            tmdb_episode INTEGER,
            episode_title TEXT,
            episode_overview TEXT,
            episode_still TEXT,
            episode_still_local TEXT,
            clean_title TEXT,
            episode_number INTEGER,
            display_title TEXT,
            external_audio_tracks TEXT DEFAULT '[]',
            "cast" TEXT DEFAULT '[]',
            crew TEXT DEFAULT '[]',
            scraper_source TEXT,
            source_id TEXT,
            bangumi_id TEXT,
            javdb_id TEXT,
            original_title TEXT,
            overview TEXT,
            scraper_raw TEXT,
            pending_review INTEGER DEFAULT 0,
            review_candidates TEXT,
            genre TEXT,
            keywords TEXT,
            studios TEXT,
            tagline TEXT,
            status TEXT,
            content_rating TEXT,
            content_role TEXT DEFAULT 'main',
            special_parent_levels TEXT,
            media_root TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_movies_code ON movies(code);
        CREATE INDEX IF NOT EXISTS idx_movies_path ON movies(path);
        CREATE INDEX IF NOT EXISTS idx_movies_folder ON movies(folder_levels);
        CREATE INDEX IF NOT EXISTS idx_movies_media_root ON movies(media_root);
        CREATE INDEX IF NOT EXISTS idx_movies_content_role ON movies(content_role);
        CREATE INDEX IF NOT EXISTS idx_movies_special_parent ON movies(media_root, special_parent_levels);

        CREATE TABLE IF NOT EXISTS javdb_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            data TEXT NOT NULL,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_javdb_cache_code ON javdb_cache(code);

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            movie_ids TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            UNIQUE(movie_id, tag)
        );

        CREATE INDEX IF NOT EXISTS idx_tags_movie ON tags(movie_id);

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS library_passwords (
            media_root TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS library_settings (
            media_root TEXT PRIMARY KEY,
            scraper TEXT DEFAULT 'auto',
            tmdb_key TEXT DEFAULT '',
            password_hash TEXT,
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS folder_special_settings (
            media_root TEXT NOT NULL,
            folder_levels TEXT NOT NULL,
            show_specials INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (media_root, folder_levels)
        );

        CREATE TABLE IF NOT EXISTS scraper_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            query TEXT NOT NULL,
            data TEXT NOT NULL,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source, query)
        );

        CREATE INDEX IF NOT EXISTS idx_scraper_cache_query ON scraper_cache(source, query);

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

        CREATE INDEX IF NOT EXISTS idx_user_data_item ON user_data(item_id);
    """)
    await db.commit()


def _valid_scraper(scraper: str | None) -> str:
    value = (scraper or "auto").strip().lower()
    if value == "tmdb":
        return "tmdb_movie"
    return value if value in {"auto", "javdatabase", "tmdb_movie", "tmdb_tv", "bangumi", "none"} else "auto"


def _normalize_special_movie_data(data: dict) -> dict:
    if (data.get("content_role") or CONTENT_ROLE_MAIN) != CONTENT_ROLE_SPECIAL:
        return data
    normalized = dict(data)
    file_title = (
        _file_title_from_path(normalized.get("path"))
        or normalized.get("display_title")
        or normalized.get("clean_title")
        or normalized.get("title")
    )
    normalized.update({
        "code": file_title,
        "title": file_title,
        "original_title": None,
        "overview": None,
        "actress": None,
        "release_date": None,
        "cover_remote": None,
        "fanart_local": None,
        "backdrop_url": None,
        "javdb_url": None,
        "javdb_score": None,
        "javdb_likes": None,
        "javdb_thumbnails": None,
        "tmdb_id": None,
        "tmdb_type": None,
        "tmdb_season": None,
        "tmdb_episode": None,
        "episode_title": None,
        "episode_overview": None,
        "episode_still": None,
        "episode_still_local": None,
        "clean_title": file_title,
        "episode_number": None,
        "display_title": file_title,
        "cast": "[]",
        "crew": "[]",
        "scraper_source": None,
        "source_id": None,
        "bangumi_id": None,
        "javdb_id": None,
        "scraper_raw": None,
        "pending_review": 0,
        "review_candidates": None,
        "genre": None,
        "keywords": None,
        "studios": None,
        "tagline": None,
        "status": None,
        "content_rating": None,
    })
    return normalized


async def upsert_movie(data: dict) -> int:
    data = _normalize_special_movie_data(data)
    db = await get_db()
    cur = await db.execute("SELECT id FROM movies WHERE path = ?", (data["path"],))
    existing = await cur.fetchone()
    if existing:
        if (data.get("content_role") or CONTENT_ROLE_MAIN) == CONTENT_ROLE_SPECIAL:
            await db.execute("""
                UPDATE movies SET code=?, title=?, original_title=NULL, overview=NULL,
                actress=NULL, release_date=NULL, duration=COALESCE(?, duration),
                cover_local=COALESCE(?, cover_local), cover_remote=NULL, fanart_local=NULL,
                javdb_url=NULL, javdb_score=NULL, javdb_likes=NULL, javdb_thumbnails=NULL,
                folder_levels=?, local_metadata=?, media_root=?,
                tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
                episode_title=NULL, episode_overview=NULL, episode_still=NULL, episode_still_local=NULL,
                clean_title=?, episode_number=NULL, display_title=?,
                external_audio_tracks=COALESCE(?, external_audio_tracks),
                "cast"='[]', crew='[]', scraper_source=NULL, source_id=NULL,
                bangumi_id=NULL, javdb_id=NULL, scraper_raw=NULL,
                pending_review=0, review_candidates=NULL,
                genre=NULL, keywords=NULL, studios=NULL, tagline=NULL, status=NULL, content_rating=NULL,
                content_role=?, special_parent_levels=?,
                updated_at=datetime('now')
                WHERE path=?
            """, (
                data.get("code"), data.get("title"), data.get("duration"),
                data.get("cover_local"), data.get("folder_levels"), data.get("local_metadata", "{}"),
                data.get("media_root", ""), data.get("clean_title"), data.get("display_title"),
                data.get("external_audio_tracks"), CONTENT_ROLE_SPECIAL, data.get("special_parent_levels"),
                data["path"]
            ))
        else:
            await db.execute("""
                UPDATE movies SET code=?,
                title=COALESCE(NULLIF(title, ''), ?), actress=COALESCE(?, actress), release_date=COALESCE(?, release_date),
                duration=COALESCE(?, duration), cover_local=COALESCE(?, cover_local),
                cover_remote=COALESCE(?, cover_remote), fanart_local=COALESCE(?, fanart_local),
                javdb_url=COALESCE(?, javdb_url), javdb_score=COALESCE(?, javdb_score),
                javdb_likes=COALESCE(?, javdb_likes), javdb_thumbnails=COALESCE(?, javdb_thumbnails),
                folder_levels=?, local_metadata=?, media_root=?,
                tmdb_type=COALESCE(tmdb_type, ?), tmdb_season=COALESCE(tmdb_season, ?),
                tmdb_episode=COALESCE(tmdb_episode, ?), episode_title=COALESCE(?, episode_title),
                episode_still=COALESCE(?, episode_still), episode_still_local=COALESCE(?, episode_still_local),
                clean_title=COALESCE(?, clean_title), episode_number=COALESCE(?, episode_number),
                display_title=COALESCE(?, display_title), external_audio_tracks=COALESCE(?, external_audio_tracks),
                content_role=?, special_parent_levels=?,
                updated_at=datetime('now')
                WHERE path=?
            """, (
                data.get("code"), data.get("title"), data.get("actress"),
                data.get("release_date"), data.get("duration"),
                data.get("cover_local"), data.get("cover_remote"),
                data.get("fanart_local") or data.get("backdrop_url"),
                data.get("javdb_url"), data.get("javdb_score"),
                data.get("javdb_likes"), data.get("javdb_thumbnails"),
                data.get("folder_levels"), data.get("local_metadata", "{}"),
                data.get("media_root", ""),
                data.get("tmdb_type"), data.get("tmdb_season"), data.get("tmdb_episode"),
                data.get("episode_title"), data.get("episode_still"), data.get("episode_still_local"),
                data.get("clean_title"), data.get("episode_number"), data.get("display_title"),
                data.get("external_audio_tracks"),
                data.get("content_role") or CONTENT_ROLE_MAIN,
                data.get("special_parent_levels"),
                data["path"]
            ))
        if data.get("created_at"):
            await db.execute("UPDATE movies SET created_at=? WHERE path=?",
                             (data["created_at"], data["path"]))
        movie_id = existing["id"]
    else:
        cur = await db.execute("""
            INSERT INTO movies (path, code, title, actress, release_date,
            duration, cover_local, cover_remote, fanart_local, javdb_url,
            javdb_score, javdb_likes, javdb_thumbnails, folder_levels, local_metadata, media_root,
            tmdb_type, tmdb_season, tmdb_episode, episode_title, episode_still, episode_still_local,
            clean_title, episode_number, display_title, external_audio_tracks,
            content_role, special_parent_levels, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["path"], data.get("code"), data.get("title"),
            data.get("actress"), data.get("release_date"),
            data.get("duration"), data.get("cover_local"),
            data.get("cover_remote"),
            data.get("fanart_local") or data.get("backdrop_url"),
            data.get("javdb_url"), data.get("javdb_score"),
            data.get("javdb_likes"), data.get("javdb_thumbnails"),
            data.get("folder_levels"), data.get("local_metadata", "{}"),
            data.get("media_root", ""),
            data.get("tmdb_type"), data.get("tmdb_season"), data.get("tmdb_episode"),
            data.get("episode_title"), data.get("episode_still"), data.get("episode_still_local"),
            data.get("clean_title"), data.get("episode_number"), data.get("display_title"),
            data.get("external_audio_tracks", "[]"),
            data.get("content_role") or CONTENT_ROLE_MAIN,
            data.get("special_parent_levels"),
            data.get("created_at", None)
        ))
        movie_id = cur.lastrowid
    await db.commit()
    return movie_id


async def get_movies(folder: str = "", tag: str = "", code: str = "",
                     actress: str = "", staff: str = "", media_root: str = "",
                     category_id: int = 0, limit: int = 50, offset: int = 0,
                     sort: str = "created_desc"):
    db = await get_db()
    where = f" WHERE {MAIN_CONTENT_WHERE}"
    params = []
    if tag:
        where += " AND id IN (SELECT movie_id FROM tags WHERE tag = ?)"
        params.append(tag)
    if folder:
        where += " AND (folder_levels = ? OR folder_levels LIKE ? ESCAPE '\\')"
        params.append(folder)
        params.append(_folder_descendant_like(folder))
    if code:
        safe_code = code.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where += " AND code LIKE ? ESCAPE '\\'"
        params.append(f"%{safe_code}%")
    if actress:
        safe_actress = actress.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where += " AND actress LIKE ? ESCAPE '\\'"
        params.append(f"%{safe_actress}%")
    if staff:
        safe_staff = staff.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where += " AND (actress LIKE ? ESCAPE '\\' OR \"cast\" LIKE ? ESCAPE '\\' OR crew LIKE ? ESCAPE '\\')"
        params.extend([f"%{safe_staff}%", f"%{safe_staff}%", f"%{safe_staff}%"])
    if media_root:
        where += " AND media_root = ?"
        params.append(media_root)
    if category_id:
        cur = await db.execute("SELECT movie_ids FROM categories WHERE id=?", (category_id,))
        row = await cur.fetchone()
        if row:
            ids = json.loads(row["movie_ids"])
            if ids:
                placeholders = ",".join("?" * len(ids))
                where += f" AND id IN ({placeholders})"
                params.extend(ids)

    count_params = params.copy()
    count_query = f"SELECT COUNT(*) FROM movies{where}"
    cur2 = await db.execute(count_query, count_params)
    total = (await cur2.fetchone())[0]

    episode_order = (
        "CASE WHEN COALESCE(tmdb_episode, episode_number) IS NULL THEN 1 ELSE 0 END, "
        "COALESCE(tmdb_episode, episode_number) ASC"
    )
    sort_map = {
        "created_desc": "ORDER BY created_at DESC",
        "created_asc": "ORDER BY created_at ASC",
        "release_date_desc": "ORDER BY release_date DESC",
        "release_date_asc": "ORDER BY release_date ASC",
        "name": f"ORDER BY COALESCE(clean_title, title, code) ASC, {episode_order}, folder_levels ASC",
        "random": "ORDER BY RANDOM()",
    }
    order = sort_map.get(sort, "ORDER BY created_at DESC")
    if folder and sort == "created_desc":
        order = f"ORDER BY {episode_order}, created_at DESC"

    cols = MOVIE_RESPONSE_COLUMNS
    query = f"SELECT {cols} FROM movies{where} {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cur = await db.execute(query, params)
    rows = await cur.fetchall()
    movies = [dict(r) for r in rows]
    _decorate_local_episode_fields(movies)

    if movies:
        movie_ids = [m["id"] for m in movies]
        placeholders = ",".join("?" * len(movie_ids))
        tag_cur = await db.execute(
            f"SELECT movie_id, tag FROM tags WHERE movie_id IN ({placeholders})",
            movie_ids
        )
        tag_map: dict[int, list[str]] = {}
        for t in await tag_cur.fetchall():
            mid = t["movie_id"]
            if mid not in tag_map:
                tag_map[mid] = []
            tag_map[mid].append(t["tag"])
        for m in movies:
            m["tags"] = tag_map.get(m["id"], [])
        await _attach_progress(movies)

    return {"movies": movies, "total": total}


async def _attach_progress(movies: list[dict]):
    if not movies:
        return
    db = await get_db()
    ids = [str(m["id"]) for m in movies]
    placeholders = ",".join("?" * len(ids))
    cur = await db.execute(
        f"""SELECT item_id, playback_position_ticks, played
            FROM user_data
            WHERE user_id=? AND item_id IN ({placeholders})""",
        [WEB_USER_ID, *ids],
    )
    progress_map = {row["item_id"]: dict(row) for row in await cur.fetchall()}
    for m in movies:
        row = progress_map.get(str(m["id"]), {})
        pos_seconds = int(row.get("playback_position_ticks") or 0) / 10_000_000
        duration = float(m.get("duration") or 0)
        if duration and pos_seconds > duration and duration < 1000:
            duration *= 60
        percent = 0
        if duration > 0 and pos_seconds > 0:
            percent = max(0, min(100, int(round((pos_seconds / duration) * 100))))
        m["playback_position"] = pos_seconds
        m["progress_percent"] = percent
        if row.get("played") and "watched" not in (m.get("tags") or []):
            m.setdefault("tags", []).append("watched")


def _episode_label(episode: int | None) -> str:
    if episode is None:
        return ""
    try:
        value = int(episode)
    except (TypeError, ValueError):
        return ""
    return f"EP{value:02d}" if value < 100 else f"EP{value}"


def _decode_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _decorate_special_movie_fields(movies: list[dict]):
    for m in movies:
        if (m.get("content_role") or CONTENT_ROLE_MAIN) != CONTENT_ROLE_SPECIAL:
            continue
        file_title = (
            _file_title_from_path(m.get("path"))
            or m.get("display_title")
            or m.get("title")
            or m.get("clean_title")
            or m.get("code")
            or ""
        )
        m.update({
            "code": file_title,
            "title": file_title,
            "original_title": None,
            "overview": None,
            "actress": None,
            "release_date": None,
            "javdb_score": None,
            "javdb_likes": None,
            "tmdb_id": None,
            "tmdb_type": None,
            "tmdb_season": None,
            "tmdb_episode": None,
            "episode_title": None,
            "episode_overview": None,
            "episode_still": None,
            "episode_still_local": None,
            "clean_title": file_title,
            "episode_number": None,
            "display_title": file_title,
            "genre": None,
            "content_rating": None,
            "cast": [],
            "crew": [],
        })
        for key in (
            "scraper_source", "source_id", "bangumi_id", "javdb_id",
            "scraper_raw", "review_candidates", "keywords", "studios",
            "tagline", "status",
        ):
            if key in m:
                m[key] = None
        if "pending_review" in m:
            m["pending_review"] = 0


def _decorate_local_episode_fields(movies: list[dict]):
    for m in movies:
        m["external_audio_tracks"] = _decode_json_list(m.get("external_audio_tracks"))

        episode = m.get("tmdb_episode")
        if episode is None:
            episode = m.get("episode_number")
        label = _episode_label(episode)
        clean_title = (m.get("clean_title") or "").strip()
        if label:
            m["episode_label"] = label

        if not m.get("display_title"):
            base = clean_title or m.get("title") or m.get("code") or ""
            m["display_title"] = f"{base} - {label}" if base and label else base
        if clean_title and not m.get("title"):
            m["title"] = clean_title


def _duration_seconds_for_progress(movie: dict, position_seconds: float) -> float:
    duration = float(movie.get("duration") or 0)
    if duration and position_seconds > duration and duration < 1000:
        duration *= 60
    return duration


def _continue_progress_state(movie: dict) -> tuple[float, bool]:
    position = int(movie.get("_playback_position_ticks") or 0) / 10_000_000
    duration = _duration_seconds_for_progress(movie, position)
    completed_by_progress = bool(duration > 0 and position > 0 and (position / duration) >= WATCHED_THRESHOLD)
    completed = bool(movie.get("_played")) or bool(movie.get("_watched_tag")) or completed_by_progress
    return position, completed


def _continue_activity_date(movie: dict) -> str:
    return movie.get("_last_played_date") or movie.get("_watched_tag_created_at") or ""


def _episode_order_value(movie: dict) -> int | None:
    value = movie.get("tmdb_episode")
    if value is None:
        value = movie.get("episode_number")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _episode_sort_key(movie: dict):
    order = _episode_order_value(movie)
    return (order is None, order or 0, movie.get("path") or "", int(movie.get("id") or 0))


def _season_group_key(movie: dict) -> tuple | None:
    if not (movie.get("tmdb_type") == "tv" or _episode_order_value(movie) is not None):
        return None
    media_root = movie.get("media_root") or ""
    if movie.get("tmdb_id") is not None and movie.get("tmdb_season") is not None:
        return ("tmdb", media_root, str(movie.get("tmdb_id")), str(movie.get("tmdb_season")))
    folder = (movie.get("folder_levels") or "").strip("/")
    if folder:
        return ("folder", media_root, folder)
    path = movie.get("path")
    if path:
        return ("path", media_root, str(Path(path).parent))
    return None


def _add_continue_candidate(candidates: dict[int, dict], movie: dict, sort_date: str):
    movie_id = int(movie["id"])
    sort_key = sort_date or movie.get("updated_at") or movie.get("created_at") or ""
    existing = candidates.get(movie_id)
    if existing is None or sort_key > (existing.get("_continue_sort_date") or ""):
        movie["_continue_sort_date"] = sort_key
        candidates[movie_id] = movie


async def _fetch_continue_rows(db, cols: str, where: str, params: list) -> list[dict]:
    query = f"""SELECT {cols},
            COALESCE(ud.playback_position_ticks, 0) AS _playback_position_ticks,
            COALESCE(ud.played, 0) AS _played,
            ud.last_played_date AS _last_played_date,
            CASE WHEN watched_tags.movie_id IS NULL THEN 0 ELSE 1 END AS _watched_tag,
            watched_tags.created_at AS _watched_tag_created_at
        FROM movies m
        LEFT JOIN user_data ud
          ON ud.user_id=? AND ud.item_id=CAST(m.id AS TEXT)
        LEFT JOIN tags watched_tags
          ON watched_tags.movie_id=m.id AND watched_tags.tag='watched'
        {where}
        ORDER BY COALESCE(ud.last_played_date, watched_tags.created_at, m.updated_at) DESC"""
    cur = await db.execute(query, [WEB_USER_ID, *params])
    return [dict(row) for row in await cur.fetchall()]


async def get_recent_watched(media_root: str = "", limit: int = 200, offset: int = 0):
    db = await get_db()
    min_continue_ticks = CONTINUE_WATCHING_MIN_SECONDS * 10_000_000
    cols = MOVIE_RESPONSE_COLUMNS_M
    activity_where = f"WHERE {MAIN_CONTENT_WHERE_M} AND (ud.playback_position_ticks>? OR ud.played=1 OR watched_tags.movie_id IS NOT NULL)"
    activity_params: list = [min_continue_ticks]
    if media_root:
        activity_where += " AND m.media_root=?"
        activity_params.append(media_root)

    movie_map: dict[int, dict] = {}
    season_keys: set[tuple] = set()
    for movie in await _fetch_continue_rows(db, cols, activity_where, activity_params):
        _position, completed = _continue_progress_state(movie)
        movie["_continue_completed"] = completed
        movie_map[int(movie["id"])] = movie
        if completed:
            season_key = _season_group_key(movie)
            if season_key is not None:
                season_keys.add(season_key)

    for season_key in season_keys:
        key_type = season_key[0]
        if key_type == "tmdb":
            _kind, key_media_root, tmdb_id, tmdb_season = season_key
            siblings_where = f"WHERE {MAIN_CONTENT_WHERE_M} AND m.media_root=? AND m.tmdb_id=? AND m.tmdb_season=?"
            siblings_params = [key_media_root, tmdb_id, tmdb_season]
        elif key_type == "folder":
            _kind, key_media_root, folder = season_key
            siblings_where = f"WHERE {MAIN_CONTENT_WHERE_M} AND m.media_root=? AND m.folder_levels=?"
            siblings_params = [key_media_root, folder]
        elif key_type == "path":
            _kind, key_media_root, parent_path = season_key
            siblings_where = f"WHERE {MAIN_CONTENT_WHERE_M} AND m.media_root=? AND m.path LIKE ? ESCAPE '\\'"
            siblings_params = [key_media_root, _folder_descendant_like(parent_path)]
        else:
            continue
        for movie in await _fetch_continue_rows(db, cols, siblings_where, siblings_params):
            _position, completed = _continue_progress_state(movie)
            movie["_continue_completed"] = completed
            movie_map[int(movie["id"])] = movie

    candidates: dict[int, dict] = {}
    seasons: dict[tuple, list[dict]] = {}
    for movie in movie_map.values():
        completed = bool(movie.get("_continue_completed"))
        if movie.get("_last_played_date") and int(movie.get("_playback_position_ticks") or 0) > min_continue_ticks and not completed:
            _add_continue_candidate(candidates, movie, _continue_activity_date(movie))
        season_key = _season_group_key(movie)
        if season_key is not None:
            seasons.setdefault(season_key, []).append(movie)

    for season_movies in seasons.values():
        ordered = sorted(season_movies, key=_episode_sort_key)
        completed_indexes = [index for index, movie in enumerate(ordered) if movie.get("_continue_completed")]
        if not completed_indexes or len(completed_indexes) == len(ordered):
            continue
        latest_completed_index = max(completed_indexes)
        next_episode = next(
            (movie for index, movie in enumerate(ordered)
             if index > latest_completed_index and not movie.get("_continue_completed")),
            None,
        )
        if next_episode is None:
            next_episode = next((movie for movie in ordered if not movie.get("_continue_completed")), None)
        if next_episode is None:
            continue
        latest_completed_date = max(
            (_continue_activity_date(movie) for movie in ordered if movie.get("_continue_completed")),
            default="",
        )
        _add_continue_candidate(
            candidates,
            next_episode,
            max(_continue_activity_date(next_episode), latest_completed_date),
        )

    ordered_candidates = sorted(
        candidates.values(),
        key=lambda movie: (
            movie.get("_continue_sort_date") or "",
            movie.get("updated_at") or "",
            int(movie.get("id") or 0),
        ),
        reverse=True,
    )
    total = len(ordered_candidates)
    safe_limit = max(0, int(limit or 0))
    safe_offset = max(0, int(offset or 0))
    paged = ordered_candidates[safe_offset:safe_offset + safe_limit]
    movies = []
    for movie in paged:
        public_movie = dict(movie)
        for key in list(public_movie.keys()):
            if key.startswith("_"):
                public_movie.pop(key, None)
        movies.append(public_movie)

    _decorate_local_episode_fields(movies)
    if movies:
        movie_ids = [m["id"] for m in movies]
        placeholders = ",".join("?" * len(movie_ids))
        tag_cur = await db.execute(
            f"SELECT movie_id, tag FROM tags WHERE movie_id IN ({placeholders})",
            movie_ids
        )
        tag_map: dict[int, list[str]] = {}
        for t in await tag_cur.fetchall():
            mid = t["movie_id"]
            if mid not in tag_map:
                tag_map[mid] = []
            tag_map[mid].append(t["tag"])
        for m in movies:
            m["tags"] = tag_map.get(m["id"], [])
        await _attach_progress(movies)
    return {"movies": movies, "total": total}


async def search_movies(q: str, media_root: str = "", limit: int = 100, offset: int = 0, field: str = ""):
    db = await get_db()
    safe_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{safe_q}%"
    if field == "staff":
        where = f" WHERE {MAIN_CONTENT_WHERE} AND (actress LIKE ? ESCAPE '\\' OR \"cast\" LIKE ? ESCAPE '\\' OR crew LIKE ? ESCAPE '\\')"
        params = [like, like, like]
    else:
        where = f" WHERE {MAIN_CONTENT_WHERE} AND (code LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' OR clean_title LIKE ? ESCAPE '\\' OR display_title LIKE ? ESCAPE '\\' OR actress LIKE ? ESCAPE '\\')"
        params = [like, like, like, like, like]
    if media_root:
        where += " AND media_root = ?"
        params.append(media_root)
    count_cur = await db.execute(f"SELECT COUNT(*) FROM movies{where}", params)
    total = (await count_cur.fetchone())[0]
    cols = MOVIE_RESPONSE_COLUMNS
    cur = await db.execute(
        f"SELECT {cols} FROM movies{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    )
    rows = await cur.fetchall()
    movies = [dict(r) for r in rows]
    _decorate_local_episode_fields(movies)
    if movies:
        movie_ids = [m["id"] for m in movies]
        placeholders = ",".join("?" * len(movie_ids))
        tag_cur = await db.execute(
            f"SELECT movie_id, tag FROM tags WHERE movie_id IN ({placeholders})",
            movie_ids
        )
        tag_map: dict[int, list[str]] = {}
        for t in await tag_cur.fetchall():
            mid = t["movie_id"]
            if mid not in tag_map:
                tag_map[mid] = []
            tag_map[mid].append(t["tag"])
        for m in movies:
            m["tags"] = tag_map.get(m["id"], [])
        await _attach_progress(movies)
    return {"movies": movies, "total": total}


def _hash_password(password: str) -> str:
    import hashlib
    import os
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return 'pbkdf2:' + salt.hex() + ':' + key.hex()


def _verify_password(password: str, stored_hash: str) -> tuple[bool, str | None]:
    """
    Verify a password against a stored hash.
    Returns (valid, upgraded_hash).
    upgraded_hash is non-None when verification succeeded against a legacy
    (non-PBKDF2) hash — the caller should persist the upgraded hash.
    """
    import hashlib
    if not stored_hash:
        return (True, None)
    if stored_hash.startswith('pbkdf2:'):
        parts = stored_hash.split(':')
        if len(parts) == 3:
            try:
                salt = bytes.fromhex(parts[1])
                key = bytes.fromhex(parts[2])
                new_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
                return (new_key == key, None)
            except (ValueError, IndexError):
                return (False, None)
    # Legacy SHA-256 hash — verify and return an upgraded PBKDF2 hash
    legacy = hashlib.sha256(password.encode()).hexdigest()
    if legacy == stored_hash:
        return (True, _hash_password(password))
    return (False, None)


def _normalize_cover_path(cover: str) -> str:
    if cover.startswith("http://") or cover.startswith("https://"):
        return cover
    if cover.startswith("/media/"):
        return cover[7:]
    if "/" not in cover and "\\" not in cover:
        return f"/api/cached-cover/{cover}"
    return cover


async def get_folder_tree_from_db(media_root: str = "") -> list[dict]:
    import random
    db = await get_db()
    where = f" WHERE {MAIN_CONTENT_WHERE}"
    params = []
    if media_root:
        where += " AND media_root = ?"
        params.append(media_root)
    display_count_expr = _display_media_count_expr()
    cur = await db.execute(
        f"""SELECT folder_levels, MAX(cover_local) as cover_local, MAX(cover_remote) as cover_remote,
                   MAX(created_at) as created_max, MAX(release_date) as release_date_max, media_root, MAX(fanart_local) as fanart_local,
                   MAX(tmdb_id) as tmdb_id, MAX(tmdb_type) as tmdb_type,
                   {display_count_expr} as movie_count,
                   COUNT(*) as item_count,
                   SUM(CASE WHEN EXISTS (SELECT 1 FROM tags t WHERE t.movie_id=movies.id AND t.tag='watched')
                         OR EXISTS (SELECT 1 FROM user_data ud WHERE ud.item_id=CAST(movies.id AS TEXT) AND ud.played=1)
                       THEN 1 ELSE 0 END) as watched_count
            FROM movies{where} GROUP BY folder_levels ORDER BY folder_levels""",
        params
    )
    rows = await cur.fetchall()
    if not rows:
        return []

    tree: dict[str, dict] = {}
    for r in rows:
        fl = r["folder_levels"] or ""
        if not fl:
            continue
        parts = fl.split("/")
        node = tree
        current_path = ""
        for i, part in enumerate(parts):
            current_path = f"{current_path}/{part}" if current_path else part
            if part not in node:
                node[part] = {
                    "_total_count": 0,
                    "_item_count": 0,
                    "_leaf_count": 0,
                    "_children": {},
                    "_cover": None,
                    "_backdrop": None,
                    "_path": current_path,
                    "_media_root": r["media_root"] or "",
                    "_created_max": "",
                    "_release_date_max": "",
                    "_watched_count": 0,
                    "_tmdb_id": None,
                    "_tmdb_type": None,
                    "_special_count": 0,
                    "_show_specials": False,
                }
            node[part]["_total_count"] += r["movie_count"]
            node[part]["_item_count"] += r["item_count"]
            node[part]["_watched_count"] += r["watched_count"] or 0
            if r["created_max"] and (not node[part]["_created_max"] or r["created_max"] > node[part]["_created_max"]):
                node[part]["_created_max"] = r["created_max"]
            if r["release_date_max"] and (not node[part]["_release_date_max"] or r["release_date_max"] > node[part]["_release_date_max"]):
                node[part]["_release_date_max"] = r["release_date_max"]
            if i == len(parts) - 1:
                node[part]["_leaf_count"] += r["movie_count"]
                cover = r["cover_local"]
                if not cover:
                    cover = r["cover_remote"]
                if cover and not node[part]["_cover"]:
                    cover = _normalize_cover_path(cover)
                    node[part]["_cover"] = cover
                fanart = r["fanart_local"]
                if fanart and not node[part]["_backdrop"]:
                    if fanart.startswith("http://") or fanart.startswith("https://"):
                        node[part]["_backdrop"] = fanart
                    elif "/" not in fanart and "\\" not in fanart:
                        node[part]["_backdrop"] = f"/api/cached-cover/{fanart}"
                if r["tmdb_id"] and not node[part]["_tmdb_id"]:
                    node[part]["_tmdb_id"] = r["tmdb_id"]
                    node[part]["_tmdb_type"] = r["tmdb_type"]
            node = node[part]["_children"]

    def find_node_info(path: str) -> dict | None:
        node = tree
        info = None
        for part in [p for p in path.split("/") if p]:
            info = node.get(part)
            if info is None:
                return None
            node = info["_children"]
        return info

    special_where = (
        " WHERE COALESCE(content_role, 'main') = 'special' "
        "AND special_parent_levels IS NOT NULL AND special_parent_levels != ''"
    )
    special_params: list = []
    if media_root:
        special_where += " AND media_root = ?"
        special_params.append(media_root)
    special_cur = await db.execute(
        f"""SELECT media_root, special_parent_levels, COUNT(*) AS special_count
            FROM movies{special_where}
            GROUP BY media_root, special_parent_levels""",
        special_params,
    )
    for row in await special_cur.fetchall():
        parent = row["special_parent_levels"] or ""
        count = int(row["special_count"] or 0)
        parts = [p for p in parent.split("/") if p]
        for idx in range(1, len(parts) + 1):
            info = find_node_info("/".join(parts[:idx]))
            if info is not None:
                info["_special_count"] += count

    settings_where = ""
    settings_params: list = []
    if media_root:
        settings_where = " WHERE media_root = ?"
        settings_params.append(media_root)
    settings_cur = await db.execute(
        f"SELECT media_root, folder_levels, show_specials FROM folder_special_settings{settings_where}",
        settings_params,
    )
    for row in await settings_cur.fetchall():
        info = find_node_info(row["folder_levels"] or "")
        if info is not None:
            info["_show_specials"] = bool(row["show_specials"])

    def flatten(node_dict: dict[str, dict]) -> list[dict]:
        result = []
        for name, info in node_dict.items():
            children = flatten(info["_children"])
            node_data = {
                "name": name,
                "path": info["_path"],
                "children": children,
                "movie_count": info["_total_count"],
                "cover": info["_cover"],
                "random_cover": info["_cover"],
                "backdrop": info.get("_backdrop"),
                "is_leaf": len(children) == 0,
                "media_root": info["_media_root"],
                "created_max": info["_created_max"],
                "release_date_max": info["_release_date_max"],
                "watched_count": info["_watched_count"],
                "folder_watched": bool(info["_item_count"] and info["_watched_count"] >= info["_item_count"]),
                "progress_percent": round((info["_watched_count"] / info["_item_count"]) * 100) if info["_item_count"] else 0,
                "tmdb_id": info.get("_tmdb_id"),
                "tmdb_type": info.get("_tmdb_type"),
                "special_count": info.get("_special_count", 0),
                "show_specials": bool(info.get("_show_specials")),
            }
            if children:
                all_covers = [c.get("random_cover") or c.get("cover") for c in children if c.get("random_cover") or c.get("cover")]
                if all_covers and not node_data.get("cover"):
                    node_data["random_cover"] = random.choice(all_covers)
                for c in children:
                    if c.get("created_max") and (not node_data.get("created_max") or c["created_max"] > node_data["created_max"]):
                        node_data["created_max"] = c["created_max"]
                    if c.get("release_date_max") and (not node_data.get("release_date_max") or c["release_date_max"] > node_data["release_date_max"]):
                        node_data["release_date_max"] = c["release_date_max"]
                    if c.get("backdrop") and not node_data.get("backdrop"):
                        node_data["backdrop"] = c["backdrop"]
            result.append(node_data)
        return result

    tree_result = flatten(tree)

    # get display titles for each folder
    if media_root:
        title_cur = await db.execute(
            """SELECT folder_levels, title FROM movies
               WHERE media_root=? AND title IS NOT NULL AND title != '' AND title != code
                 AND COALESCE(content_role, 'main') != 'special'
                 AND (tmdb_episode IS NULL OR episode_title IS NULL OR title != episode_title)
               ORDER BY folder_levels""",
            (media_root,)
        )
    else:
        title_cur = await db.execute(
            """SELECT folder_levels, title FROM movies
               WHERE title IS NOT NULL AND title != '' AND title != code
                 AND COALESCE(content_role, 'main') != 'special'
                 AND (tmdb_episode IS NULL OR episode_title IS NULL OR title != episode_title)
               ORDER BY folder_levels"""
        )
    title_map = {}
    for tr in await title_cur.fetchall():
        fl = tr["folder_levels"]
        if fl and fl not in title_map:
            title_map[fl] = tr["title"]
    def assign_display_titles(nodes: list[dict]):
        for node in nodes:
            node["display_title"] = title_map.get(node["path"])
            if not node.get("display_title"):
                parent = str(Path(node["path"]).parent) if node["path"] and str(Path(node["path"]).parent) != "." else None
                if parent and parent in title_map:
                    node["display_title"] = title_map[parent]
                else:
                    # check child folders (e.g., folder has /S01 subdirectory with movies)
                    prefix = node["path"] + "/"
                    for k, v in title_map.items():
                        if k.startswith(prefix):
                            node["display_title"] = v
                            break
            # fallback: use source folder name when no scraped title found
            if not node.get("display_title"):
                node["display_title"] = node.get("name")
            if node.get("children"):
                assign_display_titles(node["children"])

    assign_display_titles(tree_result)

    return tree_result


async def _attach_tags_and_progress(movies: list[dict]):
    if not movies:
        return
    db = await get_db()
    movie_ids = [m["id"] for m in movies]
    placeholders = ",".join("?" * len(movie_ids))
    tag_cur = await db.execute(
        f"SELECT movie_id, tag FROM tags WHERE movie_id IN ({placeholders})",
        movie_ids
    )
    tag_map: dict[int, list[str]] = {}
    for t in await tag_cur.fetchall():
        mid = t["movie_id"]
        if mid not in tag_map:
            tag_map[mid] = []
        tag_map[mid].append(t["tag"])
    for m in movies:
        m["tags"] = tag_map.get(m["id"], [])
    await _attach_progress(movies)


async def set_folder_specials_visibility(folder_levels: str, media_root: str, show_specials: bool) -> dict:
    db = await get_db()
    await db.execute(
        """INSERT INTO folder_special_settings (media_root, folder_levels, show_specials, updated_at)
           VALUES (?,?,?,datetime('now'))
           ON CONFLICT(media_root, folder_levels) DO UPDATE SET
             show_specials=excluded.show_specials,
             updated_at=datetime('now')""",
        (media_root, folder_levels, 1 if show_specials else 0),
    )
    await db.commit()
    return {"ok": True, "show_specials": bool(show_specials)}


async def get_folder_specials(folder_levels: str, media_root: str, include_movies: bool = False) -> dict:
    db = await get_db()
    setting_cur = await db.execute(
        "SELECT show_specials FROM folder_special_settings WHERE media_root=? AND folder_levels=?",
        (media_root, folder_levels),
    )
    setting = await setting_cur.fetchone()
    show_specials = bool(setting["show_specials"]) if setting else False
    where = (
        "WHERE media_root=? AND COALESCE(content_role, 'main') = 'special' "
        "AND (special_parent_levels=? OR special_parent_levels LIKE ? ESCAPE '\\')"
    )
    params = [media_root, folder_levels, _folder_descendant_like(folder_levels)]
    count_cur = await db.execute(f"SELECT COUNT(*) FROM movies {where}", params)
    special_count = int((await count_cur.fetchone())[0] or 0)
    movies: list[dict] = []
    if (show_specials or include_movies) and special_count:
        cur = await db.execute(
            f"""SELECT {MOVIE_RESPONSE_COLUMNS} FROM movies {where}
                ORDER BY folder_levels ASC, COALESCE(clean_title, title, code) ASC, path ASC""",
            params,
        )
        movies = [dict(row) for row in await cur.fetchall()]
        _decorate_special_movie_fields(movies)
        _decorate_local_episode_fields(movies)
        await _attach_tags_and_progress(movies)
    return {
        "show_specials": show_specials,
        "special_count": special_count,
        "movies": movies,
    }


async def get_movie_detail(movie_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return None
    movie = dict(row)
    _decorate_special_movie_fields([movie])
    _decorate_local_episode_fields([movie])
    tc = await db.execute("SELECT tag FROM tags WHERE movie_id=?", (movie_id,))
    movie["tags"] = [t["tag"] for t in await tc.fetchall()]
    for key in ("cast", "crew"):
        raw = movie.get(key)
        if isinstance(raw, str):
            try:
                movie[key] = json.loads(raw) if raw else []
            except (json.JSONDecodeError, TypeError):
                movie[key] = [{"name": n.strip(), "source": "legacy"} for n in raw.split(",") if n.strip()]
        elif not raw:
            movie[key] = []
    await _attach_progress([movie])
    if movie.get("javdb_thumbnails"):
        try:
            movie["javdb_thumbnails"] = json.loads(movie["javdb_thumbnails"])
        except (json.JSONDecodeError, TypeError):
            movie["javdb_thumbnails"] = []
    if isinstance(movie.get("scraper_raw"), str) and movie["scraper_raw"]:
        try:
            movie["scraper_raw"] = json.loads(movie["scraper_raw"])
        except (json.JSONDecodeError, TypeError):
            pass
    code = movie.get("code", "")
    if code:
        cc = await db.execute("SELECT data FROM javdb_cache WHERE code=?", (code,))
        crow = await cc.fetchone()
        if crow:
            try:
                cached = json.loads(crow["data"])
                comments = cached.get("javdb_comments") or []
                if isinstance(comments, str):
                    comments = [comments]
                overview = cached.get("overview") or next((c for c in comments if c), "")
                for key in ("director", "series", "studio", "genre", "dvd_id",
                           "javdb_score", "javdb_likes", "javdb_comments",
                           "title", "original_title", "actress", "release_date", "duration",
                           "cover_remote"):
                    if cached.get(key) is not None and not movie.get(key):
                        movie[key] = cached[key]
                if overview and not movie.get("overview"):
                    movie["overview"] = overview
                if cached.get("javdb_thumbnails") and not movie.get("javdb_thumbnails"):
                    try:
                        movie["javdb_thumbnails"] = json.loads(cached["javdb_thumbnails"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                if cached.get("actress") and not movie.get("cast"):
                    movie["cast"] = [
                        {"name": n.strip(), "role": "", "source": "javdb"}
                        for n in str(cached["actress"]).replace("，", ",").replace("、", ",").split(",")
                        if n.strip()
                    ]
                if cached.get("director") and not any(c.get("job") == "Director" for c in movie.get("crew", [])):
                    movie.setdefault("crew", []).append({"name": cached["director"], "job": "Director", "source": "javdb"})
                if cached.get("studio") and not any(c.get("job") == "Studio" for c in movie.get("crew", [])):
                    movie.setdefault("crew", []).append({"name": cached["studio"], "job": "Studio", "source": "javdb"})
            except (json.JSONDecodeError, TypeError):
                pass
    return movie


async def get_categories():
    db = await get_db()
    cur = await db.execute("SELECT * FROM categories ORDER BY created_at DESC")
    rows = await cur.fetchall()
    cats = []
    for r in rows:
        c = dict(r)
        try:
            c["movie_ids"] = json.loads(c["movie_ids"])
        except (json.JSONDecodeError, TypeError):
            c["movie_ids"] = []
        cats.append(c)
    return cats


async def save_category(data: dict):
    db = await get_db()
    movie_ids = json.dumps(data.get("movie_ids", []))
    if data.get("id"):
        await db.execute("UPDATE categories SET name=?, movie_ids=? WHERE id=?",
                         (data["name"], movie_ids, data["id"]))
    else:
        cur = await db.execute("INSERT INTO categories (name, movie_ids) VALUES (?,?)",
                       (data["name"], movie_ids))
        data["id"] = cur.lastrowid
    await db.commit()
    return data


async def delete_category(cat_id: int):
    db = await get_db()
    await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    await db.commit()


async def add_tag(movie_id: int, tag: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO tags (movie_id, tag, created_at) VALUES (?,?,datetime('now'))",
        (movie_id, tag)
    )
    await db.commit()


async def remove_tag(movie_id: int, tag: str):
    db = await get_db()
    await db.execute("DELETE FROM tags WHERE movie_id=? AND tag=?", (movie_id, tag))
    await db.commit()


async def set_folder_tag(folder_levels: str, tag: str, add: bool, media_root: str = ""):
    """Add or remove tag for all movies in a folder (including subfolders)."""
    db = await get_db()
    if media_root:
        if add:
            await db.execute(
                "INSERT OR IGNORE INTO tags (movie_id, tag, created_at) "
                "SELECT id, ?, datetime('now') FROM movies "
                "WHERE (folder_levels = ? OR folder_levels LIKE ? ESCAPE '\\') AND media_root = ? "
                "AND COALESCE(content_role, 'main') != 'special'",
                (tag, folder_levels, _folder_descendant_like(folder_levels), media_root)
            )
        else:
            await db.execute(
                "DELETE FROM tags WHERE tag = ? AND movie_id IN ("
                "SELECT id FROM movies WHERE (folder_levels = ? OR folder_levels LIKE ? ESCAPE '\\') AND media_root = ? "
                "AND COALESCE(content_role, 'main') != 'special'"
                ")",
                (tag, folder_levels, _folder_descendant_like(folder_levels), media_root)
            )
    else:
        if add:
            await db.execute(
                "INSERT OR IGNORE INTO tags (movie_id, tag, created_at) "
                "SELECT id, ?, datetime('now') FROM movies "
                "WHERE (folder_levels = ? OR folder_levels LIKE ? ESCAPE '\\') "
                "AND COALESCE(content_role, 'main') != 'special'",
                (tag, folder_levels, _folder_descendant_like(folder_levels))
            )
        else:
            await db.execute(
                "DELETE FROM tags WHERE tag = ? AND movie_id IN ("
                "SELECT id FROM movies WHERE (folder_levels = ? OR folder_levels LIKE ? ESCAPE '\\') "
                "AND COALESCE(content_role, 'main') != 'special'"
                ")",
                (tag, folder_levels, _folder_descendant_like(folder_levels))
            )
    await db.commit()


async def delete_movie(movie_id: int):
    db = await get_db()
    await db.execute("DELETE FROM movies WHERE id=?", (movie_id,))
    await db.commit()


async def get_media_roots() -> list[dict]:
    db = await get_db()
    display_count_expr = _display_media_count_expr()
    cur = await db.execute(
        f"SELECT media_root, {display_count_expr} as cnt FROM movies "
        f"WHERE media_root != '' AND {MAIN_CONTENT_WHERE} "
        "GROUP BY media_root"
    )
    rows = await cur.fetchall()
    results = []
    for r in rows:
        results.append({
            "path": r["media_root"],
            "label": Path(r["media_root"]).name or r["media_root"],
            "movie_count": r["cnt"],
        })
    return results


async def get_library_passwords() -> list[dict]:
    db = await get_db()
    cur = await db.execute("SELECT media_root FROM library_passwords")
    rows = await cur.fetchall()
    return [{"media_root": r["media_root"]} for r in rows]


async def set_library_password(media_root: str, password: str) -> bool:
    db = await get_db()
    if password:
        h = _hash_password(password)
        await db.execute(
            "INSERT OR REPLACE INTO library_passwords (media_root, password_hash) VALUES (?,?)",
            (media_root, h)
        )
    else:
        await db.execute("DELETE FROM library_passwords WHERE media_root=?", (media_root,))
    await db.commit()
    return True


async def verify_library_password(media_root: str, password: str) -> bool:
    db = await get_db()
    cur = await db.execute("SELECT password_hash FROM library_passwords WHERE media_root=?", (media_root,))
    row = await cur.fetchone()
    if not row:
        return True
    valid, upgraded = _verify_password(password, row["password_hash"])
    if valid and upgraded:
        await db.execute(
            "UPDATE library_passwords SET password_hash=? WHERE media_root=?",
            (upgraded, media_root)
        )
        await db.commit()
    return valid


async def get_library_settings(media_root: str = "") -> dict | None:
    db = await get_db()
    if media_root:
        cur = await db.execute("SELECT * FROM library_settings WHERE media_root=?", (media_root,))
        row = await cur.fetchone()
        if not row:
            return None
        data = dict(row)
        data["scraper"] = _valid_scraper(data.get("scraper"))
        return data
    return None


async def get_all_library_settings() -> list[dict]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM library_settings")
    rows = await cur.fetchall()
    result = []
    for r in rows:
        data = dict(r)
        data["scraper"] = _valid_scraper(data.get("scraper"))
        result.append(data)
    return result


async def save_library_settings(data: dict):
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO library_settings
           (media_root, scraper, tmdb_key, password_hash, enabled)
           VALUES (?,?,?,?,?)""",
        (data["media_root"], _valid_scraper(data.get("scraper")),
         data.get("tmdb_key", ""),
         data.get("password_hash") or None, data.get("enabled", 1))
    )
    await db.commit()


async def save_progress(movie_id: int, position: float, duration: float | None = None, stopped: bool = False) -> dict:
    db = await get_db()
    movie = await get_movie_detail(movie_id)
    if not movie:
        return {"ok": False, "error": "Movie not found"}
    if (movie.get("content_role") or CONTENT_ROLE_MAIN) == CONTENT_ROLE_SPECIAL:
        await db.execute(
            """UPDATE user_data
               SET playback_position_ticks=0,
                   play_count=0,
                   played=0,
                   last_played_date=NULL,
                   updated_at=datetime('now')
               WHERE user_id=? AND item_id=?""",
            (WEB_USER_ID, str(movie_id)),
        )
        await db.commit()
        return {
            "ok": True,
            "ignored": True,
            "played": False,
            "position": 0,
            "duration": float(duration or movie.get("duration") or 0),
            "progress_percent": 0,
        }
    total = float(duration or movie.get("duration") or 0)
    pos = max(0.0, float(position or 0))
    if total and pos > total and total < 1000:
        total *= 60
    played = bool(total > 0 and (pos / total) >= WATCHED_THRESHOLD)
    recent = bool(pos > CONTINUE_WATCHING_MIN_SECONDS or played)
    ticks = int(pos * 10_000_000)
    await db.execute(
        """INSERT INTO user_data (user_id, item_id, playback_position_ticks, play_count, is_favorite, played, last_played_date, updated_at)
           VALUES (?,?,?,?,?,?,CASE WHEN ? THEN datetime('now') ELSE NULL END,datetime('now'))
           ON CONFLICT(user_id,item_id) DO UPDATE SET
             playback_position_ticks=excluded.playback_position_ticks,
             play_count=CASE WHEN excluded.played=1 AND user_data.played=0 THEN user_data.play_count+1 ELSE user_data.play_count END,
             played=CASE WHEN excluded.played=1 THEN 1 ELSE user_data.played END,
             last_played_date=CASE WHEN ? THEN datetime('now') ELSE user_data.last_played_date END,
             updated_at=datetime('now')""",
        (
            WEB_USER_ID, str(movie_id), 0 if played else ticks, 1 if played else 0,
            0, 1 if played else 0, 1 if recent else 0, 1 if recent else 0,
        ),
    )
    if played:
        await db.execute(
            "INSERT OR IGNORE INTO tags (movie_id, tag, created_at) VALUES (?,?,datetime('now'))",
            (movie_id, "watched"),
        )
    await db.commit()
    if recent:
        from .config import logger
        logger.info(f"Recent playback updated for movie_id={movie_id} position={pos:.1f}s played={played}")
    return {"ok": True, "played": played, "position": pos, "duration": total, "progress_percent": 100 if played else (pos / total * 100 if total else 0)}


async def get_progress(movie_id: int) -> dict:
    db = await get_db()
    movie = await get_movie_detail(movie_id)
    if (movie or {}).get("content_role") == CONTENT_ROLE_SPECIAL:
        return {"position": 0, "played": False, "progress_percent": 0}
    cur = await db.execute(
        "SELECT playback_position_ticks, played FROM user_data WHERE user_id=? AND item_id=?",
        (WEB_USER_ID, str(movie_id)),
    )
    row = await cur.fetchone()
    if not row:
        return {"position": 0, "played": False, "progress_percent": 0}
    total = float(movie.get("duration") or 0) if movie else 0
    position = int(row["playback_position_ticks"] or 0) / 10_000_000
    if total and position > total and total < 1000:
        total *= 60
    percent = position / total * 100 if total else 0
    return {"position": position, "played": bool(row["played"]), "progress_percent": 100 if row["played"] else percent}


async def has_any_library_setting() -> bool:
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) as cnt FROM library_settings")
    row = await cur.fetchone()
    return row["cnt"] > 0


def _is_empty_scraper_cache_payload(data) -> bool:
    return data is None or data == {} or data == []


async def get_scraper_cache(source: str, query: str, max_hours: int):
    from datetime import datetime, timedelta
    if should_bypass_scraper_cache():
        return None
    db = await get_db()
    cur = await db.execute(
        "SELECT data, fetched_at FROM scraper_cache WHERE source=? AND query=?", (source, query)
    )
    row = await cur.fetchone()
    if not row:
        return None
    fetched = datetime.fromisoformat(row["fetched_at"])
    if datetime.now() - fetched > timedelta(hours=max_hours):
        return None
    try:
        data = json.loads(row["data"])
    except (json.JSONDecodeError, TypeError):
        return None
    if _is_empty_scraper_cache_payload(data):
        await db.execute("DELETE FROM scraper_cache WHERE source=? AND query=?", (source, query))
        await db.commit()
        return None
    return data


async def set_scraper_cache(source: str, query: str, data):
    db = await get_db()
    if _is_empty_scraper_cache_payload(data):
        await db.execute("DELETE FROM scraper_cache WHERE source=? AND query=?", (source, query))
        await db.commit()
        return
    await db.execute(
        "INSERT OR REPLACE INTO scraper_cache (source, query, data, fetched_at) VALUES (?,?,?,datetime('now'))",
        (source, query, json.dumps(data, ensure_ascii=False))
    )
    await db.commit()


async def verify_library_password_v2(media_root: str, password: str) -> bool:
    db = await get_db()
    pwd_hash = None
    source_table = None  # track which table provided the hash
    cur = await db.execute("SELECT password_hash FROM library_passwords WHERE media_root=?", (media_root,))
    row = await cur.fetchone()
    if row:
        pwd_hash = row["password_hash"]
        source_table = "library_passwords"
    if not pwd_hash:
        cur2 = await db.execute("SELECT password_hash FROM library_settings WHERE media_root=?", (media_root,))
        row2 = await cur2.fetchone()
        if row2 and row2["password_hash"]:
            pwd_hash = row2["password_hash"]
            source_table = "library_settings"
    if not pwd_hash:
        return True
    valid, upgraded = _verify_password(password, pwd_hash)
    if valid and upgraded and source_table:
        await db.execute(
            f"UPDATE {source_table} SET password_hash=? WHERE media_root=?",
            (upgraded, media_root)
        )
        await db.commit()
    return valid


async def get_review_queue(limit: int = 50, offset: int = 0):
    """Return movies with pending_review=1, with review_candidates JSON."""
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM movies WHERE pending_review=1"
    )
    total = (await cur.fetchone())[0]
    cols = (
        "id, path, code, title, original_title, overview, actress, duration, "
        "cover_local, cover_remote, javdb_score, javdb_likes, folder_levels, "
        "created_at, updated_at, media_root, tmdb_type, tmdb_season, tmdb_episode, "
        "episode_title, episode_overview, episode_still, episode_still_local, "
        "clean_title, episode_number, display_title, external_audio_tracks, "
        "\"cast\", crew, pending_review, review_candidates"
    )
    cur2 = await db.execute(
        f"SELECT {cols} FROM movies WHERE pending_review=1 "
        f"ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = await cur2.fetchall()
    movies = [dict(r) for r in rows]
    # Decode review_candidates JSON
    for m in movies:
        raw = m.get("review_candidates")
        if raw:
            try:
                m["review_candidates"] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
    return {"movies": movies, "total": total}


async def approve_review_item(movie_id: int):
    """Clear pending_review flag for a single movie."""
    db = await get_db()
    await db.execute(
        "UPDATE movies SET pending_review=0, review_candidates=NULL WHERE id=?",
        (movie_id,)
    )
    await db.commit()


async def clear_review_queue():
    """Clear all pending_review flags."""
    db = await get_db()
    await db.execute("UPDATE movies SET pending_review=0, review_candidates=NULL")
    await db.commit()
