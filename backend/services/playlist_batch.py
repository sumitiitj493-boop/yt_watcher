"""Playlist batch downloads.

When the user pastes a single playlist link, this module:

  1. Resolves the full list of videos in the playlist (no per-video URLs needed).
  2. Lets the caller pick a range / specific indices.
  3. Queues each selected video as its own download-queue task
     (one-by-one / sequential by default, optional parallel).
  4. Automatically adds every successfully downloaded file into a
     user-chosen local playlist ("My Playlist", "Workout Mix", ...).

Batch state lives in memory (same design as ``download_tasks``) and is
reconciled against the global download queue by a per-batch supervisor task.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from services.database import (
    add_playlist_item,
    get_file_link,
    get_playlist_items,
    list_playlists,
    save_saved_transcript,
)
from services.files import clean_title, extract_video_id
from services.downloader import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    download_tasks,
    initiate_download,
    request_cancel,
)
from services.transcripts import fetch_url_transcript
from services.yt_dlp_options import PUBLIC_HTTP_HEADERS, apply_reliable_ytdlp_options

_MAX_PLAYLIST_ENTRIES = 5000
_POLL_INTERVAL_SECONDS = 1.0
_TRANSCRIPT_FETCH_CONCURRENCY = 3

_LOCK = threading.RLock()
_BATCHES: dict[str, dict] = {}


def _duration_label(seconds: int | None) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _best_thumb(entry: dict) -> str:
    thumbnails = entry.get("thumbnails") or []
    if thumbnails:
        best = sorted(
            thumbnails,
            key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
        )[-1]
        return best.get("url") or entry.get("thumbnail") or ""
    return entry.get("thumbnail") or ""


def list_playlist_entries_sync(url: str) -> dict[str, Any]:
    """Resolve every video in a playlist from a single playlist URL.

    Uses yt-dlp's flat extraction, which is fast even for long playlists and
    does not download any media. Unavailable/private entries are skipped but
    do not break the rest of the list.
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "playlistend": _MAX_PLAYLIST_ENTRIES,
        "nocheckcertificate": False,
        "geo_bypass": True,
        "http_headers": PUBLIC_HTTP_HEADERS,
    }
    apply_reliable_ytdlp_options(ydl_opts, url)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        return {"is_playlist": False, "playlist_title": "", "count": 0, "entries": []}

    result: list[dict] = []
    for index, entry in enumerate(entries or [], start=1):
        if not entry or not isinstance(entry, dict):
            continue
        video_id = entry.get("id")
        title = entry.get("title")
        if not video_id or not title:
            continue
        result.append({
            "index": index,
            "id": video_id,
            "title": title,
            "duration": entry.get("duration"),
            "duration_label": _duration_label(entry.get("duration")),
            "thumbnail": _best_thumb(entry),
            "url": entry.get("webpage_url")
            or entry.get("url")
            or f"https://www.youtube.com/watch?v={video_id}",
        })

    return {
        "is_playlist": True,
        "url": url,
        "playlist_title": info.get("title") or "Playlist",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "count": len(result),
        "entries": result,
    }


# --------------------------------------------------------------------------
# Batch store
# --------------------------------------------------------------------------
def _public_batch(batch: dict) -> dict:
    tasks = []
    for item in batch.get("tasks", []):
        tasks.append({
            "index": item.get("index"),
            "id": item.get("id"),
            "title": item.get("title"),
            "duration_label": item.get("duration_label") or "",
            "status": item.get("status"),
            "task_id": item.get("task_id"),
            "percent": item.get("percent"),
            "progress": item.get("progress"),
            "filename": item.get("filename"),
            "error": item.get("error"),
            "added": item.get("added", False),
            "auto_add_error": item.get("auto_add_error"),
            "transcript_status": item.get("transcript_status"),
            "transcript_error": item.get("transcript_error"),
            "transcript_lines": item.get("transcript_lines"),
        })
    return {
        "id": batch.get("id"),
        "url": batch.get("url"),
        "playlist_title": batch.get("playlist_title"),
        "quality": batch.get("quality"),
        "format": batch.get("format"),
        "target_playlist_id": batch.get("target_playlist_id"),
        "target_playlist_name": batch.get("target_playlist_name") or "",
        "sequential": batch.get("sequential", True),
        "fetch_transcripts": batch.get("fetch_transcripts", False),
        "transcript_folder": batch.get("transcript_folder", ""),
        "transcripts_only": batch.get("transcripts_only", False),
        "created_at": batch.get("created_at"),
        "phase": batch.get("phase"),
        "total_count": batch.get("total_count", 0),
        "done_count": batch.get("done_count", 0),
        "completed_count": batch.get("completed_count", 0),
        "failed_count": batch.get("failed_count", 0),
        "added_count": batch.get("added_count", 0),
        "transcripts_total": batch.get("transcripts_total", 0),
        "transcripts_done_count": batch.get("transcripts_done_count", 0),
        "transcripts_saved_count": batch.get("transcripts_saved_count", 0),
        "tasks": tasks,
    }


