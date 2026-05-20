import aiosqlite
import json
from pathlib import Path
from .config import settings

_db_pool = None
WEB_USER_ID = "web"
WATCHED_THRESHOLD = 0.9


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
    ]
    for mig in migrations:
        try:
            await db.execute(mig)
        except Exception:
            pass
    await db.commit()

    # Ensure tags table has created_at column
    try:
        await db.execute("ALTER TABLE tags ADD COLUMN created_at TEXT")
        await db.execute("UPDATE tags SET created_at = datetime('now') WHERE created_at IS NULL")
    except Exception:
        pass
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
            media_root TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_movies_code ON movies(code);
        CREATE INDEX IF NOT EXISTS idx_movies_path ON movies(path);
        CREATE INDEX IF NOT EXISTS idx_movies_folder ON movies(folder_levels);
        CREATE INDEX IF NOT EXISTS idx_movies_media_root ON movies(media_root);

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


async def upsert_movie(data: dict) -> int:
    db = await get_db()
    cur = await db.execute("SELECT id FROM movies WHERE path = ?", (data["path"],))
    existing = await cur.fetchone()
    if existing:
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
            clean_title, episode_number, display_title, external_audio_tracks, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
    where = " WHERE 1=1"
    params = []
    if tag:
        where += " AND id IN (SELECT movie_id FROM tags WHERE tag = ?)"
        params.append(tag)
    if folder:
        where += " AND (folder_levels = ? OR folder_levels LIKE ?)"
        params.append(folder)
        params.append(f"{folder}/%")
    if code:
        where += " AND code LIKE ?"
        params.append(f"%{code}%")
    if actress:
        where += " AND (actress LIKE ? OR code IN (SELECT code FROM javdb_cache WHERE data LIKE ?))"
        params.append(f"%{actress}%")
        params.append(f"%{actress}%")
    if staff:
        where += " AND (actress LIKE ? OR \"cast\" LIKE ? OR crew LIKE ?)"
        params.extend([f"%{staff}%", f"%{staff}%", f"%{staff}%"])
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

    cols = "id, path, code, title, actress, duration, cover_local, cover_remote, javdb_score, javdb_likes, folder_levels, created_at, updated_at, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, episode_overview, episode_still, episode_still_local, clean_title, episode_number, display_title, external_audio_tracks, \"cast\", crew"
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


async def get_recent_watched(media_root: str = "", limit: int = 200, offset: int = 0):
    db = await get_db()
    min_recent_ticks = 180 * 10_000_000
    where = """ WHERE EXISTS (
        SELECT 1 FROM user_data ud
        WHERE ud.user_id=? AND ud.item_id=CAST(m.id AS TEXT)
          AND ud.last_played_date IS NOT NULL
          AND (ud.played=1 OR ud.playback_position_ticks>=?)
    )"""
    params = [WEB_USER_ID, min_recent_ticks]
    if media_root:
        where += " AND m.media_root = ?"
        params.append(media_root)
    count_cur = await db.execute(f"SELECT COUNT(*) FROM movies m{where}", params)
    total = (await count_cur.fetchone())[0]
    cols = "m.id, m.path, m.code, m.title, m.actress, m.duration, m.cover_local, m.cover_remote, m.javdb_score, m.javdb_likes, m.folder_levels, m.created_at, m.updated_at, m.media_root, m.tmdb_type, m.tmdb_season, m.tmdb_episode, m.episode_title, m.episode_overview, m.episode_still, m.episode_still_local, m.clean_title, m.episode_number, m.display_title, m.external_audio_tracks, m.\"cast\", m.crew"
    query = f"""SELECT {cols} FROM movies m{where}
        ORDER BY (
            SELECT ud.last_played_date FROM user_data ud
            WHERE ud.user_id=? AND ud.item_id=CAST(m.id AS TEXT)
        ) DESC
        LIMIT ? OFFSET ?"""
    params.extend([WEB_USER_ID])
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


