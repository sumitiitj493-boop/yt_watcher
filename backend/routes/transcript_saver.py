"""Transcript Saver endpoints.

Persistent storage for lecture transcripts. Transcripts saved here survive
video deletion, cache clears and page reloads — no need to re-paste a YouTube
link or re-fetch captions every time.

- Save a transcript manually (copy-paste) or fetch it from YouTube in one click.
- Clear individual entries, or clear all with a single call.
"""

from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException

from models import TranscriptSaverCreateRequest, TranscriptSaverFetchRequest, TranscriptSaverUpdateRequest
from services.database import (
    delete_all_saved_transcripts,
    delete_saved_transcript,
    get_saved_transcript,
    list_saved_transcripts,
    save_saved_transcript,
    update_saved_transcript,
)
from services.transcripts import fetch_url_transcript
from services.url_guard import validate_public_url

router = APIRouter()


def _extract_video_id(url: str) -> str:
    """Best-effort YouTube video id extraction (no network calls)."""
    url = str(url or "").strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
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


@router.get("/transcript-saver")
async def transcript_saver_list():
    return {"transcripts": list_saved_transcripts()}


@router.post("/transcript-saver")
async def transcript_saver_save(payload: TranscriptSaverCreateRequest):
    """Save a transcript from pasted text (or update an existing one)."""
    video_id = _extract_video_id(payload.url or "")
    try:
        saved = save_saved_transcript(
            title=payload.title,
            text=payload.text,
            url=(payload.url or "").strip(),
            video_id=video_id or None,
            source="manual",
            folder=payload.folder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"transcript": saved}


@router.post("/transcript-saver/fetch")
async def transcript_saver_fetch(request: TranscriptSaverFetchRequest):
    """Fetch the YouTube auto transcript for a URL and save it to the saver."""
    try:
        safe_url = await validate_public_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = await fetch_url_transcript(safe_url)
    if not result.get("available"):
        raise HTTPException(
            status_code=404,
            detail=result.get("reason") or "No transcript available for this video",
        )

    video_id = result.get("video_id") or _extract_video_id(safe_url) or None
    saved = save_saved_transcript(
        title=(result.get("title") or "").strip() or "YouTube transcript",
        text=result.get("text") or "",
        url=safe_url,
        video_id=video_id,
        source="youtube",
        folder=request.folder,
    )
    return {"transcript": saved}


@router.get("/transcript-saver/{transcript_id}")
async def transcript_saver_get(transcript_id: int):
    row = get_saved_transcript(transcript_id)
    if not row:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"transcript": row}


@router.patch("/transcript-saver/{transcript_id}")
async def transcript_saver_update(transcript_id: int, payload: TranscriptSaverUpdateRequest):
    try:
        row = update_saved_transcript(
            transcript_id,
            title=payload.title,
            text=payload.text,
            url=payload.url,
            folder=payload.folder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not row:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"transcript": row}


@router.delete("/transcript-saver/{transcript_id}")
async def transcript_saver_delete(transcript_id: int):
    if not delete_saved_transcript(transcript_id):
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"message": "Deleted"}


@router.delete("/transcript-saver")
async def transcript_saver_clear_all():
    deleted = delete_all_saved_transcripts()
    return {"message": "Cleared", "deleted": deleted}
