"""End-to-end test for video -> audio extraction (uses real ffmpeg).

Run from the repo root:
    python testing/test_audio_extractor.py
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

if shutil.which("ffmpeg") is None:
    print("SKIP: ffmpeg not installed")
    sys.exit(0)

tmp_dir = Path(tempfile.mkdtemp(prefix="yt_audio_"))
try:
    import services.files as files_mod

    files_mod.DOWNLOAD_DIR = tmp_dir

    # Generate a tiny real video (12 seconds, with audio track) with ffmpeg.
    # Long enough that the extracted mp3 exceeds the library's 100KB filter.
    src = tmp_dir / "Sample Clip (dQw4w9WgXcQ).mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=12:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src),
        ],
        check=True,
        capture_output=True,
    )
    assert src.exists() and src.stat().st_size > 0

    from routes import library as library_routes

    app = FastAPI()
    app.include_router(library_routes.router, prefix="/api")
    client = TestClient(app)

    # --- 1. start extraction (mp3) ---
    resp = client.post("/api/extract-audio", json={"filename": src.name, "format": "mp3", "bitrate": "128k"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    job_id = data["job_id"]
    assert data["status"] == "queued", data
    assert data["source"] == src.name, data
    print("[PASS] extraction job started:", job_id)

    # --- 2. poll until done ---
    status = None
    for _ in range(120):
        resp = client.get(f"/api/extract-audio/{job_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()
        if status["status"] in ("completed", "error"):
            break
        time.sleep(0.25)

    assert status["status"] == "completed", status
    assert status["progress"] == 100, status
    assert status["filename"] and status["size_bytes"] > 0, status
    output_path = tmp_dir / status["filename"]
    assert output_path.exists(), status
    assert output_path.suffix.lower() == ".mp3", status
    print(f"[PASS] completed -> {status['filename']} ({status['size_bytes']} bytes)")

    # --- 3. output appears in /api/files (library listing) ---
    resp = client.get("/api/files")
    names = [f["filename"] for f in resp.json()["files"]]
    assert status["filename"] in names, names
    print("[PASS] extracted audio shows up in the library listing")

    # --- 4. unknown job -> 404 ---
    resp = client.get("/api/extract-audio/nope")
    assert resp.status_code == 404, resp.text
    print("[PASS] unknown job -> 404")

    # --- 5. missing file -> 404, invalid format -> 400 ---
    resp = client.post("/api/extract-audio", json={"filename": "missing.mp4", "format": "mp3"})
    assert resp.status_code == 404, resp.text
    resp = client.post("/api/extract-audio", json={"filename": src.name, "format": "wma"})
    assert resp.status_code == 400, resp.text
    resp = client.post("/api/extract-audio", json={"filename": src.name, "format": "mp3", "bitrate": "999k"})
    assert resp.status_code == 400, resp.text
    print("[PASS] validation: missing->404, bad format->400, bad bitrate->400")

    # --- 6. lossless format (flac) ignores bitrate ---
    resp = client.post("/api/extract-audio", json={"filename": src.name, "format": "flac", "bitrate": "128k"})
    assert resp.status_code == 200, resp.text
    job_id2 = resp.json()["job_id"]
    for _ in range(120):
        status = client.get(f"/api/extract-audio/{job_id2}").json()
        if status["status"] in ("completed", "error"):
            break
        time.sleep(0.25)
    assert status["status"] == "completed", status
    assert status["filename"].endswith(".flac"), status
    print(f"[PASS] flac extraction -> {status['filename']}")

    print("\nALL AUDIO EXTRACTOR TESTS PASSED")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)
