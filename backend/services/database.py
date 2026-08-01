import json
import sqlite3
import time
from threading import RLock
from typing import Dict, List, Optional

import services.files as files_mod


_SCHEMA_LOCK = RLock()


def _connect() -> sqlite3.Connection:
    db_path = files_mod.DOWNLOAD_DIR / "yt_private_suite.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _migrate_legacy_playlist_schema(conn: sqlite3.Connection) -> None:
    """
    The very first release had a single unnamed playlist stored in a flat
    `playlist_items` table (filename UNIQUE, position, created_at). This
    migration renames that table, creates the new multi-playlist tables and
    moves the old items into a default playlist named "My Playlist".
    """
    columns = _table_columns(conn, "playlist_items")
    if not columns:
        return
    # New schema already applied (has playlist_id) -> nothing to do.
    if "playlist_id" in columns:
        return

    conn.execute("ALTER TABLE playlist_items RENAME TO playlist_items_legacy")
    conn.execute("DROP INDEX IF EXISTS idx_playlist_items_position")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            position INTEGER NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(playlist_id, filename)
        );

        CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist_position
            ON playlist_items(playlist_id, position);
        """
    )

    now = time.time()
    conn.execute(
        "INSERT OR IGNORE INTO playlists (name, created_at) VALUES ('My Playlist', ?)",
        (now,),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO playlist_items (playlist_id, filename, position, created_at)
        SELECT p.id, legacy.filename, legacy.position, legacy.created_at
        FROM playlist_items_legacy legacy
        JOIN playlists p ON p.name = 'My Playlist'
        """
    )
    conn.execute("DROP TABLE playlist_items_legacy")
    conn.commit()


def _ensure_default_playlist(conn: sqlite3.Connection) -> None:
    """
    Create the starter "My Playlist" once per install (first boot, or when a
    legacy install is migrated). After that the user is free to delete every
    playlist and have none.
    """
    meta = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'default_playlist_created'"
    ).fetchone()
    if meta is not None:
        return
    count = conn.execute("SELECT COUNT(*) AS c FROM playlists").fetchone()["c"]
    if count == 0:
        conn.execute(
            "INSERT INTO playlists (name, created_at) VALUES (?, ?)",
            ("My Playlist", time.time()),
        )
    conn.execute(
        "INSERT OR IGNORE INTO app_meta (key, value) VALUES ('default_playlist_created', '1')"
    )
    conn.commit()