def get_batch(batch_id: str) -> dict | None:
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        return _public_batch(batch) if batch else None


def list_batches() -> list[dict]:
    with _LOCK:
        ordered = sorted(
            _BATCHES.values(),
            key=lambda item: item.get("created_at", 0),
            reverse=True,
        )
        return [_public_batch(batch) for batch in ordered]


def _update_phase(batch: dict) -> None:
    statuses = [item.get("status", "planned") for item in batch.get("tasks", [])]
    total = len(statuses)
    done = sum(1 for status in statuses if status in TERMINAL_STATUSES)
    completed = sum(1 for status in statuses if status == "completed")
    failed = sum(1 for status in statuses if status in ("error", "cancelled"))

    batch["total_count"] = total
    batch["done_count"] = done
    batch["completed_count"] = completed
    batch["failed_count"] = failed

    if batch.get("cancel_requested"):
        batch["phase"] = "cancelled" if done == total else "cancelling"
    elif done == total:
        batch["phase"] = "completed" if failed == 0 else "partial"
    else:
        batch["phase"] = "running"

    # Transcript-only batches have no downloads; progress comes from the
    # transcript fetches themselves (done == transcripts_done_count).
    if batch.get("transcripts_only"):
        t_total = batch.get("transcripts_total", 0)
        t_done = batch.get("transcripts_done_count", 0)
        t_saved = batch.get("transcripts_saved_count", 0)
        batch["total_count"] = t_total
        batch["done_count"] = t_done
        batch["completed_count"] = t_saved
        batch["failed_count"] = max(0, t_done - t_saved)
        if batch.get("cancel_requested"):
            batch["phase"] = "cancelled" if t_done >= t_total else "cancelling"
        elif t_total > 0 and t_done >= t_total:
            batch["phase"] = "completed" if t_saved >= t_done else "partial"
        else:
            batch["phase"] = "running"


def _add_to_target_playlist(batch: dict, item: dict, filename: str) -> None:
    """Auto-save a finished download into the chosen local playlist."""
    playlist_id = batch.get("target_playlist_id")
    if not playlist_id or not filename or item.get("added"):
        return
    try:
        add_playlist_item(playlist_id, filename)
        item["added"] = True
        batch["added_count"] = batch.get("added_count", 0) + 1
    except Exception as exc:  # noqa: BLE001 -- surface as a friendly note
        item["auto_add_error"] = f"Saved to disk but could not be added to the playlist: {exc}"


async def _enqueue_one(batch: dict, item: dict) -> None:
    try:
        task_id = await initiate_download(item["url"], batch["quality"], batch["format"])
    except Exception as exc:  # noqa: BLE001
        item["status"] = "error"
        item["error"] = str(exc)
        return
    item["task_id"] = task_id
    item["status"] = download_tasks.get(task_id, {}).get("status", "queued")
    with _LOCK:
        batch["enqueued_count"] = batch.get("enqueued_count", 0) + 1


