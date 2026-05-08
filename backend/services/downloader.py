import asyncio
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List

import yt_dlp

from services.files import DOWNLOAD_DIR, clean_title, extract_video_id
from services.job_store import load_jobs, save_jobs

# Dictionary to hold the download progress of tasks
# Structure: { video_id: {"status": "downloading", "percent": 0.0, "title": "", ...} }
download_tasks: Dict[str, dict] = load_jobs()

MAX_CONCURRENT_DOWNLOADS = 2
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

TERMINAL_STATUSES = {"completed", "error", "cancelled"}

_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean(value: str) -> str:
    return _ANSI.sub("", value).strip()


def _normalize_quality(value: str) -> str:
    return str(value).strip().lower().replace("p", "")


def _resolve_downloaded_file(ydl, info: dict, format_ext: str) -> str:
    raw_filename = ydl.prepare_filename(info)
    final_path = Path(raw_filename)

    if final_path.exists():
        return raw_filename

    for ext in [format_ext, "mp4", "mkv", "webm", "mp3", "m4a"]:
        candidate = final_path.with_suffix(f".{ext}")
        if candidate.exists():
            return str(candidate)

    return raw_filename


def _touch_task(task_id: str) -> None:
    if task_id in download_tasks:
        download_tasks[task_id]["updated_at"] = time.time()


def _persist_if_terminal(task_id: str) -> None:
    if download_tasks.get(task_id, {}).get("status") in TERMINAL_STATUSES:
        save_jobs(download_tasks)

def start_download_sync(url: str, task_id: str, quality: str, format_ext: str):
    quality = _normalize_quality(quality)
    # Ensure we don't crash if the task wasn't pre-seeded; prefer any existing created_at
    created_at = download_tasks.get(task_id, {}).get("created_at", time.time())
    download_tasks[task_id] = {
        "status": "starting",
        "percent": "0%",
        "title": "Unknown",
        "filename": None,
        "video_id": None,
        "cancel_requested": False,
        "url": url,
        "quality": quality,
        "format": format_ext,
        "created_at": created_at,
        "updated_at": time.time(),
        "progress": 0.0,
        "last_progress": 0.0,
    }
    save_jobs(download_tasks)

    def hook(d):
        if download_tasks[task_id].get("cancel_requested"):
            download_tasks[task_id]["status"] = "cancelled"
            raise Exception("Download cancelled")

        if d["status"] == "downloading":
            download_tasks[task_id].update({
                "status": "downloading",
                "percent": _clean(d.get("_percent_str", "0%")),
                "speed": _clean(d.get("_speed_str", "")),
                "eta": _clean(d.get("_eta_str", "")),
            })
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded_bytes = d.get("downloaded_bytes")
            if total_bytes and downloaded_bytes is not None:
                computed = round((downloaded_bytes / total_bytes) * 100, 2)
                last_progress = download_tasks[task_id].get("last_progress", 0.0)
                stabilized = max(last_progress, computed)
                download_tasks[task_id].update({
                    "progress": stabilized,
                    "last_progress": stabilized,
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": total_bytes,
                })
            _touch_task(task_id)

        elif d["status"] == "finished":
            download_tasks[task_id].update({
                "status": "processing",
                "percent": "100%",
                "progress": 100.0,
                "last_progress": 100.0,
            })
            _touch_task(task_id)

    quality_map = {
        "2160": (
            "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=2160]+bestaudio"
            "/best[height<=2160]"
            "/best"
        ),
        "1440": (
            "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=1440]+bestaudio"
            "/best[height<=1440]"
            "/best"
        ),
        "1080": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=1080]+bestaudio"
            "/best[height<=1080]"
            "/best"
        ),
        "720": (
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=720]+bestaudio"
            "/best[height<=720]"
            "/best"
        ),
        "480": (
            "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=480]+bestaudio"
            "/best[height<=480]"
            "/best"
        ),
        "360": (
            "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=360]+bestaudio"
            "/best[height<=360]"
            "/best"
        ),
        "144": (
            "bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=144]+bestaudio"
            "/best[height<=144]"
            "/best"
        ),
    }

    if format_ext == "mp3":
        format_string = "bestaudio/best"
    elif quality in ("best", ""):
        format_string = "bestvideo*[ext=mp4]+bestaudio[ext=m4a]/bestvideo*+bestaudio/best"
    else:
        format_string = quality_map.get(
            quality,
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        )

    ydl_opts = {
        "format": format_string,
        "outtmpl": (DOWNLOAD_DIR / "%(title)s (%(id)s).%(ext)s").as_posix(),
        "progress_hooks": [hook],
        "quiet": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "windowsfilenames": True,
        "js_runtimes": {
            "node": {},
        },
        "remote_components": ["ejs:github"],
        # Better defaults for public social sites
        "nocheckcertificate": False,
        "geo_bypass": True,
        "age_limit": None,
        "ignoreerrors": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    }

    cookies_file = Path("cookies.txt")
    if cookies_file.exists():
        ydl_opts["cookiefile"] = "cookies.txt"

    if format_ext == "mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            download_tasks[task_id]["title"] = info.get("title", "Unknown")
            download_tasks[task_id]["video_id"] = info.get("id")

        if download_tasks[task_id].get("status") == "cancelled":
            return

        filename = _resolve_downloaded_file(ydl, info, format_ext)
        download_tasks[task_id].update({
            "filename": filename,
            "title": clean_title(filename),
            "video_id": extract_video_id(filename) or info.get("id"),
            "status": "completed",
            "progress": 100.0,
            "last_progress": 100.0,
        })
        _touch_task(task_id)
    except Exception as e:
        if download_tasks[task_id].get("status") == "cancelled":
            return
        download_tasks[task_id]["status"] = "error"
        download_tasks[task_id]["error"] = str(e)
        _touch_task(task_id)
    finally:
        if download_tasks.get(task_id, {}).get("status") == "cancelled":
            download_tasks[task_id]["percent"] = "0%"
            _touch_task(task_id)
        _persist_if_terminal(task_id)


