import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List

import yt_dlp

from services.files import DOWNLOAD_DIR, clean_title, extract_video_id

_VIDEO_FORMAT_RE = re.compile(r"^(\d{3,4})p?$")


def _duration_label(seconds: int | None) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_bytes(value: int | None) -> str:
    if not value or value <= 0:
        return ""
    units = ["B", "KB", "MB", "GB"]
    size = float(value)
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def _best_thumbnail(info: dict) -> str:
    thumbnails = info.get("thumbnails") or []
    if thumbnails:
        best = sorted(thumbnails, key=lambda item: (item.get("width") or 0) * (item.get("height") or 0))[-1]
        return best.get("url") or info.get("thumbnail") or ""
    return info.get("thumbnail") or ""


def _extract_qualities(formats: List[dict]) -> List[str]:
    heights = set()
    for fmt in formats:
        height = fmt.get("height")
        if height:
            heights.add(str(height))
            continue
        note = str(fmt.get("format_note") or "")
        match = _VIDEO_FORMAT_RE.match(note)
        if match:
            heights.add(match.group(1))
    preferred_order = ["2160", "1440", "1080", "720", "480", "360", "240", "144"]
    found = [q for q in preferred_order if q in heights]
    return ["best", *found] if found else ["best", "1080", "720", "480", "360"]


def _extract_formats(formats: List[dict]) -> List[str]:
    exts = set()
    has_audio = False
    for fmt in formats:
        ext = (fmt.get("ext") or "").lower()
        if ext in {"mp4", "webm", "mkv", "m4a"}:
            exts.add(ext)
        if fmt.get("acodec") not in {None, "none"}:
            has_audio = True
    ordered = [ext for ext in ["mp4", "webm", "mkv", "m4a"] if ext in exts]
    if has_audio:
        ordered.append("mp3")
    return ordered or ["mp4", "mp3"]


def _estimate_size(formats: List[dict]) -> int | None:
    candidates = []
    for fmt in formats:
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if size:
            candidates.append(int(size))
    return max(candidates) if candidates else None


def _find_existing(video_id: str | None, title: str | None) -> dict | None:
    if not DOWNLOAD_DIR.exists():
        return None
    normalized_title = (title or "").strip().lower()
    for file_path in DOWNLOAD_DIR.iterdir():
        if not file_path.is_file():
            continue
        filename = file_path.name
        if video_id and (extract_video_id(filename) == video_id or f"({video_id})" in filename):
            stat = file_path.stat()
            return {
                "filename": filename,
                "title": clean_title(filename),
                "size": stat.st_size,
                "created_at": stat.st_mtime,
                "reason": "video_id",
            }
        if normalized_title and clean_title(filename).lower() == normalized_title:
            stat = file_path.stat()
            return {
                "filename": filename,
                "title": clean_title(filename),
                "size": stat.st_size,
                "created_at": stat.st_mtime,
                "reason": "title",
            }
    return None


def _metadata_sync(url: str) -> Dict[str, Any]:
    cookies_file = Path(__file__).resolve().parents[1] / "cookies.txt"
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": False,
        "playlistend": 50,
        "extract_flat": "in_playlist",
        "ignoreerrors": False,
        "nocheckcertificate": False,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if cookies_file.exists():
        ydl_opts["cookiefile"] = str(cookies_file)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    is_playlist = bool(entries)
    first = None
    if is_playlist:
        entries_list = [entry for entry in entries if entry]
        first = entries_list[0] if entries_list else None
    else:
        entries_list = []

    target = first or info or {}
    formats = target.get("formats") or info.get("formats") or []
    title = target.get("title") or info.get("title") or "Untitled video"
    video_id = target.get("id") or info.get("id")
    duration = target.get("duration") or info.get("duration")
    estimate_size = _estimate_size(formats)
    existing = _find_existing(video_id, title)

    return {
        "url": url,
        "id": video_id,
        "title": title,
        "uploader": target.get("uploader") or target.get("channel") or info.get("uploader") or info.get("channel") or "",
        "duration": duration,
        "duration_label": _duration_label(duration),
        "thumbnail": _best_thumbnail(target or info),
        "webpage_url": target.get("webpage_url") or info.get("webpage_url") or url,
        "qualities": _extract_qualities(formats),
        "formats": _extract_formats(formats),
        "estimated_size": estimate_size,
        "estimated_size_label": _format_bytes(estimate_size),
        "is_playlist": is_playlist,
        "playlist_count": len(entries_list) if is_playlist else 0,
        "playlist_title": info.get("title") if is_playlist else "",
        "preview_items": [
            {
                "id": entry.get("id"),
                "title": entry.get("title") or "Untitled",
                "duration": entry.get("duration"),
                "duration_label": _duration_label(entry.get("duration")),
                "thumbnail": _best_thumbnail(entry),
            }
            for entry in entries_list[:10]
        ],
        "already_downloaded": bool(existing),
        "existing_file": existing,
    }


async def fetch_metadata(url: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_metadata_sync, url)