def _reconcile(batch: dict) -> dict | None:
    """Sync one batch against the global download queue.

    Returns the next item that should be enqueued (sequential batches), or
    ``None``. Kept as a plain function so it is easy to unit test.
    """
    to_enqueue = None

    # 1) Sync task states with the global queue.
    for item in batch.get("tasks", []):
        task_id = item.get("task_id")
        task = download_tasks.get(task_id) if task_id else None
        if task is None:
            # Only tasks that WERE enqueued should be flagged if the
            # queue record vanished. Planned items (sequential batches
            # that haven't started yet) simply have no task_id yet.
            if item.get("task_id") and item.get("status") in ACTIVE_STATUSES:
                item["status"] = "error"
                item["error"] = item.get("error") or "Download task is no longer available"
            continue
        item["status"] = task.get("status", item["status"])
        item["percent"] = task.get("percent", "")
        item["progress"] = task.get("progress")
        if task.get("status") == "completed":
            filename = Path(str(task.get("filename") or "")).name
            if filename:
                item["filename"] = filename
            _add_to_target_playlist(batch, item, filename)
        elif task.get("status") == "error":
            item["error"] = task.get("error") or task.get("last_error")
        elif task.get("status") == "cancelled":
            item["error"] = item.get("error") or "Cancelled"

    # 2) Sequential batches: start the next video only once nothing from
    #    this batch is still downloading (true one-by-one behaviour).
    #    Transcript-only batches enqueue nothing.
    if batch.get("sequential") and not batch.get("transcripts_only") and not batch.get("cancel_requested"):
        next_index = batch.get("next_to_enqueue", 0)
        if next_index < len(batch.get("tasks", [])):
            any_active = any(
                download_tasks.get(item.get("task_id"), {}).get("status") in ACTIVE_STATUSES
                for item in batch.get("tasks", [])
                if item.get("task_id")
            )
            if not any_active:
                candidate = batch["tasks"][next_index]
                if not candidate.get("task_id"):
                    to_enqueue = candidate

    _update_phase(batch)
    return to_enqueue


async def _supervise_batch(batch_id: str) -> None:
    """Periodically reconcile batch tasks against the global download queue."""
    while True:
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        with _LOCK:
            batch = _BATCHES.get(batch_id)
            if batch is None:
                return
            to_enqueue = _reconcile(batch)
            finished = batch.get("phase") in ("completed", "partial", "cancelled")

        if to_enqueue is not None:
            await _enqueue_one(batch, to_enqueue)
            with _LOCK:
                current = _BATCHES.get(batch_id)
                if current is not None:
                    current["next_to_enqueue"] = current.get("next_to_enqueue", 0) + 1

        if finished:
            break

    with _LOCK:
        current = _BATCHES.get(batch_id)
        if current is not None:
            current["supervisor_active"] = False
            # If a retry reset the batch while we were finishing, pick it up.
            if current.get("phase") == "running" and not current.get("done"):
                asyncio.create_task(_supervise_batch(batch_id))


async def _ensure_supervisor(batch_id: str) -> None:
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if not batch or batch.get("supervisor_active"):
            return
        batch["supervisor_active"] = True
    asyncio.create_task(_supervise_batch(batch_id))


