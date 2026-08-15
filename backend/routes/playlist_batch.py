"""Playlist batch download endpoints.

A single playlist link is enough: the backend resolves the video list,
enqueues each selected video as its own download task, and auto-saves
finished files into a user-chosen local playlist.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from models import (
    MultiDownloadRequest,
    PlaylistDownloadRequest,
    PlaylistEntriesRequest,
    PlaylistTranscriptsRequest,
)
from services.playlist_batch import (
    cancel_batch,
    create_batch,
    create_local_transcript_batch,
    create_multi_batch,
    get_batch,
    list_batches,
    list_playlist_entries_sync,
    retry_batch,
)
from services.url_guard import validate_public_url

router = APIRouter()


@router.post("/playlist/entries")
async def playlist_entries(request: PlaylistEntriesRequest):
    """List every video in a playlist (single URL, no per-video links needed)."""
    try:
        safe_url = await validate_public_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        return await asyncio.to_thread(list_playlist_entries_sync, safe_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read playlist: {exc}")


@router.post("/playlist/download")
async def playlist_download(request: PlaylistDownloadRequest):
    """Enqueue the selected range/specific videos as a batch download."""
    try:
        batch = await create_batch(
            str(request.url),
            request.indices,
            request.quality,
            request.format,
            request.target_playlist_id,
            request.sequential,
            request.fetch_transcripts,
            request.transcript_folder,
            request.transcripts_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "message": "Playlist batch queued",
        "batch_id": batch["id"],
        "task_count": batch["total_count"],
    }


@router.post("/multi-download")
async def multi_download(request: MultiDownloadRequest):
    """Queue many individual URLs (any platform) as one batch."""
    try:
        batch = await create_multi_batch(
            request.urls,
            request.quality,
            request.format,
            request.target_playlist_id,
            request.sequential,
            request.fetch_transcripts,
            request.transcript_folder,
            request.transcripts_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "message": "Multi-link batch queued",
        "batch_id": batch["id"],
        "task_count": batch["total_count"],
    }


@router.post("/playlist/{playlist_id}/transcripts")
async def playlist_local_transcripts(playlist_id: int, request: PlaylistTranscriptsRequest):
    """Re-fetch YouTube transcripts for a saved playlist (range/all) — no download."""
    try:
        batch = await create_local_transcript_batch(
            playlist_id,
            request.indices,
            request.transcript_folder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "message": "Transcript fetch queued",
        "batch_id": batch["id"],
        "task_count": batch["total_count"],
    }


@router.get("/playlist/batches")
async def playlist_batches_list():
    return {"batches": list_batches()}


@router.get("/playlist/batches/{batch_id}")
async def playlist_batch_status(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.post("/playlist/batches/{batch_id}/cancel")
async def playlist_batch_cancel(batch_id: str):
    if not cancel_batch(batch_id):
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Cancel requested"}


@router.post("/playlist/batches/{batch_id}/retry")
async def playlist_batch_retry(batch_id: str):
    if not await retry_batch(batch_id):
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Retry queued"}
