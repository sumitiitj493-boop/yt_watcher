import mimetypes
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.database import (
    add_playlist_item,
    add_playlist_items,
    create_note,
    create_playlist,
    delete_note,
    delete_playlist,
    get_default_playlist_id,
    get_playlist_items,
    list_notes,
    list_playlists,
    remove_playlist_item,
    rename_playlist,
    reorder_playlist,
    update_note,
)

import os
import gc
import stat
import sys
from services.files import DOWNLOAD_DIR, clean_title, extract_video_id, resolve_download_path
from services.stream_state import active_streams
from services.transcripts import fetch_online_transcript
from services.audio_extractor import (
    get_audio_extraction_job,
    start_audio_extraction,
)

router = APIRouter()

CACHE_TTL_SECONDS = 5
_files_cache = {"ts": 0.0, "data": []}
MEDIA_EXTENSIONS = {
    "mp4", "webm", "mkv", "mov", "avi",
    "mp3", "m4a", "aac", "ogg", "flac", "wav",
    "jpg", "jpeg", "png", "webp",
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


class PlaylistNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PlaylistAddItemRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)


class PlaylistAddItemsRequest(BaseModel):
    filenames: list[str] = Field(default_factory=list, max_length=1000)


class AudioExtractRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    format: str = Field(default="mp3", max_length=10)
    bitrate: str = Field(default="192k", max_length=10)


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


@router.get("/storage")
async def get_storage():
    """Return actual disk usage of the downloads folder in bytes."""
    if not DOWNLOAD_DIR.exists():
        return {"total_bytes": 0, "file_count": 0}
    total = 0
    count = 0
    for file_path in DOWNLOAD_DIR.iterdir():
        if file_path.is_file():
            total += file_path.stat().st_size
            count += 1
    return {"total_bytes": total, "file_count": count}


def _open_downloads_folder() -> None:
    """Open the downloads folder in the OS file explorer (server-side, so it
    works because this app is self-hosted on the user's machine)."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(DOWNLOAD_DIR))  # type: ignore[attr-defined]
        return
    import subprocess

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(DOWNLOAD_DIR)])


@router.post("/open-downloads-folder")
async def open_downloads_folder():
    try:
        _open_downloads_folder()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open downloads folder: {exc}")
    return {"message": "Opened"}


# --- Video -> audio extraction -------------------------------------------
@router.post("/extract-audio")
async def extract_audio(payload: AudioExtractRequest):
    try:
        safe_path = resolve_download_path(payload.filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if safe_path.suffix.lower().lstrip(".") not in MEDIA_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not a media file")

    try:
        job_id = start_audio_extraction(safe_path, payload.format, payload.bitrate)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "job_id": job_id,
        "status": "queued",
        "source": safe_path.name,
        "output_format": payload.format,
    }


@router.get("/extract-audio/{job_id}")
async def extract_audio_status(job_id: str):
    job = get_audio_extraction_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Extraction job not found")
    return job


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


# --- Playlist endpoints (multiple, named) ---------------------------------
def _playlist_exists(playlist_id: int) -> bool:
    return any(item["id"] == playlist_id for item in list_playlists())


def _default_playlist_id_or_create() -> int:
    """Return the default (oldest) playlist, creating one if none remain."""
    playlist_id = get_default_playlist_id()
    if playlist_id is None:
        try:
            create_playlist("My Playlist")
            playlist_id = get_default_playlist_id()
        except ValueError:
            playlist_id = get_default_playlist_id()
    if playlist_id is None:
        raise HTTPException(status_code=404, detail="No playlist available")
    return playlist_id


@router.get('/playlists')
async def playlists_list():
    return {"playlists": list_playlists()}


@router.post('/playlists')
async def playlists_create(payload: PlaylistNameRequest):
    try:
        playlist = create_playlist(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"playlist": playlist}


@router.patch('/playlists/{playlist_id}')
async def playlists_rename(playlist_id: int, payload: PlaylistNameRequest):
    try:
        playlist = rename_playlist(playlist_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"playlist": playlist}


@router.delete('/playlists/{playlist_id}')
async def playlists_delete(playlist_id: int):
    if not delete_playlist(playlist_id):
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"message": "Deleted"}


@router.get('/playlists/{playlist_id}/items')
async def playlists_items(playlist_id: int):
    if not _playlist_exists(playlist_id):
        raise HTTPException(status_code=404, detail="Playlist not found")
    return get_playlist_items(playlist_id)


@router.post('/playlists/{playlist_id}/items')
async def playlists_add_item(playlist_id: int, payload: PlaylistAddItemRequest):
    if not _playlist_exists(playlist_id):
        raise HTTPException(status_code=404, detail="Playlist not found")
    try:
        safe_path = resolve_download_path(payload.filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return add_playlist_item(playlist_id, safe_path.name)


@router.post('/playlists/{playlist_id}/items/batch')
async def playlists_add_items_batch(playlist_id: int, payload: PlaylistAddItemsRequest):
    if not _playlist_exists(playlist_id):
        raise HTTPException(status_code=404, detail="Playlist not found")
    safe_filenames: list[str] = []
    for filename in payload.filenames or []:
        try:
            safe_path = resolve_download_path(filename)
        except ValueError:
            continue
        if safe_path.exists():
            safe_filenames.append(safe_path.name)
    return add_playlist_items(playlist_id, safe_filenames)


@router.delete('/playlists/{playlist_id}/items/{filename}')
async def playlists_remove_item(playlist_id: int, filename: str):
    if not _playlist_exists(playlist_id):
        raise HTTPException(status_code=404, detail="Playlist not found")
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return remove_playlist_item(playlist_id, safe_path.name)


@router.post('/playlists/{playlist_id}/reorder')
async def playlists_reorder(playlist_id: int, order: list[str]):
    if not _playlist_exists(playlist_id):
        raise HTTPException(status_code=404, detail="Playlist not found")
    safe_order: list[str] = []
    for filename in order or []:
        try:
            safe_order.append(resolve_download_path(filename).name)
        except ValueError:
            continue
    return reorder_playlist(playlist_id, safe_order)


# --- Legacy single-playlist endpoints (kept for compatibility) ------------
# These operate on the default (oldest) playlist.
@router.get('/playlist')
async def playlist_get_legacy():
    playlist_id = _default_playlist_id_or_create()
    return get_playlist_items(playlist_id)


@router.post('/playlist/add/{filename}')
async def add_to_playlist_legacy(filename: str):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    playlist_id = _default_playlist_id_or_create()
    return add_playlist_item(playlist_id, safe_path.name)


@router.delete('/playlist/remove/{filename}')
async def remove_from_playlist_legacy(filename: str):
    try:
        safe_path = resolve_download_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    playlist_id = _default_playlist_id_or_create()
    return remove_playlist_item(playlist_id, safe_path.name)


@router.post('/playlist/reorder')
async def playlist_reorder_legacy(order: list[str]):
    playlist_id = _default_playlist_id_or_create()
    safe_order: list[str] = []
    for filename in order or []:
        try:
            safe_order.append(resolve_download_path(filename).name)
        except ValueError:
            continue
    return reorder_playlist(playlist_id, safe_order)