async def _fetch_batch_transcripts(batch_id: str) -> None:
    """Fetch the YouTube auto transcript for every video in a batch, in parallel.

    Runs independently of the download queue (downloads and transcript fetches
    happen at the same time). Each successful transcript is saved into the
    persistent Transcript Saver, keyed by video id, so it survives reloads.
    """
    semaphore = asyncio.Semaphore(_TRANSCRIPT_FETCH_CONCURRENCY)

    async def fetch_one(item: dict) -> None:
        async with semaphore:
            with _LOCK:
                current = _BATCHES.get(batch_id)
                if current is None or current.get("cancel_requested"):
                    return
                current_item = next(
                    (task for task in current.get("tasks", []) if task.get("index") == item.get("index")),
                    None,
                )
            if current_item is None:
                return
            current_item["transcript_status"] = "fetching"
            try:
                result = await fetch_url_transcript(item["url"])
            except Exception as exc:  # noqa: BLE001
                current_item["transcript_status"] = "error"
                current_item["transcript_error"] = str(exc)[:300]
            else:
                if result.get("available"):
                    try:
                        save_saved_transcript(
                            title=(result.get("title") or "").strip() or item.get("title") or "YouTube transcript",
                            text=result.get("text") or "",
                            url=item.get("url") or "",
                            video_id=item.get("id") or None,
                            source="youtube",
                            folder=(item.get("folder") or ""),
                        )
                    except Exception as exc:  # noqa: BLE001
                        current_item["transcript_status"] = "error"
                        current_item["transcript_error"] = str(exc)[:300]
                    else:
                        current_item["transcript_status"] = "saved"
                        current_item["transcript_lines"] = len(result.get("segments") or [])
                        with _LOCK:
                            active = _BATCHES.get(batch_id)
                            if active is not None:
                                active["transcripts_saved_count"] = active.get("transcripts_saved_count", 0) + 1
                else:
                    current_item["transcript_status"] = "unavailable"
                    current_item["transcript_error"] = (result.get("reason") or "")[:300]
            with _LOCK:
                active = _BATCHES.get(batch_id)
                if active is not None:
                    active["transcripts_done_count"] = active.get("transcripts_done_count", 0) + 1

    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if not batch:
            return
        targets = [item for item in batch.get("tasks", []) if not item.get("task_id") or True]

    if targets:
        await asyncio.gather(*(fetch_one(item) for item in targets), return_exceptions=True)


async def _create_batch_from_entries(
    source_url: str,
    playlist_title: str,
    entries: list[dict],
    quality: str = "best",
    format_ext: str = "mp4",
    target_playlist_id: int | None = None,
    sequential: bool = True,
    fetch_transcripts: bool = False,
    transcript_folder: str = "",
    transcripts_only: bool = False,
) -> dict:
    """Create a batch from a resolved list of entries and enqueue it.

    Shared by playlist batches and multi-link batches.
    """
    if transcripts_only:
        fetch_transcripts = True  # transcripts-only implies fetching transcripts

    target_name = ""
    if target_playlist_id is not None:
        target_name = next(
            (item.get("name", "") for item in list_playlists() if item.get("id") == target_playlist_id),
            "",
        )

    batch_id = str(uuid.uuid4())
    tasks = []
    for index, entry in enumerate(entries, start=1):
        tasks.append({
            "index": index,
            "id": entry.get("id"),
            "title": entry.get("title") or f"Video {index}",
            "duration_label": entry.get("duration_label") or "",
            "url": entry["url"],
            "task_id": None,
            "status": "planned",
            "percent": "",
            "progress": None,
            "filename": None,
            "error": None,
            "added": False,
            "transcript_status": "pending" if fetch_transcripts else "skipped",
            "transcript_error": None,
            "transcript_lines": None,
            "folder": transcript_folder,
        })

    batch = {
        "id": batch_id,
        "url": source_url,
        "playlist_title": playlist_title or "Batch",
        "quality": str(quality).strip().lower(),
        "format": str(format_ext).strip().lower(),
        "target_playlist_id": target_playlist_id,
        "target_playlist_name": target_name,
        "sequential": bool(sequential),
        "fetch_transcripts": bool(fetch_transcripts),
        "transcript_folder": (transcript_folder or "").strip(),
        "transcripts_only": bool(transcripts_only),
        "created_at": time.time(),
        "tasks": tasks,
        "total_count": len(tasks),
        "done_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "added_count": 0,
        "enqueued_count": 0,
        "next_to_enqueue": 0,
        "transcripts_total": len(tasks) if fetch_transcripts else 0,
        "transcripts_done_count": 0,
        "transcripts_saved_count": 0,
        "phase": "running",
        "cancel_requested": False,
        "done": False,
        "supervisor_active": False,
    }

    with _LOCK:
        _BATCHES[batch_id] = batch

    # Queue the work (skip entirely for transcript-only batches).
    if not transcripts_only:
        if sequential:
            if tasks:
                await _enqueue_one(batch, tasks[0])
                with _LOCK:
                    _BATCHES[batch_id]["next_to_enqueue"] = 1
        else:
            for item in tasks:
                await _enqueue_one(batch, item)

    await _ensure_supervisor(batch_id)

    # Optionally fetch YouTube auto transcripts in parallel with the downloads
    # and save them into the persistent Transcript Saver.
    if fetch_transcripts and tasks:
        asyncio.create_task(_fetch_batch_transcripts(batch_id))

    return _BATCHES[batch_id]


