import asyncio
import os
import re
import time
import uuid
import base64
import urllib.request
from urllib.parse import parse_qs
from pathlib import Path
from threading import RLock
from typing import Dict, List

import yt_dlp

from services.files import DOWNLOAD_DIR, clean_title, extract_video_id
from services.job_store import delete_job as delete_job_record
from services.job_store import load_jobs, save_jobs
from services.url_guard import validate_public_url

# Dictionary to hold the download progress of tasks
# Structure: { video_id: {"status": "downloading", "percent": 0.0, "title": "", ...} }
download_tasks: Dict[str, dict] = load_jobs()

MAX_CONCURRENT_DOWNLOADS = max(1, int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "2") or "2"))
MAX_AUTO_RETRIES = max(0, int(os.environ.get("MAX_AUTO_RETRIES", "1") or "1"))
AUTO_RETRY_BASE_DELAY_SECONDS = max(5, int(os.environ.get("AUTO_RETRY_BASE_DELAY_SECONDS", "20") or "20"))

TERMINAL_STATUSES = {"completed", "error", "cancelled"}
QUEUED_STATUSES = {"pending", "queued"}
ACTIVE_STATUSES = {"pending", "queued", "starting", "downloading", "processing"}

STATE_LOCK = RLock()
PENDING_TASK_IDS: list[str] = []
RUNNING_TASK_IDS: set[str] = set()
_QUEUE_DISPATCHER_TASK: asyncio.Task | None = None

for _task_id, _task in list(download_tasks.items()):
    if _task.get("status") not in TERMINAL_STATUSES:
        _task["status"] = "pending"
        _task["percent"] = "0%"
        _task["progress"] = 0.0
        _task["cancel_requested"] = False
        if _task_id not in PENDING_TASK_IDS:
            PENDING_TASK_IDS.append(_task_id)

_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean(value: str) -> str:
    return _ANSI.sub("", value).strip()


def _normalize_quality(value: str) -> str:
    return str(value).strip().lower().replace("p", "")


