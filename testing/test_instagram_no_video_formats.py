"""Regression test for Instagram's 'No video formats found' retry handling.

Run from the repo root:
    python testing/test_instagram_no_video_formats.py
"""
import sys
import asyncio
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from models import SocialDownloadRequest
from routes import download as download_routes
from services.downloader import (
    _categorize_error,
    _download_root_for_url,
    _mark_error_or_retry,
    _normalize_download_profile,
    download_tasks,
)
from services.files import DOWNLOAD_DIR, INSTAGRAM_TEMP_DIR, resolve_download_path


def main() -> None:
    post_root = _download_root_for_url("https://www.instagram.com/p/DbaAGMiGVAN/")
    reel_root = _download_root_for_url("https://www.instagram.com/reel/DbaAGMiGVAN/")
    assert post_root != DOWNLOAD_DIR and post_root.name == "_instagram_temp", post_root
    assert reel_root == DOWNLOAD_DIR, reel_root

    INSTAGRAM_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = INSTAGRAM_TEMP_DIR / "Post by samreenkaur__ (DbdjcLvjej6).NA"
    temp_file.write_text("temp")
    resolved_temp = resolve_download_path(temp_file.name)
    assert resolved_temp.parent == INSTAGRAM_TEMP_DIR, resolved_temp

    calls: list[tuple[str, str, str]] = []

    async def fake_validate_public_url(url: str) -> str:
        return url

    async def fake_initiate_download(url: str, quality: str = "best", format_ext: str = "mp4") -> str:
        calls.append((url, quality, format_ext))
        return "task-123"

    original_validate = download_routes.validate_public_url
    original_initiate = download_routes.initiate_download
    download_routes.validate_public_url = fake_validate_public_url
    download_routes.initiate_download = fake_initiate_download
    try:
        response = asyncio.run(
            download_routes.social_download_video(
                SocialDownloadRequest(
                    url="https://www.instagram.com/reel/DbaADc_q9mg/",
                    quality="best",
                    format="mp4",
                )
            )
        )
    finally:
        download_routes.validate_public_url = original_validate
        download_routes.initiate_download = original_initiate

    assert response["task_id"] == "task-123", response
    assert calls == [("https://www.instagram.com/reel/DbaADc_q9mg/", "best", "best")], calls

    insta_quality, insta_format = _normalize_download_profile(
        "https://www.instagram.com/reel/DbaADc_q9mg/",
        "1080",
        "mp4",
    )
    assert (insta_quality, insta_format) == ("best", "best"), (insta_quality, insta_format)

    yt_quality, yt_format = _normalize_download_profile(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "1080",
        "mp4",
    )
    assert (yt_quality, yt_format) == ("1080", "mp4"), (yt_quality, yt_format)

    error_text = "ERROR: [Instagram] DbaADc_q9mg: No video formats found!"

    category = _categorize_error(error_text)
    assert category == "unsupported", category

    task_id = "test-instagram-no-video-formats"
    original_task = download_tasks.get(task_id)
    download_tasks[task_id] = {
        "status": "downloading",
        "retry_count": 0,
        "cancel_requested": False,
    }
    try:
        _mark_error_or_retry(task_id, error_text)
        task = download_tasks[task_id]
        assert task["status"] == "error", task
        assert task["retryable"] is False, task
        assert task["next_retry_at"] is None, task
        assert task["error_category"] == "unsupported", task
        print("[PASS] 'No video formats found' is terminal and does not auto-retry")
    finally:
        if original_task is None:
            download_tasks.pop(task_id, None)
        else:
            download_tasks[task_id] = original_task

    print("\nALL INSTAGRAM NO-FORMATS TESTS PASSED")


if __name__ == "__main__":
    main()