async def create_batch(
    url: str,
    indices: list[int],
    quality: str = "best",
    format_ext: str = "mp4",
    target_playlist_id: int | None = None,
    sequential: bool = True,
    fetch_transcripts: bool = False,
    transcript_folder: str = "",
    transcripts_only: bool = False,
) -> dict:
    """Create a batch download from a single playlist URL and enqueue it.

    ``transcript_folder`` groups the auto-fetched transcripts inside the
    Transcript Saver (empty = "General", first-come-first-serve).

    ``transcripts_only`` fetches the selected videos' YouTube auto transcripts
    directly (no download, no Whisper) and saves them into the Transcript Saver.
    """
    from services.url_guard import validate_public_url

    safe_url = await validate_public_url(str(url))

    if target_playlist_id is not None and not any(
        item.get("id") == target_playlist_id for item in list_playlists()
    ):
        raise ValueError("Target playlist not found")

    data = await asyncio.to_thread(list_playlist_entries_sync, safe_url)
    if not data.get("is_playlist"):
        raise ValueError(
            "This link is not a playlist. Paste a playlist URL "
            "(e.g. https://www.youtube.com/playlist?list=...)."
        )

    entries_by_index = {entry["index"]: entry for entry in data.get("entries", [])}
    clean_indices = sorted({int(index) for index in indices if int(index) in entries_by_index})
    if not clean_indices:
        raise ValueError("No valid videos selected from the playlist")

    entries = [entries_by_index[index] for index in clean_indices]
    return await _create_batch_from_entries(
        safe_url,
        data.get("playlist_title") or "Playlist",
        entries,
        quality,
        format_ext,
        target_playlist_id,
        sequential,
        fetch_transcripts,
        transcript_folder,
        transcripts_only,
    )


async def create_multi_batch(
    urls: list[str],
    quality: str = "best",
    format_ext: str = "mp4",
    target_playlist_id: int | None = None,
    sequential: bool = True,
    fetch_transcripts: bool = False,
    transcript_folder: str = "",
    transcripts_only: bool = False,
) -> dict:
    """Create a batch from many individual URLs (any platform) in the order given.

    Each URL becomes one queued download (or one transcript fetch in
    transcript-only mode). YouTube ids are extracted so transcripts save under
    the right video; non-YouTube links still download fine.
    """
    from urllib.parse import parse_qs, urlparse

    from services.url_guard import validate_public_url

    if not urls:
        raise ValueError("No URLs provided")

    def extract_video_id(raw_url: str) -> str:
        raw_url = str(raw_url or "").strip()
        try:
            parsed = urlparse(raw_url)
        except Exception:
            return ""
        host = (parsed.hostname or "").lower()
        if host in {"youtu.be", "www.youtu.be"}:
            return (parsed.path or "").lstrip("/")[:11] or ""
        if "youtube.com" in host or "youtube-nocookie.com" in host:
            query_id = (parse_qs(parsed.query).get("v") or [""])[0]
            if query_id:
                return query_id[:11]
            segments = [segment for segment in parsed.path.split("/") if segment]
            if len(segments) >= 2 and segments[0] in {"shorts", "embed", "live", "v"}:
                return segments[1][:11]
        return ""

    safe_urls = []
    seen = set()
    for raw in urls:
        raw = str(raw or "").strip()
        if not raw:
            continue
        if raw in seen:
            continue
        try:
            safe = await validate_public_url(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid URL \"{raw}\": {exc}")
        seen.add(raw)
        safe_urls.append(safe)

    if not safe_urls:
        raise ValueError("No valid URLs provided")

    if target_playlist_id is not None and not any(
        item.get("id") == target_playlist_id for item in list_playlists()
    ):
        raise ValueError("Target playlist not found")

    entries = []
    for index, safe in enumerate(safe_urls, start=1):
        host = (urlparse(safe).hostname or "").replace("www.", "")
        entries.append({
            "index": index,
            "id": extract_video_id(safe) or None,
            "title": f"Link {index} ({host})",
            "duration_label": "",
            "url": safe,
        })

    return await _create_batch_from_entries(
        safe_urls[0],
        f"Multi-link batch ({len(safe_urls)} links)",
        entries,
        quality,
        format_ext,
        target_playlist_id,
        sequential,
        fetch_transcripts,
        transcript_folder,
        transcripts_only,
    )