async def search_movies(q: str, media_root: str = "", limit: int = 100, offset: int = 0, field: str = ""):
    db = await get_db()
    like = f"%{q}%"
    if field == "staff":
        where = " WHERE (actress LIKE ? OR \"cast\" LIKE ? OR crew LIKE ?)"
        params = [like, like, like]
    else:
        where = " WHERE (code LIKE ? OR title LIKE ? OR clean_title LIKE ? OR display_title LIKE ? OR actress LIKE ?)"
        params = [like, like, like, like, like]
    if media_root:
        where += " AND media_root = ?"
        params.append(media_root)
    count_cur = await db.execute(f"SELECT COUNT(*) FROM movies{where}", params)
    total = (await count_cur.fetchone())[0]
    cols = "id, path, code, title, actress, duration, cover_local, cover_remote, javdb_score, javdb_likes, folder_levels, created_at, updated_at, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, episode_overview, episode_still, episode_still_local, clean_title, episode_number, display_title, external_audio_tracks, \"cast\", crew"
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
    where = ""
    params = []
    if media_root:
        where = " WHERE media_root = ?"
        params.append(media_root)
    cur = await db.execute(
        f"""SELECT folder_levels, MAX(cover_local) as cover_local, MAX(cover_remote) as cover_remote,
                   MAX(created_at) as created_max, media_root, MAX(fanart_local) as fanart_local,
                   COUNT(*) as movie_count,
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
                    "_leaf_count": 0,
                    "_children": {},
                    "_cover": None,
                    "_backdrop": None,
                    "_path": current_path,
                    "_media_root": r["media_root"] or "",
                    "_created_max": "",
                    "_watched_count": 0,
                }
            node[part]["_total_count"] += r["movie_count"]
            node[part]["_watched_count"] += r["watched_count"] or 0
            if r["created_max"] and (not node[part]["_created_max"] or r["created_max"] > node[part]["_created_max"]):
                node[part]["_created_max"] = r["created_max"]
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
            node = node[part]["_children"]

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
                "watched_count": info["_watched_count"],
                "folder_watched": bool(info["_total_count"] and info["_watched_count"] >= info["_total_count"]),
                "progress_percent": round((info["_watched_count"] / info["_total_count"]) * 100) if info["_total_count"] else 0,
            }
            if children:
                all_covers = [c.get("random_cover") or c.get("cover") for c in children if c.get("random_cover") or c.get("cover")]
                if all_covers and not node_data.get("cover"):
                    node_data["random_cover"] = random.choice(all_covers)
                for c in children:
                    if c.get("created_max") and (not node_data.get("created_max") or c["created_max"] > node_data["created_max"]):
                        node_data["created_max"] = c["created_max"]
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
                 AND (tmdb_episode IS NULL OR episode_title IS NULL OR title != episode_title)
               ORDER BY folder_levels""",
            (media_root,)
        )
    else:
        title_cur = await db.execute(
            """SELECT folder_levels, title FROM movies
               WHERE title IS NOT NULL AND title != '' AND title != code
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
            if node.get("children"):
                assign_display_titles(node["children"])

    assign_display_titles(tree_result)

    return tree_result


async def get_movie_detail(movie_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return None
    movie = dict(row)
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
    code = movie.get("code", "")
    if code:
        cc = await db.execute("SELECT data FROM javdb_cache WHERE code=?", (code,))
        crow = await cc.fetchone()
        if crow:
            try:
                cached = json.loads(crow["data"])
                for key in ("director", "series", "studio", "genre", "dvd_id",
                           "javdb_score", "javdb_likes", "javdb_comments",
                           "title", "actress", "release_date", "duration",
                           "cover_remote"):
                    if cached.get(key) is not None and not movie.get(key):
                        movie[key] = cached[key]
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
        await db.execute("INSERT INTO categories (name, movie_ids) VALUES (?,?)",
                         (data["name"], movie_ids))
        data["id"] = db.total_changes
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


async def delete_movie(movie_id: int):
    db = await get_db()
    await db.execute("DELETE FROM movies WHERE id=?", (movie_id,))
    await db.commit()


async def get_media_roots() -> list[dict]:
    db = await get_db()
    cur = await db.execute(
        "SELECT media_root, COUNT(*) as cnt FROM movies WHERE media_root != '' GROUP BY media_root"
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
    import hashlib
    db = await get_db()
    if password:
        h = hashlib.sha256(password.encode()).hexdigest()
        await db.execute(
            "INSERT OR REPLACE INTO library_passwords (media_root, password_hash) VALUES (?,?)",
            (media_root, h)
        )
    else:
        await db.execute("DELETE FROM library_passwords WHERE media_root=?", (media_root,))
    await db.commit()
    return True


async def verify_library_password(media_root: str, password: str) -> bool:
    import hashlib
    db = await get_db()
    cur = await db.execute("SELECT password_hash FROM library_passwords WHERE media_root=?", (media_root,))
    row = await cur.fetchone()
    if not row:
        return True
    h = hashlib.sha256(password.encode()).hexdigest()
    return h == row["password_hash"]


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
    total = float(duration or movie.get("duration") or 0)
    pos = max(0.0, float(position or 0))
    if total and pos > total and total < 1000:
        total *= 60
    played = bool(total > 0 and (pos / total) >= WATCHED_THRESHOLD)
    recent = bool(pos >= 180 or played)
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
    cur = await db.execute(
        "SELECT playback_position_ticks, played FROM user_data WHERE user_id=? AND item_id=?",
        (WEB_USER_ID, str(movie_id)),
    )
    row = await cur.fetchone()
    if not row:
        return {"position": 0, "played": False, "progress_percent": 0}
    movie = await get_movie_detail(movie_id)
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


async def get_scraper_cache(source: str, query: str, max_hours: int) -> dict | None:
    from datetime import datetime, timedelta
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
        return json.loads(row["data"])
    except (json.JSONDecodeError, TypeError):
        return None


async def set_scraper_cache(source: str, query: str, data: dict):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO scraper_cache (source, query, data, fetched_at) VALUES (?,?,?,datetime('now'))",
        (source, query, json.dumps(data, ensure_ascii=False))
    )
    await db.commit()


async def verify_library_password_v2(media_root: str, password: str) -> bool:
    import hashlib
    db = await get_db()
    pwd_hash = None
    cur = await db.execute("SELECT password_hash FROM library_passwords WHERE media_root=?", (media_root,))
    row = await cur.fetchone()
    if row:
        pwd_hash = row["password_hash"]
    if not pwd_hash:
        cur2 = await db.execute("SELECT password_hash FROM library_settings WHERE media_root=?", (media_root,))
        row2 = await cur2.fetchone()
        if row2 and row2["password_hash"]:
            pwd_hash = row2["password_hash"]
    if not pwd_hash:
        return True
    h = hashlib.sha256(password.encode()).hexdigest()
    return h == pwd_hash
