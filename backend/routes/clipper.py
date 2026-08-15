"""Clip Studio endpoints — cut precise clips from downloaded videos."""

from fastapi import APIRouter, HTTPException

from models import ClipAnalyzeRequest, ClipCreateRequest
from services.clipper import analyze_file, get_clip_job, start_clip_job
from services.database import delete_clip_row, get_clip, list_clips
from services.files import resolve_download_path

router = APIRouter()


@router.get("/clips")
async def clips_list():
    return {"clips": list_clips()}


@router.post("/clips/analyze")
async def clip_analyze(request: ClipAnalyzeRequest):
    try:
        return analyze_file(request.filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/clips")
async def clip_create(request: ClipCreateRequest):
    try:
        safe_path = resolve_download_path(request.filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        job_id = start_clip_job(
            safe_path.name,
            request.start_seconds,
            request.end_seconds,
            request.title,
            request.collection,
            request.target_playlist_id,
            request.mode,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_id": job_id, "status": "queued", "source": safe_path.name}


@router.get("/clips/job/{job_id}")
async def clip_job_status(job_id: str):
    job = get_clip_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Clip job not found")
    return job


@router.get("/clips/{clip_id}")
async def clip_get(clip_id: int):
    row = get_clip(clip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"clip": row}


@router.delete("/clips/{clip_id}")
async def clip_delete(clip_id: int):
    row = get_clip(clip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")
    try:
        safe_path = resolve_download_path(row["filename"])
        safe_path.unlink(missing_ok=True)
    except Exception:
        pass
    delete_clip_row(clip_id)
    return {"message": "Deleted"}
