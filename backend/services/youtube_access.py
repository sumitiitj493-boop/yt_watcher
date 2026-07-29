from __future__ import annotations

import time
from typing import Any

import yt_dlp

from services.yt_dlp_options import (
    PUBLIC_HTTP_HEADERS,
    apply_reliable_ytdlp_options,
    cookiefile_report,
    is_youtube_url,
    safe_cookie_report_for_response,
    tool_runtime_report,
    validate_cookiefile_for_ytdlp,
)


def _categorize_error(message: str) -> str:
    text = (message or "").lower()
    if any(marker in text for marker in ["startup timeout", "timed out before media transfer", "pre-download timed out"]):
        return "timeout"
    if any(marker in text for marker in ["confirm you're not a bot", "confirm you’re not a bot", "unusual traffic", "bot check"]):
        return "bot_check"
    if any(marker in text for marker in ["timed out", "timeout", "temporarily unavailable", "connection reset", "503", "502", "504", "fragment"]):
        return "network"
    if any(marker in text for marker in ["sign in", "login", "cookies", "private video", "members-only", "members only", "join this channel", "permission", "not authorized"]):
        return "auth"
    if any(marker in text for marker in ["not available in your country", "geo", "region"]):
        return "geo"
    if any(marker in text for marker in ["unsupported url", "no suitable extractor"]):
        return "unsupported"
    if any(marker in text for marker in ["video unavailable", "removed", "deleted", "does not exist"]):
        return "unavailable"
    return "unknown"


def _format_summary(formats: list[dict[str, Any]]) -> dict[str, Any]:
    heights = sorted({int(fmt.get("height")) for fmt in formats if fmt.get("height")}, reverse=True)
    video_count = sum(1 for fmt in formats if fmt.get("vcodec") not in {None, "none"})
    audio_count = sum(1 for fmt in formats if fmt.get("acodec") not in {None, "none"})
    return {
        "count": len(formats),
        "video_count": video_count,
        "audio_count": audio_count,
        "has_video": video_count > 0,
        "has_audio": audio_count > 0,
        "heights": heights[:12],
    }


def check_youtube_access_sync(url: str) -> dict[str, Any]:
    """Safely test whether yt-dlp can see a YouTube URL with local cookies.

    This never returns cookie values. It is intended as a quick pre-flight check
    before trying a large members-only video download.
    """
    started_at = time.time()
    url = str(url or "").strip()
    cookie_report = cookiefile_report(url)
    runtime_report = tool_runtime_report()

    result: dict[str, Any] = {
        "ok": False,
        "url": url,
        "is_youtube": is_youtube_url(url),
        "cookies": safe_cookie_report_for_response(cookie_report),
        "runtime": runtime_report,
        "elapsed_seconds": 0.0,
        "title": "",
        "id": "",
        "webpage_url": "",
        "duration": None,
        "uploader": "",
        "availability": "",
        "formats": _format_summary([]),
        "error": "",
        "error_category": "",
        "suggestions": [],
    }

    if not result["is_youtube"]:
        result["error"] = "This diagnostic endpoint is for YouTube URLs only."
        result["error_category"] = "unsupported"
        return result

    suggestions: list[str] = []
    if not cookie_report.get("exists"):
        suggestions.append("For members-only videos, save Netscape-format cookies as backend/youtube_cookies.txt.")
    elif cookie_report.get("warning"):
        suggestions.append(str(cookie_report["warning"]))
    if not runtime_report.get("ffmpeg"):
        suggestions.append("Install FFmpeg and keep it on PATH so video+audio merge and MP3 extraction work.")
    node_version = str(runtime_report.get("node_version") or "")
    if not runtime_report.get("node_path"):
        suggestions.append("Install Node.js 22+ or configure YTDLP_JS_RUNTIMES; YouTube extraction is more reliable with a supported JS runtime.")
    elif node_version and node_version != "unknown":
        try:
            major = int(node_version.lstrip("v").split(".", 1)[0])
            if major < 22:
                suggestions.append("Node.js is installed, but yt-dlp may consider this version unsupported. Upgrade to Node.js 22+ or 24+.")
        except Exception:
            pass

    try:
        validate_cookiefile_for_ytdlp(url)
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "ignoreerrors": False,
            "http_headers": PUBLIC_HTTP_HEADERS,
        }
        apply_reliable_ytdlp_options(ydl_opts, url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}

        formats = info.get("formats") or []
        result.update({
            "ok": True,
            "title": info.get("title") or "",
            "id": info.get("id") or "",
            "webpage_url": info.get("webpage_url") or url,
            "duration": info.get("duration"),
            "uploader": info.get("uploader") or info.get("channel") or "",
            "availability": info.get("availability") or "",
            "formats": _format_summary(formats),
        })
        if not formats:
            result["ok"] = False
            result["error"] = "Metadata loaded, but yt-dlp returned no downloadable formats."
            result["error_category"] = "no_formats"
            suggestions.append("Update yt-dlp and make sure cookies are fresh. Some DRM/PO-token restricted formats may not be downloadable.")
    except Exception as exc:
        message = str(exc)
        category = _categorize_error(message)
        result.update({
            "ok": False,
            "error": message,
            "error_category": category,
        })
        if category == "auth":
            suggestions.append("Re-export youtube_cookies.txt from the exact browser/profile where the members-only video plays.")
        elif category == "bot_check":
            suggestions.append("Open YouTube in that browser, solve any bot/account checks, then export fresh cookies and retry.")
        elif category in {"network", "timeout"}:
            suggestions.append("Retry after a minute; if it repeats, update yt-dlp and check your network/VPN/region.")
        elif category == "geo":
            suggestions.append("The video may be region-restricted for the current network/account.")
        else:
            suggestions.append("Update yt-dlp, restart the backend, and retry with fresh cookies.")

    result["elapsed_seconds"] = round(time.time() - started_at, 2)
    result["suggestions"] = list(dict.fromkeys(suggestions))
    return result


async def check_youtube_access(url: str) -> dict[str, Any]:
    import asyncio

    return await asyncio.to_thread(check_youtube_access_sync, url)
