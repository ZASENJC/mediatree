import sqlite3

from ..config import logger


def _is_expected_migration_error(exc: Exception) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).lower()
    return (
        "duplicate column name" in message
        or "no such table: movies" in message
        or "no such table: tags" in message
        or "no such table: scraper_plugins" in message
    )


async def init_schema(get_db):
    db = await get_db()

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
        "ALTER TABLE scraper_plugins ADD COLUMN deleted INTEGER DEFAULT 0",
    ]
    for mig in migrations:
        try:
            await db.execute(mig)
        except Exception as exc:
            if not _is_expected_migration_error(exc):
                logger.exception("Database migration failed: %s", mig)
                raise
    await db.commit()

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

        CREATE TABLE IF NOT EXISTS scraper_plugins (
            name TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT DEFAULT '',
            supported_media_types TEXT DEFAULT '[]',
            entrypoint TEXT NOT NULL,
            class_name TEXT NOT NULL,
            installed_path TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            builtin INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            installed_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            error TEXT
        );

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
