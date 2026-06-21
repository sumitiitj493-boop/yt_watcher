import mimetypes
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.database import (
    add_playlist_item,
    create_note,
    delete_note,
    get_playlist,
    list_notes,
    remove_playlist_item,
    reorder_playlist,
    update_note,
)

import os
import gc
import stat
from services.files import DOWNLOAD_DIR, clean_title, extract_video_id, resolve_download_path
from services.stream_state import active_streams
from services.transcripts import fetch_online_transcript

router = APIRouter()

CACHE_TTL_SECONDS = 5
_files_cache = {"ts": 0.0, "data": []}
MEDIA_EXTENSIONS = {
    "mp4", "webm", "mkv", "mov", "avi",
    "mp3", "m4a", "aac", "ogg", "flac", "wav",
}


class NoteCreateRequest(BaseModel):
    time_seconds: int = Field(default=0, ge=0)
    content: str = Field(min_length=1, max_length=5000)
    tag: str = Field(default="", max_length=80)
    color: str = Field(default="", max_length=40)


class NoteUpdateRequest(BaseModel):
    time_seconds: int | None = Field(default=None, ge=0)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    tag: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=40)


def _get_cached_files() -> list[dict]:
    now = time.time()
    if now - _files_cache["ts"] <= CACHE_TTL_SECONDS:
        return _files_cache["data"]

    # Patterns to exclude from library
    EXCLUDE_SUFFIXES = {".part", ".temp", ".ytdl", ".json"}
    EXCLUDE_PATTERNS = [".f399.", ".f137.", ".f248.", ".f251.", ".temp."]

    file_list = []
    for file_path in DOWNLOAD_DIR.iterdir():
        # Skip non-files
        if not file_path.is_file():
            continue
        # Skip partial/temp/json files
        if file_path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        # Skip intermediate stream files like .f399.mp4
        if any(p in file_path.name for p in EXCLUDE_PATTERNS):
            continue
        # Skip non-media files
        if file_path.suffix.lower().lstrip(".") not in MEDIA_EXTENSIONS:
            continue
        # Skip very small files (likely corrupted/partial) under 100KB
        if file_path.stat().st_size < 102400:
            continue

        stat_info = file_path.stat()
        file_list.append({
            "filename": file_path.name,
            "title": clean_title(file_path.name),
            "video_id": extract_video_id(file_path.name),
            "size": stat_info.st_size,
            "created_at": stat_info.st_mtime,
            "ext": file_path.suffix.lower().lstrip("."),
        })

    file_list = sorted(
        file_list,
        key=lambda item: item.get("created_at", 0),
        reverse=True,
    )
    _files_cache["ts"] = now
    _files_cache["data"] = file_list
    return file_list


@router.get("/files")
async def list_files():
    if not DOWNLOAD_DIR.exists():
        return {"files": []}
    return {"files": _get_cached_files()}


@router.delete("/delete/{filename}")
async def delete_file(filename: str):
    try:
        file_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Attempt to release any known active streams for this file, then delete.
    active_streams.discard(filename)
    gc.collect()
    try:
        file_path.unlink()
    except PermissionError:
        try:
            os.chmod(str(file_path), stat.S_IWRITE)
            file_path.unlink()
        except Exception:
            import subprocess

            subprocess.run(["cmd", "/c", "del", "/f", str(file_path)], capture_output=True)
            if file_path.exists():
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Stop playback first then try again.", "filename": filename},
                )
    _files_cache["ts"] = 0.0
    return {"message": "Deleted"}


@router.get("/search")
async def search_files(query: str):
    if not DOWNLOAD_DIR.exists():
        return {"results": []}

    normalized = query.lower()
    results = [
        item
        for item in _get_cached_files()
        if normalized in item["filename"].lower() or normalized in item["title"].lower()
    ]
    return {"results": results}


@router.get("/transcript/{filename}")
async def get_transcript(filename: str):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return await fetch_online_transcript(safe_path.name)


@router.get("/files/download/{filename}")
async def download_file(filename: str):
    try:
        file_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type, _ = mimetypes.guess_type(file_path.name)
    return FileResponse(
        str(file_path),
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
    )


@router.post("/files/clear")
async def clear_files():
    if not DOWNLOAD_DIR.exists():
        return {"deleted": 0}

    failed: list[str] = []
    deleted = 0
    for file_path in list(DOWNLOAD_DIR.iterdir()):
        if not file_path.is_file():
            continue

        EXCLUDE_SUFFIXES = {".part", ".temp", ".ytdl", ".json"}
        EXCLUDE_PATTERNS = [".f399.", ".f137.", ".f248.", ".f251.", ".temp."]

        # Skip partial/temp/json files
        if file_path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        # Skip intermediate stream files like .f399.mp4
        if any(p in file_path.name for p in EXCLUDE_PATTERNS):
            continue
        if file_path.suffix.lower().lstrip('.') not in MEDIA_EXTENSIONS:
            continue
        # Try to release any active stream references and then remove
        active_streams.discard(file_path.name)
        gc.collect()
        try:
            file_path.unlink()
            deleted += 1
        except PermissionError:
            try:
                os.chmod(str(file_path), stat.S_IWRITE)
                file_path.unlink()
                deleted += 1
            except Exception:
                failed.append(file_path.name)

    _files_cache["ts"] = 0.0
    # Return a summary so the client can handle partial failures (e.g., files in use on Windows).
    return {"deleted": deleted, "failed": failed}


# --- Persistent study notes --------------------------------------------
@router.get('/files/{filename}/notes')
async def file_notes(filename: str):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return {"notes": list_notes(safe_path.name)}


@router.post('/files/{filename}/notes')
async def add_file_note(filename: str, payload: NoteCreateRequest):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    note = create_note(
        safe_path.name,
        payload.time_seconds,
        payload.content,
        payload.tag,
        payload.color,
    )
    return {"note": note}


@router.patch('/notes/{note_id}')
async def patch_note(note_id: int, payload: NoteUpdateRequest):
    note = update_note(
        note_id,
        content=payload.content,
        time_seconds=payload.time_seconds,
        tag=payload.tag,
        color=payload.color,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note}


@router.delete('/notes/{note_id}')
async def remove_note(note_id: int):
    if not delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Deleted"}


# --- Playlist endpoints -------------------------------------------------
@router.get('/playlist')
async def playlist_get():
    return get_playlist()


@router.post('/playlist/add/{filename}')
async def add_to_playlist(filename: str):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return add_playlist_item(safe_path.name)


@router.delete('/playlist/remove/{filename}')
async def remove_from_playlist(filename: str):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return remove_playlist_item(safe_path.name)


@router.post('/playlist/reorder')
async def playlist_reorder(order: list[str]):
    safe_order: list[str] = []
    for filename in order or []:
        try:
            safe_order.append(resolve_download_path(filename).name)
        except ValueError:
            continue
    return reorder_playlist(safe_order)