def _extract_custom_url(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        match = re.search(r'player-x\.php\?q=([A-Za-z0-9+/=]+)', html)
        if match:
            q_b64 = match.group(1)
            decoded = base64.b64decode(q_b64).decode('utf-8', errors='ignore')
            parsed = parse_qs(decoded)
            if 'tag' in parsed:
                tag_html = parsed['tag'][0]
                src_match = re.search(r'src=["\']([^"\']+)["\']', tag_html)
                if src_match:
                    return src_match.group(1)
    except Exception as e:
        pass
    return None


def _categorize_error(message: str) -> str:
    text = (message or "").lower()
    transient_markers = [
        "timed out", "timeout", "temporarily unavailable", "connection reset",
        "connection aborted", "network is unreachable", "http error 5", "503", "502", "504",
        "fragment", "incomplete read",
    ]
    auth_markers = ["sign in", "login", "cookies", "private video", "members-only", "permission"]
    geo_markers = ["not available in your country", "geo", "region"]
    unsupported_markers = ["unsupported url", "no suitable extractor"]
    removed_markers = ["video unavailable", "removed", "deleted", "does not exist"]
    if any(marker in text for marker in transient_markers):
        return "network"
    if any(marker in text for marker in auth_markers):
        return "auth"
    if any(marker in text for marker in geo_markers):
        return "geo"
    if any(marker in text for marker in unsupported_markers):
        return "unsupported"
    if any(marker in text for marker in removed_markers):
        return "unavailable"
    return "unknown"


def _is_retryable_error(category: str) -> bool:
    return category in {"network", "unknown"}


def _queue_position(task_id: str) -> int | None:
    with STATE_LOCK:
        active_pending = [
            pending_id
            for pending_id in PENDING_TASK_IDS
            if download_tasks.get(pending_id, {}).get("status") in QUEUED_STATUSES
            and not download_tasks.get(pending_id, {}).get("cancel_requested")
        ]
        if task_id not in active_pending:
            return None
        return active_pending.index(task_id) + 1


def _refresh_queue_positions() -> None:
    with STATE_LOCK:
        for task_id in list(PENDING_TASK_IDS):
            task = download_tasks.get(task_id)
            if not task or task.get("status") not in QUEUED_STATUSES:
                continue
            position = _queue_position(task_id)
            task["queue_position"] = position
            task["queue_size"] = len(PENDING_TASK_IDS)
            task["max_concurrent_downloads"] = MAX_CONCURRENT_DOWNLOADS
            _touch_task(task_id)


async def ensure_queue_dispatcher() -> None:
    global _QUEUE_DISPATCHER_TASK
    if _QUEUE_DISPATCHER_TASK is None or _QUEUE_DISPATCHER_TASK.done():
        _QUEUE_DISPATCHER_TASK = asyncio.create_task(_queue_dispatcher())


async def resume_pending_downloads() -> None:
    with STATE_LOCK:
        _refresh_queue_positions()
        if PENDING_TASK_IDS:
            save_jobs(download_tasks)
    await ensure_queue_dispatcher()


async def _queue_dispatcher() -> None:
    while True:
        started_any = False
        with STATE_LOCK:
            while len(RUNNING_TASK_IDS) < MAX_CONCURRENT_DOWNLOADS and PENDING_TASK_IDS:
                now = time.time()
                ready_index = None
                for index, candidate_id in enumerate(PENDING_TASK_IDS):
                    candidate = download_tasks.get(candidate_id)
                    if not candidate or candidate.get("status") in TERMINAL_STATUSES:
                        ready_index = index
                        break
                    if candidate.get("cancel_requested"):
                        ready_index = index
                        break
                    if float(candidate.get("next_retry_at") or 0) <= now:
                        ready_index = index
                        break
                if ready_index is None:
                    break

                task_id = PENDING_TASK_IDS.pop(ready_index)
                task = download_tasks.get(task_id)
                if not task or task.get("status") in TERMINAL_STATUSES:
                    continue
                if task.get("cancel_requested"):
                    task["status"] = "cancelled"
                    task["percent"] = "0%"
                    task["progress"] = 0.0
                    task["queue_position"] = None
                    _touch_task(task_id)
                    continue
                if float(task.get("next_retry_at") or 0) > time.time():
                    PENDING_TASK_IDS.append(task_id)
                    break
                RUNNING_TASK_IDS.add(task_id)
                task["status"] = "queued"
                task["queue_position"] = None
                task["started_at"] = time.time()
                task["max_concurrent_downloads"] = MAX_CONCURRENT_DOWNLOADS
                _touch_task(task_id)
                asyncio.create_task(_run_queued_download(task_id))
                started_any = True
            _refresh_queue_positions()
        if started_any:
            save_jobs(download_tasks)
        await asyncio.sleep(0.5)


async def _run_queued_download(task_id: str) -> None:
    task = download_tasks.get(task_id)
    if not task:
        with STATE_LOCK:
            RUNNING_TASK_IDS.discard(task_id)
        return
    try:
        await asyncio.to_thread(
            start_download_sync,
            task.get("url"),
            task_id,
            task.get("quality", "best"),
            task.get("format", "mp4"),
        )
    finally:
        with STATE_LOCK:
            RUNNING_TASK_IDS.discard(task_id)
            _refresh_queue_positions()
        save_jobs(download_tasks)


def _resolve_downloaded_file(ydl, info: dict, format_ext: str) -> str:
    """Resolve the downloaded file path with retry logic to handle Windows file locking."""
    raw_filename = ydl.prepare_filename(info)
    final_path = Path(raw_filename)

    # Retry with exponential backoff to handle Windows file locks
    # (antivirus scanning, file explorer preview, etc.)
    max_retries = 5
    retry_delay = 0.1  # Start with 100ms
    
    for attempt in range(max_retries):
        if final_path.exists():
            return raw_filename

        for ext in [format_ext, "mp4", "mkv", "webm", "mp3", "m4a"]:
            candidate = final_path.with_suffix(f".{ext}")
            if candidate.exists():
                return str(candidate)
        
        # If not found on last attempt, return the raw filename anyway
        if attempt == max_retries - 1:
            return raw_filename
        
        # Wait before retrying (exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s)
        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 2.0)  # Cap at 2 seconds

    return raw_filename


