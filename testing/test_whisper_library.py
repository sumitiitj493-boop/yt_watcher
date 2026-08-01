"""Sanity test for POST /api/whisper-library (transcribe a saved file).

Run from the repo root:
    python testing/test_whisper_library.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

tmp_dir = Path(tempfile.mkdtemp(prefix="yt_whisper_lib_"))
try:
    import services.files as files_mod

    files_mod.DOWNLOAD_DIR = tmp_dir

    # Fake media file (tiny, won't actually be transcribed — we only check the endpoint wiring)
    (tmp_dir / "My Lecture (dQw4w9WgXcQ).mp4").write_bytes(b"\x00" * 4096)

    from routes import download as download_routes

    app = FastAPI()
    app.include_router(download_routes.router, prefix="/api")
    client = TestClient(app)

    # 1. Valid file -> starts a queued job (or cached result if available)
    resp = client.post("/api/whisper-library", json={
        "filename": "My Lecture (dQw4w9WgXcQ).mp4",
        "force": False,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("filename") == "My Lecture (dQw4w9WgXcQ).mp4", data
    assert data.get("size_bytes") == 4096, data
    assert data.get("job_id") or data.get("already_done"), data
    print("[PASS] valid library file accepted:", data.get("job_id") and "queued job" or "cached result")

    # 2. Missing file -> 404
    resp = client.post("/api/whisper-library", json={"filename": "nope.mp3", "force": False})
    assert resp.status_code == 404, resp.text
    print("[PASS] missing file -> 404")

    # 3. Invalid filename (path traversal) -> 400
    resp = client.post("/api/whisper-library", json={"filename": "../etc/passwd", "force": False})
    assert resp.status_code == 400, resp.text
    print("[PASS] traversal filename -> 400")

    # 4. Unsupported extension -> 400
    (tmp_dir / "data.json").write_text("{}")
    resp = client.post("/api/whisper-library", json={"filename": "data.json", "force": False})
    assert resp.status_code == 400, resp.text
    print("[PASS] unsupported extension -> 400")

    # 5. Missing body field -> 422
    resp = client.post("/api/whisper-library", json={"force": False})
    assert resp.status_code == 422, resp.text
    print("[PASS] missing filename -> 422")

    print("\nALL WHISPER LIBRARY TESTS PASSED")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)
