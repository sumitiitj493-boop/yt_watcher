import mimetypes
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import os
import gc
import stat
from services.files import DOWNLOAD_DIR, clean_title, extract_video_id, resolve_download_path
from services.stream_state import active_streams

router = APIRouter()

CACHE_TTL_SECONDS = 5
_files_cache = {"ts": 0.0, "data": []}
MEDIA_EXTENSIONS = {
    "mp4", "webm", "mkv", "mov", "avi",
    "mp3", "m4a", "aac", "ogg", "flac", "wav",
}


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
        # Try to force writable and remove as a fallback on Windows
        try:
            os.chmod(str(file_path), stat.S_IWRITE)
            file_path.unlink()
        except PermissionError:
            raise HTTPException(
                status_code=409,
                detail={"message": "File is currently in use. Stop playback and try again.", "filename": filename},
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


# --- Playlist endpoints -------------------------------------------------
PLAYLIST_FILENAME = DOWNLOAD_DIR / 'playlist.json'

def _load_playlist() -> list[str]:
    try:
        if PLAYLIST_FILENAME.exists():
            import json
            return json.loads(PLAYLIST_FILENAME.read_text(encoding='utf-8'))
    except Exception:
        pass
    return []

def _save_playlist(pl: list[str]) -> None:
    try:
        import json
        PLAYLIST_FILENAME.write_text(json.dumps(pl, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


@router.get('/playlist')
async def get_playlist():
    return _load_playlist()


@router.post('/playlist/add/{filename}')
async def add_to_playlist(filename: str):
    pl = _load_playlist()
    if filename not in pl:
        pl.append(filename)
        _save_playlist(pl)
    return pl


@router.delete('/playlist/remove/{filename}')
async def remove_from_playlist(filename: str):
    pl = _load_playlist()
    pl = [f for f in pl if f != filename]
    _save_playlist(pl)
    return pl


@router.post('/playlist/reorder')
async def reorder_playlist(order: list[str]):
    _save_playlist(order or [])
    return order or []
