"""Sanity test for Instagram/social cookie support.

Run from the repo root:
    python testing/test_social_cookies.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

tmp_dir = Path(tempfile.mkdtemp(prefix="yt_social_"))
try:
    import services.files as files_mod

    files_mod.DOWNLOAD_DIR = tmp_dir

    from routes import download as download_routes
    from services import yt_dlp_options as opts

    # Point cookie file paths at the temp dir so we never touch the real one.
    tmp_cookies = tmp_dir / "instagram_cookies.txt"
    opts.DEFAULT_SOCIAL_COOKIES_FILE = tmp_cookies
    opts.BACKEND_DIR = tmp_dir

    app = FastAPI()
    app.include_router(download_routes.router, prefix="/api")
    client = TestClient(app)

    # --- 1. status when nothing configured ---
    resp = client.get("/api/social-cookies")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["exists"] is False, data
    assert data["browsers_configured"] == [], data
    print("[PASS] status endpoint: no cookies, no browsers configured")

    # --- 2. upload a valid Netscape cookies.txt ---
    NETSCAPE = (
        "# Netscape HTTP Cookie File\n"
        "instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tABC123\n"
        "instagram.com\tTRUE\t/\tTRUE\t0\tcsrftoken\tXYZ\n"
    )
    resp = client.post(
        "/api/social-cookies",
        files={"file": ("instagram_cookies.txt", NETSCAPE.encode(), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["exists"] is True, resp.text
    assert resp.json()["cookie_count"] == 2, resp.json()
    assert tmp_cookies.exists()
    print("[PASS] upload valid Netscape cookies.txt -> saved, 2 rows")

    # --- 3. upload JSON format -> rejected ---
    resp = client.post(
        "/api/social-cookies",
        files={"file": ("cookies.json", b'{"cookies":[]}', "application/json")},
    )
    assert resp.status_code == 400, resp.text
    print("[PASS] JSON cookie file rejected with clear message")

    # --- 4. upload garbage with no Netscape rows -> rejected ---
    resp = client.post(
        "/api/social-cookies",
        files={"file": ("cookies.txt", b"hello world no tabs here", "text/plain")},
    )
    assert resp.status_code == 400, resp.text
    print("[PASS] non-Netscape garbage rejected")

    # --- 5. delete removes file ---
    resp = client.delete("/api/social-cookies")
    assert resp.status_code == 200, resp.text
    assert not tmp_cookies.exists()
    print("[PASS] delete removes cookie file")

    # --- 6. cookiefile is applied for instagram URLs ---
    opts.DEFAULT_SOCIAL_COOKIES_FILE = tmp_cookies
    tmp_cookies.write_text(NETSCAPE)
    ydl = {}
    ydl = opts.apply_social_auth_options(ydl, "https://www.instagram.com/reel/ABC/")
    assert "cookiefile" in ydl and "cookiesfrombrowser" not in ydl, ydl
    print("[PASS] instagram URL gets cookiefile, not cookiesfrombrowser (file wins)")

    # --- 7. cookiesfrombrowser applied when no file + env set ---
    tmp_cookies.unlink(missing_ok=True)
    import os
    os.environ["SOCIAL_COOKIES_BROWSER"] = "chrome,edge"
    ydl = {}
    ydl = opts.apply_social_auth_options(ydl, "https://www.instagram.com/p/XYZ/")
    assert ydl.get("cookiesfrombrowser") == ("chrome", None, None, None), ydl
    assert opts.social_cookies_browsers() == ["chrome", "edge"]
    print("[PASS] cookiesfrombrowser used when no file + SOCIAL_COOKIES_BROWSER set")

    # --- 8. YouTube URL never gets social browser cookies ---
    ydl = {}
    ydl = opts.apply_social_auth_options(ydl, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert "cookiesfrombrowser" not in ydl, ydl
    print("[PASS] youtube URL unaffected by social browser cookies")

    # --- 9. instagram error help ---
    help_text = opts.instagram_error_help("ERROR: [Instagram] abc: Instagram sent an empty media response.")
    assert "SOCIAL_COOKIES_BROWSER" in help_text and "instagram_cookies.txt" in help_text, help_text
    print("[PASS] instagram error help contains actionable steps")

    print("\nALL SOCIAL COOKIES TESTS PASSED")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)