async def initiate_download(url: str, quality: str = "best", format_ext: str = "mp4"):
    quality = _normalize_quality(quality)
    # Deduplication: if an identical task (same url+quality+format) is already
    # active (not in terminal states), return its task_id instead of creating
    # a duplicate. This prevents multiple background downloads for the same
    # resource when the frontend calls the endpoint twice.
    for existing_task_id, data in list(download_tasks.items()):
        if (
            data.get("url") == url
            and data.get("quality") == quality
            and data.get("format") == format_ext
            and data.get("status") not in TERMINAL_STATUSES
        ):
            return existing_task_id

    task_id = str(uuid.uuid4())
    # Pre-seed the task so the background thread can safely update it immediately
    download_tasks[task_id] = {
        "status": "starting",
        "percent": "0%",
        "title": "Unknown",
        "filename": None,
        "video_id": None,
        "cancel_requested": False,
        "url": url,
        "quality": quality,
        "format": format_ext,
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": 0.0,
        "last_progress": 0.0,
    }
    save_jobs(download_tasks)

    # Runs the synchronous yt-dlp in a background thread so it doesn't block FastAPI
    async def run_with_limits():
        async with DOWNLOAD_SEMAPHORE:
            await asyncio.to_thread(start_download_sync, url, task_id, quality, format_ext)

    asyncio.create_task(run_with_limits())
    return task_id

def get_download_status(task_id: str):
    return download_tasks.get(task_id, {"status": "not_found"})


def list_downloads() -> List[dict]:
    items = []
    for task_id, data in download_tasks.items():
        item = dict(data)
        filename = item.get("filename")
        if filename:
            item["filename"] = Path(filename).name
        item["task_id"] = task_id
        items.append(item)

    return sorted(
        items,
        key=lambda item: item.get("created_at", 0),
        reverse=True,
    )


def delete_download(task_id: str) -> bool:
    if task_id not in download_tasks:
        return False
    download_tasks.pop(task_id, None)
    save_jobs(download_tasks)
    return True


def clear_downloads() -> None:
    download_tasks.clear()
    save_jobs(download_tasks)


def request_cancel(task_id: str) -> bool:
    task = download_tasks.get(task_id)
    if not task:
        return False
    task["cancel_requested"] = True
    _touch_task(task_id)
    save_jobs(download_tasks)
    return True
