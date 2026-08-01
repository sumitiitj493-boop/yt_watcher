"""Sanity test for POST /api/open-downloads-folder.

Run from the repo root:
    python testing/test_open_downloads_folder.py
"""
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

tmp_dir = Path(tempfile.mkdtemp(prefix="yt_folder_"))
try:
    import services.files as files_mod

    files_mod.DOWNLOAD_DIR = tmp_dir

    from routes import library as library_routes

    app = FastAPI()
    app.include_router(library_routes.router, prefix="/api")
    client = TestClient(app)

    # The OS folder-open call is mocked; we just verify the endpoint wiring.
    with mock.patch.object(library_routes, "_open_downloads_folder", return_value=None) as opener:
        resp = client.post("/api/open-downloads-folder")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"message": "Opened"}, resp.text
        opener.assert_called_once()

    # If the OS call fails, we surface a 500 with a clear message.
    with mock.patch.object(
        library_routes, "_open_downloads_folder", side_effect=RuntimeError("boom")
    ):
        resp = client.post("/api/open-downloads-folder")
        assert resp.status_code == 500, resp.text
        assert "boom" in resp.json()["detail"], resp.text

    print("ALL OPEN-DOWNLOADS-FOLDER TESTS PASSED")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)