def ensure_db_initialized() -> None:
    with _SCHEMA_LOCK:
        with _connect() as conn:
            _migrate_legacy_playlist_schema(conn)
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS download_jobs (
                    task_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    quality TEXT NOT NULL DEFAULT 'best',
                    format TEXT NOT NULL DEFAULT 'mp4',
                    status TEXT NOT NULL DEFAULT 'starting',
                    title TEXT,
                    filename TEXT,
                    video_id TEXT,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    completed_at REAL
                );

                CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs(status);
                CREATE INDEX IF NOT EXISTS idx_download_jobs_created_at ON download_jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_download_jobs_video_id ON download_jobs(video_id);

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    time_seconds INTEGER NOT NULL DEFAULT 0,
                    content TEXT NOT NULL,
                    tag TEXT NOT NULL DEFAULT '',
                    color TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_notes_filename_time ON notes(filename, time_seconds);

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS playlist_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(playlist_id, filename)
                );

                CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist_position
                    ON playlist_items(playlist_id, position);
                """
            )
            _ensure_default_playlist(conn)
            conn.commit()


def _job_payload_from_row(row: sqlite3.Row) -> dict:
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    payload.setdefault("url", row["url"])
    payload.setdefault("quality", row["quality"])
    payload.setdefault("format", row["format"])
    payload.setdefault("status", row["status"])
    payload.setdefault("title", row["title"] or "Unknown")
    payload.setdefault("filename", row["filename"])
    payload.setdefault("video_id", row["video_id"])
    payload.setdefault("created_at", row["created_at"])
    payload.setdefault("updated_at", row["updated_at"])
    if row["completed_at"] is not None:
        payload.setdefault("completed_at", row["completed_at"])
    return payload


def load_jobs_from_db() -> Dict[str, dict]:
    ensure_db_initialized()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM download_jobs ORDER BY created_at DESC").fetchall()
    return {row["task_id"]: _job_payload_from_row(row) for row in rows}


def save_jobs_to_db(jobs: Dict[str, dict]) -> None:
    ensure_db_initialized()
    now = time.time()
    with _connect() as conn:
        for task_id, data in jobs.items():
            created_at = float(data.get("created_at") or now)
            updated_at = float(data.get("updated_at") or now)
            status = str(data.get("status") or "starting")
            completed_at = data.get("completed_at")
            if completed_at is None and status == "completed":
                completed_at = updated_at
                data["completed_at"] = completed_at
            conn.execute(
                """
                INSERT INTO download_jobs (
                    task_id, url, quality, format, status, title, filename, video_id,
                    payload, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    url=excluded.url,
                    quality=excluded.quality,
                    format=excluded.format,
                    status=excluded.status,
                    title=excluded.title,
                    filename=excluded.filename,
                    video_id=excluded.video_id,
                    payload=excluded.payload,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at
                """,
                (
                    task_id,
                    str(data.get("url") or ""),
                    str(data.get("quality") or "best"),
                    str(data.get("format") or "mp4"),
                    status,
                    data.get("title"),
                    data.get("filename"),
                    data.get("video_id"),
                    json.dumps(data, ensure_ascii=False),
                    created_at,
                    updated_at,
                    completed_at,
                ),
            )
        conn.commit()


def delete_job_from_db(task_id: str) -> bool:
    ensure_db_initialized()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM download_jobs WHERE task_id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_jobs_from_db() -> None:
    ensure_db_initialized()
    with _connect() as conn:
        conn.execute("DELETE FROM download_jobs")
        conn.commit()


def list_notes(filename: str) -> List[dict]:
    ensure_db_initialized()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE filename = ? ORDER BY time_seconds ASC, created_at ASC",
            (filename,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_note(filename: str, time_seconds: int, content: str, tag: str = "", color: str = "") -> dict:
    ensure_db_initialized()
    now = time.time()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notes (filename, time_seconds, content, tag, color, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, max(0, int(time_seconds)), content.strip(), tag.strip(), color.strip(), now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def update_note(note_id: int, *, content: Optional[str] = None, time_seconds: Optional[int] = None,
                tag: Optional[str] = None, color: Optional[str] = None) -> Optional[dict]:
    ensure_db_initialized()
    with _connect() as conn:
        current = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not current:
            return None
        new_content = current["content"] if content is None else content.strip()
        new_time = current["time_seconds"] if time_seconds is None else max(0, int(time_seconds))
        new_tag = current["tag"] if tag is None else tag.strip()
        new_color = current["color"] if color is None else color.strip()
        conn.execute(
            """
            UPDATE notes
            SET content = ?, time_seconds = ?, tag = ?, color = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_content, new_time, new_tag, new_color, time.time(), note_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return dict(row)


def delete_note(note_id: int) -> bool:
    ensure_db_initialized()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return cursor.rowcount > 0


# --- Playlists (multiple, named) ------------------------------------------
def _playlist_row(conn: sqlite3.Connection, playlist_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT p.id, p.name, p.created_at,
               (SELECT COUNT(*) FROM playlist_items i WHERE i.playlist_id = p.id) AS item_count
        FROM playlists p
        WHERE p.id = ?
        """,
        (playlist_id,),
    ).fetchone()
    return dict(row) if row else None


def list_playlists() -> List[dict]:
    ensure_db_initialized()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.created_at,
                   (SELECT COUNT(*) FROM playlist_items i WHERE i.playlist_id = p.id) AS item_count
            FROM playlists p
            ORDER BY p.created_at ASC, p.id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_default_playlist_id() -> Optional[int]:
    """The default playlist is simply the oldest one (used by legacy endpoints)."""
    ensure_db_initialized()
    with _connect() as conn:
        row = conn.execute("SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT 1").fetchone()
    return row["id"] if row else None


def create_playlist(name: str) -> dict:
    ensure_db_initialized()
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Playlist name cannot be empty")
    with _connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO playlists (name, created_at) VALUES (?, ?)",
                (cleaned, time.time()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"A playlist named '{cleaned}' already exists")
        row = _playlist_row(conn, cursor.lastrowid)
    return row


def rename_playlist(playlist_id: int, name: str) -> Optional[dict]:
    ensure_db_initialized()
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Playlist name cannot be empty")
    with _connect() as conn:
        try:
            conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (cleaned, playlist_id))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"A playlist named '{cleaned}' already exists")
        row = _playlist_row(conn, playlist_id)
    return row


def delete_playlist(playlist_id: int) -> bool:
    ensure_db_initialized()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_playlist_items(playlist_id: int) -> List[str]:
    ensure_db_initialized()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT filename FROM playlist_items WHERE playlist_id = ? ORDER BY position ASC, id ASC",
            (playlist_id,),
        ).fetchall()
    return [row["filename"] for row in rows]


def add_playlist_item(playlist_id: int, filename: str) -> List[str]:
    ensure_db_initialized()
    now = time.time()
    with _connect() as conn:
        max_position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS pos FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()["pos"]
        conn.execute(
            "INSERT OR IGNORE INTO playlist_items (playlist_id, filename, position, created_at) VALUES (?, ?, ?, ?)",
            (playlist_id, filename, int(max_position) + 1, now),
        )
        conn.commit()
    return get_playlist_items(playlist_id)


def add_playlist_items(playlist_id: int, filenames: List[str]) -> List[str]:
    """Add many files to a playlist in one transaction (skips duplicates)."""
    ensure_db_initialized()
    now = time.time()
    with _connect() as conn:
        existing = {
            row["filename"]
            for row in conn.execute(
                "SELECT filename FROM playlist_items WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchall()
        }
        max_position = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS pos FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()["pos"]
        position = int(max_position) + 1
        seen = set()
        for filename in filenames or []:
            if not filename or filename in seen:
                continue
            seen.add(filename)
            if filename in existing:
                continue
            conn.execute(
                "INSERT INTO playlist_items (playlist_id, filename, position, created_at) VALUES (?, ?, ?, ?)",
                (playlist_id, filename, position, now),
            )
            existing.add(filename)
            position += 1
        conn.commit()
    return get_playlist_items(playlist_id)


def remove_playlist_item(playlist_id: int, filename: str) -> List[str]:
    ensure_db_initialized()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND filename = ?",
            (playlist_id, filename),
        )
        rows = conn.execute(
            "SELECT filename FROM playlist_items WHERE playlist_id = ? ORDER BY position ASC, id ASC",
            (playlist_id,),
        ).fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                "UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND filename = ?",
                (index, playlist_id, row["filename"]),
            )
        conn.commit()
    return get_playlist_items(playlist_id)


def reorder_playlist(playlist_id: int, filenames: List[str]) -> List[str]:
    ensure_db_initialized()
    unique: List[str] = []
    seen = set()
    for filename in filenames or []:
        if filename and filename not in seen:
            unique.append(filename)
            seen.add(filename)
    now = time.time()
    with _connect() as conn:
        conn.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
        for index, filename in enumerate(unique):
            conn.execute(
                "INSERT INTO playlist_items (playlist_id, filename, position, created_at) VALUES (?, ?, ?, ?)",
                (playlist_id, filename, index, now),
            )
        conn.commit()
    return get_playlist_items(playlist_id)


async def init_db():
    ensure_db_initialized()
