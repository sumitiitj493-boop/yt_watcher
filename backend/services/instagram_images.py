"""Instagram photo/post image download.

For Instagram posts (single photos and photo carousels), yt-dlp's current
extractor exposes the images only as *thumbnails*, not as *formats*, so the
normal video pipeline reports "No video formats found". This module:

1. extracts the post with yt-dlp (ignore_no_formats_error),
2. picks the largest-resolution image URL for every carousel item,
3. downloads each image directly (curl_cffi + browser impersonation)
   into DOWNLOAD_DIR so they appear in the Library.

If a Netscape-format instagram_cookies.txt exists (from a logged-in browser),
it is passed to both yt-dlp and the CDN fetch — this is what allows viewing
posts from private accounts the logged-in user follows.
"""
import re
import time
import uuid
from pathlib import Path
from threading import RLock

from curl_cffi import requests as cffi_requests

from services.files import DOWNLOAD_DIR
from services.yt_dlp_options import apply_social_auth_options, get_cookiefile_for_url

_PHOTO_JOBS: dict[str, dict] = {}
_PHOTO_JOBS_LOCK = RLock()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

_PIXEL_RE = re.compile(r"_(?:s|p)(\d+)x(\d+)")

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _cookie_header() -> str:
    """Build a 'name=value; ...' Cookie header from the social cookies.txt file.

    Only rows for instagram(.com) domains are used. Returns "" if no file or
    no usable rows.
    """
    path = get_cookiefile_for_url("https://www.instagram.com/")
    if not path:
        return ""
    pairs: list[str] = []
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            elif line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, _, _, _, name, value = parts[:7]
            if "instagram" in domain and name and value:
                pairs.append(f"{name}={value}")
    except OSError:
        return ""
    return "; ".join(pairs)


def _best_photo_url(thumbnails) -> str | None:
    """Pick the largest-resolution image URL from a thumbnail list."""
    best_url = None
    best_size = 0
    for thumb in thumbnails or []:
        url = (thumb or {}).get("url") or ""
        if not url:
            continue
        match = _PIXEL_RE.search(url)
        size = int(match.group(1)) * int(match.group(2)) if match else 0
        if size > best_size:
            best_size = size
            best_url = url
    return best_url


def _clean_title(value: str, fallback: str = "Instagram post") -> str:
    cleaned = re.sub(r"[^\w\-. ]+", " ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120] or fallback


def _unique_path(base_title: str, entry_id: str) -> Path:
    candidate = DOWNLOAD_DIR / f"{base_title} ({entry_id}).jpg"
    index = 1
    while candidate.exists():
        candidate = DOWNLOAD_DIR / f"{base_title} ({entry_id}) ({index}).jpg"
        index += 1
    return candidate


def extract_instagram_entries(url: str, max_items: int = 30) -> tuple[dict, list]:
    """Run yt-dlp on the URL and return (info, entries)."""
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
        "playlist_items": f"1:{max_items}",
    }
    # Pass the logged-in session cookies (if present) so private posts the
    # user follows can be extracted too.
    apply_social_auth_options(opts, url)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = info.get("entries") or [info]
    return info, entries


def download_instagram_photos(url: str, max_items: int = 30) -> list[str]:
    """Download every image in an Instagram post/carousel into DOWNLOAD_DIR.

    Returns the list of saved filenames (empty if nothing was found). Only
    files verified present on disk are counted.
    """
    info, entries = extract_instagram_entries(url, max_items=max_items)
    base_title = _clean_title(info.get("title")) or "Instagram post"
    saved: list[str] = []
    skipped_video = 0
    skipped_failed = 0
    for entry in entries:
        if not entry:
            skipped_video += 1
            continue
        photo_url = _best_photo_url(entry.get("thumbnails"))
        if not photo_url:
            skipped_failed += 1
            continue
        entry_id = str(entry.get("id") or uuid.uuid4().hex[:11])
        path = _unique_path(base_title, entry_id)
        try:
            headers = dict(_HEADERS)
            cookie_header = _cookie_header()
            if cookie_header:
                headers["Cookie"] = cookie_header
            response = cffi_requests.get(
                photo_url, headers=headers, impersonate="chrome", timeout=30
            )
            if response.status_code == 200 and len(response.content) > 1000:
                path.write_bytes(response.content)
                if path.exists() and path.stat().st_size > 1000:
                    saved.append(path.name)
                else:
                    skipped_failed += 1
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
            else:
                skipped_failed += 1
        except Exception:
            skipped_failed += 1
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
    return saved


def get_photo_job(job_id: str) -> dict | None:
    with _PHOTO_JOBS_LOCK:
        job = _PHOTO_JOBS.get(job_id)
        return dict(job) if job else None


def start_photo_download(url: str) -> str:
    """Queue an Instagram photo download in the background (mirrors the
    Whisper/audio job pattern)."""
    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        "job_id": job_id,
        "url": url,
        "status": "queued",
        "progress": 0,
        "message": "Photo download queued",
        "saved": [],
        "created_at": now,
        "completed_at": None,
        "error": None,
    }
    with _PHOTO_JOBS_LOCK:
        _PHOTO_JOBS[job_id] = job

    import threading

    def _runner() -> None:
        job = _PHOTO_JOBS[job_id]
        job["status"] = "downloading"
        job["message"] = "Downloading photos..."
        try:
            saved = download_instagram_photos(url)
            if saved:
                job.update({
                    "status": "completed",
                    "progress": 100,
                    "message": f"Saved {len(saved)} photo(s)",
                    "saved": saved,
                    "completed_at": time.time(),
                })
            else:
                job.update({
                    "status": "error",
                    "progress": 100,
                    "message": "No photos found in this post",
                    "error": "No photos found in this post",
                })
        except Exception as exc:
            job.update({
                "status": "error",
                "progress": 100,
                "message": str(exc),
                "error": str(exc),
            })

    threading.Thread(target=_runner, daemon=True).start()
    return job_id