def _touch_task(task_id: str) -> None:
    if task_id in download_tasks:
        download_tasks[task_id]["updated_at"] = time.time()


def _persist_if_terminal(task_id: str) -> None:
    if download_tasks.get(task_id, {}).get("status") in TERMINAL_STATUSES:
        save_jobs(download_tasks)


def _mark_completed(task_id: str, ydl, info: dict, format_ext: str) -> None:
    filename = _resolve_downloaded_file(ydl, info, format_ext)
    now = time.time()
    download_tasks[task_id].update({
        "filename": filename,
        "title": clean_title(filename),
        "video_id": extract_video_id(filename) or info.get("id"),
        "status": "completed",
        "progress": 100.0,
        "last_progress": 100.0,
        "completed_at": now,
        "updated_at": now,
        "last_error": None,
        "error": None,
        "error_category": None,
        "retryable": False,
        "next_retry_at": None,
    })
    _touch_task(task_id)


def _mark_error_or_retry(task_id: str, clean_error: str) -> None:
    category = _categorize_error(clean_error)
    retryable = _is_retryable_error(category)
    task = download_tasks.get(task_id)
    if not task:
        return

    retry_count = int(task.get("retry_count") or 0)
    auto_retry = retryable and retry_count < MAX_AUTO_RETRIES and not task.get("cancel_requested")
    now = time.time()

    if auto_retry:
        next_retry_at = now + AUTO_RETRY_BASE_DELAY_SECONDS * (2 ** retry_count)
        task.update({
            "status": "pending",
            "percent": "0%",
            "progress": 0.0,
            "last_progress": 0.0,
            "speed": "",
            "eta": "",
            "retry_count": retry_count + 1,
            "last_error": clean_error,
            "error": f"Auto retry scheduled: {clean_error}",
            "error_category": category,
            "retryable": True,
            "next_retry_at": next_retry_at,
            "updated_at": now,
        })
        with STATE_LOCK:
            if task_id not in PENDING_TASK_IDS:
                PENDING_TASK_IDS.append(task_id)
            _refresh_queue_positions()
        return

    task.update({
        "status": "error",
        "error": clean_error,
        "last_error": clean_error,
        "error_category": category,
        "retryable": retryable,
        "next_retry_at": None,
        "updated_at": now,
    })
    _touch_task(task_id)