async def create_local_transcript_batch(
    playlist_id: int,
    indices: list[int] | None = None,
    transcript_folder: str = "",
) -> dict:
    """Re-fetch YouTube transcripts for a SAVED playlist's videos.

    Uses the stored source links (file_links) — or reconstructs the YouTube URL
    from each file's video id — so transcripts can be fetched again without
    re-downloading anything. Runs as a transcript-only batch.
    """
    if playlist_id is None or not any(item.get("id") == playlist_id for item in list_playlists()):
        raise ValueError("Playlist not found")

    filenames = get_playlist_items(playlist_id)
    if not filenames:
        raise ValueError("Playlist is empty")

    if indices:
        clean_indices = sorted({int(i) for i in indices if 1 <= int(i) <= len(filenames)})
        if not clean_indices:
            raise ValueError("No valid items selected from the playlist")
        selected = [filenames[i - 1] for i in clean_indices]
    else:
        selected = filenames

    entries = []
    for idx, filename in enumerate(selected, start=1):
        filename = Path(filename).name
        video_id = extract_video_id(filename)
        link = get_file_link(filename) or {}
        url = link.get("url") or ""
        if not url and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        if not url:
            # No stored link and no video id -> can't fetch a transcript.
            continue
        # Backfill the link so future lookups are instant.
        if not link.get("url"):
            try:
                from services.database import save_file_link
                save_file_link(filename, url, video_id or "")
            except Exception:
                pass
        entries.append({
            "index": idx,
            "id": video_id or None,
            "title": clean_title(filename),
            "duration_label": "",
            "url": url,
        })

    if not entries:
        raise ValueError(
            "None of these playlist items have a stored link or a YouTube video id. "
            "Re-download the videos so links are stored, or paste the links in Multi-link."
        )

    playlist_name = next((p.get("name", "") for p in list_playlists() if p.get("id") == playlist_id), "Playlist")
    return await _create_batch_from_entries(
        "",
        f"{playlist_name} transcripts",
        entries,
        quality="best",
        format_ext="mp4",
        target_playlist_id=None,
        sequential=True,
        fetch_transcripts=True,
        transcript_folder=transcript_folder,
        transcripts_only=True,
    )


def cancel_batch(batch_id: str) -> bool:
    """Cancel every queued/running task in a batch (planned ones never start)."""
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if not batch:
            return False
        if batch.get("phase") in ("completed", "partial", "cancelled"):
            return True
        batch["cancel_requested"] = True
        batch["phase"] = "cancelling"
        for item in batch.get("tasks", []):
            if item.get("status") in ("planned", "pending", "queued"):
                item["status"] = "cancelled"
                item["error"] = "Cancelled by user"
            task_id = item.get("task_id")
            if task_id and download_tasks.get(task_id, {}).get("status") in ACTIVE_STATUSES:
                request_cancel(task_id)
    return True


async def retry_batch(batch_id: str) -> bool:
    """Re-queue the failed/cancelled items of a finished or partial batch."""
    with _LOCK:
        batch = _BATCHES.get(batch_id)
        if not batch:
            return False
        for item in batch.get("tasks", []):
            if item.get("status") in ("error", "cancelled"):
                item["status"] = "planned"
                item["task_id"] = None
                item["error"] = None
                item["percent"] = ""
                item["progress"] = None
                item["added"] = False
                item.pop("auto_add_error", None)
        first_open = next(
            (index for index, item in enumerate(batch["tasks"]) if item.get("status") != "completed"),
            0,
        )
        batch["next_to_enqueue"] = first_open
        batch["cancel_requested"] = False
        batch["phase"] = "running"
        batch["done"] = False
    await _ensure_supervisor(batch_id)
    return True
