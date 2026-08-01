"""API-level sanity test for the new multi-playlist endpoints.

Run from the repo root:
    python testing/test_multi_playlist_api.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Point the app at a throwaway downloads directory BEFORE importing the router.
tmp_dir = Path(tempfile.mkdtemp(prefix="yt_api_"))
try:
    import services.files as files_mod

    files_mod.DOWNLOAD_DIR = tmp_dir

    # Fake saved media files
    (tmp_dir / "Song One.mp3").write_bytes(b"0" * 2048)
    (tmp_dir / "Video Two.mp4").write_bytes(b"0" * 2048)
    (tmp_dir / "Clip Three.webm").write_bytes(b"0" * 2048)
    (tmp_dir / "ignore.tmp").write_bytes(b"0" * 2048)

    from routes import library as library_routes

    app = FastAPI()
    app.include_router(library_routes.router, prefix="/api")
    client = TestClient(app)

    # --- playlist CRUD ---
    resp = client.get("/api/playlists")
    assert resp.status_code == 200, resp.text
    playlists = resp.json()["playlists"]
    assert len(playlists) == 1 and playlists[0]["name"] == "My Playlist", playlists
    default_id = playlists[0]["id"]

    resp = client.post("/api/playlists", json={"name": "Workout"})
    assert resp.status_code == 200, resp.text
    workout = resp.json()["playlist"]
    workout_id = workout["id"]

    resp = client.post("/api/playlists", json={"name": "Workout"})
    assert resp.status_code == 409, resp.text

    resp = client.post("/api/playlists", json={"name": "   "})
    assert resp.status_code == 409, resp.text  # whitespace-only name rejected

    # --- add items ---
    resp = client.post(f"/api/playlists/{workout_id}/items", json={"filename": "Song One.mp3"})
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3"], resp.text

    # --- batch add (multiple files at once) ---
    resp = client.post(
        f"/api/playlists/{workout_id}/items/batch",
        json={"filenames": ["Video Two.mp4", "Clip Three.webm", "Video Two.mp4", "missing.mp4", "Song One.mp3"]},
    )
    assert resp.status_code == 200, resp.text
    # missing file skipped, duplicate skipped, already-present file skipped
    assert resp.json() == ["Song One.mp3", "Video Two.mp4", "Clip Three.webm"], resp.text

    resp = client.post(
        f"/api/playlists/{default_id}/items/batch",
        json={"filenames": ["Song One.mp3", "Video Two.mp4"]},
    )
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3", "Video Two.mp4"], resp.text

    resp = client.post("/api/playlists/99999/items/batch", json={"filenames": ["Song One.mp3"]})
    assert resp.status_code == 404, resp.text
    print("    batch endpoint OK")

    resp = client.post(f"/api/playlists/{workout_id}/items", json={"filename": "missing.mp3"})
    assert resp.status_code == 404, resp.text

    resp = client.post(f"/api/playlists/{default_id}/items", json={"filename": "Song One.mp3"})
    # already added via batch above -> ignored, list unchanged
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3", "Video Two.mp4"], resp.text

    # --- rename ---
    resp = client.patch(f"/api/playlists/{workout_id}", json={"name": "Gym Mix"})
    assert resp.status_code == 200 and resp.json()["playlist"]["name"] == "Gym Mix", resp.text

    resp = client.patch(f"/api/playlists/{workout_id}", json={"name": "My Playlist"})
    assert resp.status_code == 409, resp.text

    resp = client.patch("/api/playlists/99999", json={"name": "Nope"})
    assert resp.status_code == 404, resp.text

    # --- counts reflect items ---
    resp = client.get("/api/playlists")
    counts = {p["name"]: p["item_count"] for p in resp.json()["playlists"]}
    assert counts == {"My Playlist": 2, "Gym Mix": 3}, counts

    # --- reorder (scoped) ---
    client.post(f"/api/playlists/{workout_id}/items", json={"filename": "Clip Three.webm"})
    resp = client.post(f"/api/playlists/{workout_id}/reorder", json=["Clip Three.webm", "Song One.mp3"])
    assert resp.json() == ["Clip Three.webm", "Song One.mp3"], resp.text
    assert client.get(f"/api/playlists/{default_id}/items").json() == ["Song One.mp3", "Video Two.mp4"]

    # --- remove item ---
    resp = client.delete(f"/api/playlists/{workout_id}/items/Clip%20Three.webm")
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3"], resp.text

    # --- delete playlist ---
    resp = client.delete(f"/api/playlists/{workout_id}")
    assert resp.status_code == 200, resp.text
    resp = client.delete(f"/api/playlists/{workout_id}")
    assert resp.status_code == 404, resp.text
    assert client.get(f"/api/playlists/{workout_id}/items").status_code == 404

    # --- legacy endpoints still work on the default playlist ---
    resp = client.get("/api/playlist")
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3", "Video Two.mp4"], resp.text
    resp = client.post("/api/playlist/add/Video%20Two.mp4")
    # already present -> list unchanged
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3", "Video Two.mp4"], resp.text
    resp = client.delete("/api/playlist/remove/Video%20Two.mp4")
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3"], resp.text
    resp = client.post("/api/playlist/reorder", json=["Song One.mp3"])
    assert resp.status_code == 200 and resp.json() == ["Song One.mp3"], resp.text

    # --- after deleting every playlist, the legacy endpoints recreate a default ---
    client.delete(f"/api/playlists/{default_id}")
    assert client.get("/api/playlists").json()["playlists"] == []
    resp = client.get("/api/playlist")
    assert resp.status_code == 200 and resp.json() == [], resp.text
    names = [p["name"] for p in client.get("/api/playlists").json()["playlists"]]
    assert names == ["My Playlist"], names

    print("ALL API PLAYLIST TESTS PASSED")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)
