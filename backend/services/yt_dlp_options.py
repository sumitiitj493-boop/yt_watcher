from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PUBLIC_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BACKEND_DIR = Path(__file__).resolve().parents[1]
YOUTUBE_COOKIES_FILE = BACKEND_DIR / "youtube_cookies.txt"
SOCIAL_COOKIES_FILE = BACKEND_DIR / "instagram_cookies.txt"


def is_youtube_url(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"} or host.endswith(".youtube.com")


def apply_cookiefile(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    cookies_file = YOUTUBE_COOKIES_FILE if is_youtube_url(url) else SOCIAL_COOKIES_FILE
    if cookies_file.exists():
        ydl_opts["cookiefile"] = str(cookies_file)
    return ydl_opts


def add_generic_impersonation(ydl_opts: dict[str, Any]) -> dict[str, Any]:
    """Enable yt-dlp's generic extractor Cloudflare impersonation retry."""
    extractor_args = dict(ydl_opts.get("extractor_args") or {})
    generic_args = dict(extractor_args.get("generic") or {})
    generic_args.setdefault("impersonate", ["chrome"])
    extractor_args["generic"] = generic_args
    ydl_opts["extractor_args"] = extractor_args
    return ydl_opts
