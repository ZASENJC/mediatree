import aiosqlite
import json
from pathlib import Path
from .config import settings

_db_pool = None


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
            scraper TEXT DEFAULT 'none',
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
    """)
    await db.commit()


async def upsert_movie(data: dict) -> int:
    db = await get_db()
    cur = await db.execute("SELECT id FROM movies WHERE path = ?", (data["path"],))
    existing = await cur.fetchone()
    if existing:
        await db.execute("""
            UPDATE movies SET code=?, title=?, actress=?, release_date=?,
            duration=?, cover_local=?, cover_remote=?, fanart_local=?,
            javdb_url=?, javdb_score=?, javdb_likes=?, javdb_thumbnails=?,
            folder_levels=?, local_metadata=?, media_root=?, updated_at=datetime('now')
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
            javdb_score, javdb_likes, javdb_thumbnails, folder_levels, local_metadata, media_root, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            data.get("created_at", None)
        ))
        movie_id = cur.lastrowid
    await db.commit()
    return movie_id


async def get_movies(folder: str = "", tag: str = "", code: str = "",
                     actress: str = "", media_root: str = "",
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

    sort_map = {
        "created_desc": "ORDER BY created_at DESC",
        "created_asc": "ORDER BY created_at ASC",
        "release_date_desc": "ORDER BY release_date DESC",
        "release_date_asc": "ORDER BY release_date ASC",
        "name": "ORDER BY folder_levels ASC",
        "random": "ORDER BY RANDOM()",
    }
    order = sort_map.get(sort, "ORDER BY created_at DESC")

    cols = "id, path, code, title, actress, duration, cover_local, cover_remote, javdb_score, javdb_likes, folder_levels, created_at, updated_at, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, episode_overview, episode_still, episode_still_local"
    query = f"SELECT {cols} FROM movies{where} {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cur = await db.execute(query, params)
    rows = await cur.fetchall()
    movies = [dict(r) for r in rows]

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

    return {"movies": movies, "total": total}


async def get_recent_watched(media_root: str = "", limit: int = 200, offset: int = 0):
    db = await get_db()
    where = " WHERE m.id IN (SELECT movie_id FROM tags WHERE tag = 'watched')"
    params = []
    if media_root:
        where += " AND m.media_root = ?"
        params.append(media_root)
    count_cur = await db.execute(f"SELECT COUNT(*) FROM movies m{where}", params)
    total = (await count_cur.fetchone())[0]
    cols = "m.id, m.path, m.code, m.title, m.actress, m.duration, m.cover_local, m.cover_remote, m.javdb_score, m.javdb_likes, m.folder_levels, m.created_at, m.updated_at, m.media_root, m.tmdb_type, m.tmdb_season, m.tmdb_episode, m.episode_title, m.episode_overview, m.episode_still, m.episode_still_local"
    query = f"SELECT {cols} FROM movies m{where} ORDER BY (SELECT MAX(t.created_at) FROM tags t WHERE t.movie_id = m.id AND t.tag = 'watched') DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cur = await db.execute(query, params)
    rows = await cur.fetchall()
    movies = [dict(r) for r in rows]
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
    return {"movies": movies, "total": total}


async def search_movies(q: str, media_root: str = "", limit: int = 100, offset: int = 0):
    db = await get_db()
    like = f"%{q}%"
    where = " WHERE (code LIKE ? OR title LIKE ? OR actress LIKE ?)"
    params = [like, like, like]
    if media_root:
        where += " AND media_root = ?"
        params.append(media_root)
    count_cur = await db.execute(f"SELECT COUNT(*) FROM movies{where}", params)
    total = (await count_cur.fetchone())[0]
    cols = "id, path, code, title, actress, duration, cover_local, cover_remote, javdb_score, javdb_likes, folder_levels, created_at, updated_at, media_root, tmdb_type, tmdb_season, tmdb_episode, episode_title, episode_overview, episode_still, episode_still_local"
    cur = await db.execute(
        f"SELECT {cols} FROM movies{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    )
    rows = await cur.fetchall()
    movies = [dict(r) for r in rows]
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
        f"SELECT folder_levels, MAX(cover_local) as cover_local, MAX(cover_remote) as cover_remote, MAX(created_at) as created_max, media_root, MAX(fanart_local) as fanart_local, COUNT(*) as movie_count FROM movies{where} GROUP BY folder_levels ORDER BY folder_levels",
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
                }
            node[part]["_total_count"] += r["movie_count"]
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
            "SELECT folder_levels, title FROM movies WHERE media_root=? AND title IS NOT NULL AND title != '' AND title != code AND tmdb_episode IS NULL ORDER BY folder_levels",
            (media_root,)
        )
    else:
        title_cur = await db.execute(
            "SELECT folder_levels, title FROM movies WHERE title IS NOT NULL AND title != '' AND title != code AND tmdb_episode IS NULL ORDER BY folder_levels"
        )
    title_map = {}
    for tr in await title_cur.fetchall():
        fl = tr["folder_levels"]
        if fl and fl not in title_map:
            title_map[fl] = tr["title"]
    for node in tree_result:
        node["display_title"] = title_map.get(node["path"])
        if not node.get("display_title"):
            parent = str(Path(node["path"]).parent) if node["path"] and str(Path(node["path"]).parent) != "." else None
            if parent and parent in title_map:
                node["display_title"] = title_map[parent]

    return tree_result


async def get_movie_detail(movie_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return None
    movie = dict(row)
    tc = await db.execute("SELECT tag FROM tags WHERE movie_id=?", (movie_id,))
    movie["tags"] = [t["tag"] for t in await tc.fetchall()]
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
        return dict(row) if row else None
    return None


async def get_all_library_settings() -> list[dict]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM library_settings")
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def save_library_settings(data: dict):
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO library_settings
           (media_root, scraper, tmdb_key, password_hash, enabled)
           VALUES (?,?,?,?,?)""",
        (data["media_root"], data.get("scraper", "none"),
         data.get("tmdb_key", ""),
         data.get("password_hash") or None, data.get("enabled", 1))
    )
    await db.commit()


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