def start_download_sync(url: str, task_id: str, quality: str, format_ext: str):
    quality = _normalize_quality(quality)
    # Ensure we don't crash if the task wasn't pre-seeded; preserve queue metadata.
    existing_task = download_tasks.get(task_id, {})
    created_at = existing_task.get("created_at", time.time())
    download_tasks[task_id] = {
        "status": "starting",
        "percent": "0%",
        "title": existing_task.get("title") or "Unknown",
        "filename": None,
        "video_id": existing_task.get("video_id"),
        "cancel_requested": existing_task.get("cancel_requested", False),
        "url": url,
        "quality": quality,
        "format": format_ext,
        "created_at": created_at,
        "queued_at": existing_task.get("queued_at", created_at),
        "started_at": existing_task.get("started_at", time.time()),
        "updated_at": time.time(),
        "progress": 0.0,
        "last_progress": 0.0,
        "queue_position": None,
        "max_concurrent_downloads": MAX_CONCURRENT_DOWNLOADS,
        "retry_count": int(existing_task.get("retry_count") or 0),
        "max_auto_retries": MAX_AUTO_RETRIES,
        "last_error": existing_task.get("last_error"),
        "error_category": existing_task.get("error_category"),
        "retryable": existing_task.get("retryable", False),
        "next_retry_at": None,
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

    cookies_file = Path(__file__).resolve().parent.parent / "instagram_cookies.txt"
    if cookies_file.exists():
        ydl_opts["cookiefile"] = str(cookies_file)

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
            # Small delay to allow Windows to release file locks from antivirus/indexing
            time.sleep(0.5)
            _mark_completed(task_id, ydl, info, format_ext)
    except Exception as e:
        if download_tasks[task_id].get("status") == "cancelled":
            return

        clean_error = _clean(str(e))

        # Some public sites are not recognized by platform extractors.
        # Retry with yt-dlp generic extractor before failing.
        if "Unsupported URL" in clean_error:
            custom_extracted = _extract_custom_url(url)
            if custom_extracted:
                url = custom_extracted

            try:
                generic_opts = dict(ydl_opts)
                generic_opts["force_generic_extractor"] = True
                with yt_dlp.YoutubeDL(generic_opts) as ydl_generic:
                    info = ydl_generic.extract_info(url, download=True)
                    download_tasks[task_id]["title"] = info.get("title", "Unknown")
                    download_tasks[task_id]["video_id"] = info.get("id")
                    if download_tasks[task_id].get("status") == "cancelled":
                        return
                    _mark_completed(task_id, ydl_generic, info, format_ext)
                    return
            except Exception as generic_error:
                clean_error = _clean(str(generic_error))

        _mark_error_or_retry(task_id, clean_error)
    finally:
        if download_tasks.get(task_id, {}).get("status") == "cancelled":
            download_tasks[task_id]["percent"] = "0%"
            _touch_task(task_id)
        _persist_if_terminal(task_id)


async def retry_download_task(task_id: str) -> str | None:
    task = download_tasks.get(task_id)
    if not task:
        return None
    if task.get("status") not in TERMINAL_STATUSES:
        return task_id
    if not task.get("url"):
        raise ValueError("Cannot retry without the original URL")
    safe_url = await validate_public_url(task.get("url"))

    with STATE_LOCK:
        task = download_tasks.get(task_id)
        if not task:
            return None
        if task.get("status") not in TERMINAL_STATUSES:
            return task_id
        now = time.time()
        task.update({
            "status": "pending",
            "percent": "0%",
            "progress": 0.0,
            "last_progress": 0.0,
            "speed": "",
            "eta": "",
            "filename": None,
            "cancel_requested": False,
            "url": safe_url,
            "queued_at": now,
            "updated_at": now,
            "completed_at": None,
            "error": None,
            "last_error": task.get("last_error") or task.get("error"),
            "error_category": None,
            "retryable": False,
            "next_retry_at": None,
            "manual_retry_count": int(task.get("manual_retry_count") or 0) + 1,
        })
        if task_id not in PENDING_TASK_IDS:
            PENDING_TASK_IDS.append(task_id)
        _refresh_queue_positions()
        save_jobs(download_tasks)
    await ensure_queue_dispatcher()
    return task_id


async def initiate_download(url: str, quality: str = "best", format_ext: str = "mp4"):
    url = await validate_public_url(url)
    quality = _normalize_quality(quality)
    format_ext = str(format_ext).strip().lower()

    with STATE_LOCK:
        # Deduplication: if an identical task (same url+quality+format) is already
        # active (not in terminal states), return its task_id instead of creating
        # a duplicate.
        for existing_task_id, data in list(download_tasks.items()):
            if (
                data.get("url") == url
                and data.get("quality") == quality
                and data.get("format") == format_ext
                and data.get("status") not in TERMINAL_STATUSES
            ):
                return existing_task_id

        task_id = str(uuid.uuid4())
        now = time.time()
        download_tasks[task_id] = {
            "status": "pending",
            "percent": "0%",
            "title": "Unknown",
            "filename": None,
            "video_id": None,
            "cancel_requested": False,
            "url": url,
            "quality": quality,
            "format": format_ext,
            "created_at": now,
            "queued_at": now,
            "updated_at": now,
            "progress": 0.0,
            "last_progress": 0.0,
            "queue_position": None,
            "max_concurrent_downloads": MAX_CONCURRENT_DOWNLOADS,
            "retry_count": 0,
            "max_auto_retries": MAX_AUTO_RETRIES,
            "last_error": None,
            "error_category": None,
            "retryable": False,
            "next_retry_at": None,
        }
        PENDING_TASK_IDS.append(task_id)
        _refresh_queue_positions()
        save_jobs(download_tasks)

    await ensure_queue_dispatcher()
    return task_id

def get_download_status(task_id: str):
    task = download_tasks.get(task_id)
    if not task:
        return {"status": "not_found"}
    item = dict(task)
    if item.get("status") in QUEUED_STATUSES:
        item["queue_position"] = _queue_position(task_id)
        item["queue_size"] = len(PENDING_TASK_IDS)
        item["max_concurrent_downloads"] = MAX_CONCURRENT_DOWNLOADS
    return item


def queue_summary() -> dict:
    with STATE_LOCK:
        pending = [task_id for task_id in PENDING_TASK_IDS if download_tasks.get(task_id, {}).get("status") in QUEUED_STATUSES]
        running = [task_id for task_id in RUNNING_TASK_IDS if download_tasks.get(task_id, {}).get("status") in ACTIVE_STATUSES]
        return {
            "pending": len(pending),
            "running": len(running),
            "max_concurrent": MAX_CONCURRENT_DOWNLOADS,
            "pending_task_ids": pending,
            "running_task_ids": running,
        }


def list_downloads() -> List[dict]:
    items = []
    for task_id, data in download_tasks.items():
        item = dict(data)
        filename = item.get("filename")
        if filename:
            item["filename"] = Path(filename).name
        item["task_id"] = task_id
        if item.get("status") in QUEUED_STATUSES:
            item["queue_position"] = _queue_position(task_id)
            item["queue_size"] = len(PENDING_TASK_IDS)
            item["max_concurrent_downloads"] = MAX_CONCURRENT_DOWNLOADS
        elif task_id in RUNNING_TASK_IDS:
            item["queue_position"] = None
            item["max_concurrent_downloads"] = MAX_CONCURRENT_DOWNLOADS
        items.append(item)

    return sorted(
        items,
        key=lambda item: item.get("created_at", 0),
        reverse=True,
    )


def delete_download(task_id: str) -> bool:
    with STATE_LOCK:
        if task_id not in download_tasks:
            return False
        task = download_tasks.get(task_id, {})
        if task.get("status") in ACTIVE_STATUSES:
            task["cancel_requested"] = True
            if task_id in PENDING_TASK_IDS:
                PENDING_TASK_IDS.remove(task_id)
                task["status"] = "cancelled"
                _touch_task(task_id)
                save_jobs(download_tasks)
                return True
            save_jobs(download_tasks)
            return True
        download_tasks.pop(task_id, None)
        delete_job_record(task_id)
        return True


def clear_downloads() -> None:
    with STATE_LOCK:
        for task in download_tasks.values():
            if task.get("status") in ACTIVE_STATUSES:
                task["cancel_requested"] = True
        terminal_ids = [task_id for task_id, task in download_tasks.items() if task.get("status") in TERMINAL_STATUSES]
        for task_id in terminal_ids:
            download_tasks.pop(task_id, None)
            delete_job_record(task_id)
        PENDING_TASK_IDS[:] = [task_id for task_id in PENDING_TASK_IDS if task_id in download_tasks]
        save_jobs(download_tasks)


def request_cancel(task_id: str) -> bool:
    with STATE_LOCK:
        task = download_tasks.get(task_id)
        if not task:
            return False
        task["cancel_requested"] = True
        if task.get("status") in QUEUED_STATUSES and task_id in PENDING_TASK_IDS:
            PENDING_TASK_IDS.remove(task_id)
            task["status"] = "cancelled"
            task["percent"] = "0%"
            task["progress"] = 0.0
            task["queue_position"] = None
        _touch_task(task_id)
        _refresh_queue_positions()
        save_jobs(download_tasks)
        return True
