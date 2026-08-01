"""Quick sanity tests for the multi-playlist feature (DB layer + migration).

Run from the repo root:
    python testing/test_multi_playlist.py
"""
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

# --------------------------------------------------------------------------
# 1. Build a LEGACY database (old single-playlist schema) so we can verify
#    the migration path that existing installs will hit.
# --------------------------------------------------------------------------
legacy_dir = Path(tempfile.mkdtemp(prefix="yt_legacy_"))
try:
    legacy_dir.mkdir(parents=True, exist_ok=True)
    db_path = legacy_dir / "yt_private_suite.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE download_jobs (
            task_id TEXT PRIMARY KEY, url TEXT NOT NULL,
            quality TEXT NOT NULL DEFAULT 'best', format TEXT NOT NULL DEFAULT 'mp4',
            status TEXT NOT NULL DEFAULT 'starting', title TEXT, filename TEXT, video_id TEXT,
            payload TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL,
            updated_at REAL NOT NULL, completed_at REAL
        );
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL,
            time_seconds INTEGER NOT NULL DEFAULT 0, content TEXT NOT NULL,
            tag TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            position INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE INDEX idx_playlist_items_position ON playlist_items(position);
        """
    )
    now = time.time()
    for index, name in enumerate(["Song One.mp3", "Video Two.mp4", "Clip Three.webm"]):
        conn.execute(
            "INSERT INTO playlist_items (filename, position, created_at) VALUES (?, ?, ?)",
            (name, index, now - index),
        )
    conn.commit()
    conn.close()

    # Point the app at this fake install directory, then import the DB module.
    import services.files as files_mod

    files_mod.DOWNLOAD_DIR = legacy_dir

    import services.database as db

    db.DOWNLOAD_DIR = legacy_dir  # module imported DOWNLOAD_DIR by value; sync it
    db.DB_PATH = legacy_dir / "yt_private_suite.db"

    db.ensure_db_initialized()

    playlists = db.list_playlists()
    assert len(playlists) == 1, f"expected 1 default playlist after migration, got {playlists}"
    default_id = playlists[0]["id"]
    assert playlists[0]["name"] == "My Playlist"
    assert playlists[0]["item_count"] == 3, playlists
    items = db.get_playlist_items(default_id)
    assert items == ["Song One.mp3", "Video Two.mp4", "Clip Three.webm"], items
    print("[PASS] legacy schema migrated into default playlist with 3 items")

    # ----------------------------------------------------------------------
    # 2. New multi-playlist behaviour.
    # ----------------------------------------------------------------------
    created = db.create_playlist("Workout")
    workout_id = created["id"]
    assert created["name"] == "Workout" and created["item_count"] == 0

    # Duplicate name is rejected
    try:
        db.create_playlist("Workout")
        raise AssertionError("duplicate playlist name should have raised")
    except ValueError:
        pass

    # Add items to each playlist independently
    db.add_playlist_item(workout_id, "Song One.mp3")
    db.add_playlist_item(workout_id, "Clip Three.webm")
    db.add_playlist_item(default_id, "Song One.mp3")  # same file, different playlist
    assert db.get_playlist_items(workout_id) == ["Song One.mp3", "Clip Three.webm"]
    assert db.get_playlist_items(default_id) == ["Song One.mp3", "Video Two.mp4", "Clip Three.webm"]
    print("[PASS] items are scoped per playlist; same file can live in two playlists")

    # Adding the same file twice to one playlist is a no-op
    db.add_playlist_item(workout_id, "Song One.mp3")
    assert db.get_playlist_items(workout_id) == ["Song One.mp3", "Clip Three.webm"]
    print("[PASS] duplicate item in the same playlist is ignored")

    # Reorder only touches the target playlist
    db.reorder_playlist(workout_id, ["Clip Three.webm", "Song One.mp3"])
    assert db.get_playlist_items(workout_id) == ["Clip Three.webm", "Song One.mp3"]
    assert db.get_playlist_items(default_id) == ["Song One.mp3", "Video Two.mp4", "Clip Three.webm"]
    print("[PASS] reorder is scoped to one playlist")

    # Rename
    renamed = db.rename_playlist(workout_id, "Gym Mix")
    assert renamed["name"] == "Gym Mix"
    try:
        db.rename_playlist(workout_id, "My Playlist")
        raise AssertionError("rename to duplicate name should have raised")
    except ValueError:
        pass
    print("[PASS] rename works and duplicate names are rejected")

    # Counts stay correct after mutations
    counts = {p["name"]: p["item_count"] for p in db.list_playlists()}
    assert counts == {"My Playlist": 3, "Gym Mix": 2}, counts
    print("[PASS] item counts are accurate")

    # Delete playlist cascades to its items
    assert db.delete_playlist(workout_id) is True
    assert db.get_playlist_items(workout_id) == []
    assert db.delete_playlist(99999) is False
    remaining = db.list_playlists()
    assert len(remaining) == 1 and remaining[0]["name"] == "My Playlist"
    print("[PASS] deleting a playlist removes only its own items")

    # Default playlist id picks the oldest remaining one
    assert db.get_default_playlist_id() == default_id
    print("[PASS] get_default_playlist_id returns oldest playlist")

    print("\nALL BACKEND PLAYLIST TESTS PASSED")
finally:
    shutil.rmtree(legacy_dir, ignore_errors=True)
