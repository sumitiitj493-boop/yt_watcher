import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket
from starlette.websockets import WebSocketDisconnect

from models import DownloadRequest, MetadataRequest, SocialDownloadRequest, TranscriptUrlRequest, WhisperLibraryRequest
from services.metadata import fetch_metadata
from services.transcripts import (
    UPLOAD_AUDIO_EXTENSIONS,
    fetch_url_transcript,
    get_url_transcription_job,
    save_uploaded_audio_file,
    start_library_whisper_transcription,
    start_uploaded_whisper_transcription,
    start_url_whisper_transcription,
)
from services.yt_dlp_options import (
    cookiefile_report,
    safe_cookie_report_for_response,
    social_cookies_browsers,
    social_cookies_file,
)
from services.youtube_access import check_youtube_access
from services.url_guard import validate_public_url
from services import instagram_images
from services.downloader import (
    clear_downloads,
    delete_download,
    download_tasks,
    get_download_status,
    initiate_download,
    list_downloads,
    request_cancel,
    retry_download_task,
    queue_summary,
    TERMINAL_STATUSES,
)
from pathlib import Path
from services.files import DOWNLOAD_DIR, resolve_download_path

router = APIRouter()


@router.post("/metadata")
async def video_metadata(request: MetadataRequest):
    try:
        safe_url = await validate_public_url(str(request.url))
        return await fetch_metadata(safe_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch metadata: {exc}")


@router.post("/youtube-access-check")
async def youtube_access_check(request: MetadataRequest):
    try:
        safe_url = await validate_public_url(str(request.url))
        return await check_youtube_access(safe_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to check YouTube access: {exc}")


@router.post("/transcript-from-url")
async def transcript_from_url(request: TranscriptUrlRequest):
    try:
        safe_url = await validate_public_url(str(request.url))
        return await fetch_url_transcript(safe_url, request.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch transcript: {exc}")


@router.post("/whisper-transcriptions")
async def whisper_transcription_create(request: TranscriptUrlRequest):
    try:
        safe_url = await validate_public_url(str(request.url))
        return await start_url_whisper_transcription(safe_url, request.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to start Whisper transcription: {exc}")


@router.post("/whisper-upload")
@router.post("/whisper-transcriptions/upload")
async def whisper_transcription_upload(
    file: UploadFile = File(...),
    force: bool = Form(default=False),
):
    try:
        audio_path, original_filename, key, size_bytes = await save_uploaded_audio_file(file)
        response = await start_uploaded_whisper_transcription(audio_path, original_filename, key, force)
        response["filename"] = original_filename
        response["size_bytes"] = size_bytes
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to upload audio for Whisper transcription: {exc}")
    finally:
        try:
            await file.close()
        except Exception:
            pass


@router.post("/whisper-library")
async def whisper_library_transcription(request: WhisperLibraryRequest):
    """Transcribe a file already saved in the library (e.g. a playlist item).

    No upload is needed — the backend reads the local file directly and runs
    the same Whisper pipeline used for uploads.
    """
    try:
        safe_path = resolve_download_path(request.filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if safe_path.suffix.lower().lstrip(".") not in UPLOAD_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type .{safe_path.suffix.lower().lstrip('.') or 'unknown'}",
        )

    size_bytes = safe_path.stat().st_size
    response = await start_library_whisper_transcription(safe_path, safe_path.name, request.force)
    response["filename"] = safe_path.name
    response["size_bytes"] = size_bytes
    return response


# --- Instagram / social cookies -------------------------------------------
# Instagram blocks downloads without login. Users can upload a Netscape-format
# cookies.txt exported from their logged-in browser, or rely on
# SOCIAL_COOKIES_BROWSER (cookiesfrombrowser) configured in the backend env.
SOCIAL_COOKIES_PROBE_URL = "https://www.instagram.com/"


@router.get("/social-cookies")
async def social_cookies_status():
    report = safe_cookie_report_for_response(cookiefile_report(SOCIAL_COOKIES_PROBE_URL))
    report["browsers_configured"] = social_cookies_browsers()
    return report


@router.post("/social-cookies")
async def social_cookies_upload(file: UploadFile = File(...)):
    filename = Path(getattr(file, "filename", "") or "").name
    if filename and not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Cookie file must be a .txt file (Netscape format).")

    target = social_cookies_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw = await file.read(2_000_000)
    finally:
        try:
            await file.close()
        except Exception:
            pass

    if not raw.strip():
        raise HTTPException(status_code=400, detail="Cookie file is empty.")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cookie file must be UTF-8 text (Netscape format).")

    first_content = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_content.startswith("{") or first_content.startswith("["):
        raise HTTPException(
            status_code=400,
            detail="This looks like a JSON cookie file. yt-dlp needs Netscape/Mozilla cookies.txt format. "
            "Export cookies as Netscape format (e.g. with the 'Get cookies.txt LOCALLY' extension).",
        )

    # Only keep Netscape rows; require at least one real cookie row.
    rows = [line for line in text.splitlines() if line.strip() and (line.lstrip().startswith("#") or "\t" in line)]
    valid_rows = [line for line in rows if "\t" in line and not line.lstrip().startswith("#")]
    if not valid_rows:
        raise HTTPException(
            status_code=400,
            detail="No Netscape cookie rows found. Export cookies in Netscape/Mozilla cookies.txt format.",
        )

    target.write_bytes(raw)
    report = safe_cookie_report_for_response(cookiefile_report(SOCIAL_COOKIES_PROBE_URL))
    return {"message": "Instagram cookies saved", **report}


@router.delete("/social-cookies")
async def social_cookies_delete():
    target = social_cookies_file()
    if target.exists():
        try:
            target.unlink()
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Unable to remove cookie file: {exc}")
    return {"message": "Instagram cookies removed"}


@router.post("/instagram-photos")
async def instagram_photos_download(request: MetadataRequest):
    """Download every photo in an Instagram post / carousel into the Library.

    Instagram posts are images; yt-dlp exposes them as thumbnails (not video
    formats), so the normal video download path can't get them. This endpoint
    grabs the best-resolution image for each carousel item directly.
    """
    try:
        safe_url = await validate_public_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        saved = await asyncio.to_thread(instagram_images.download_instagram_photos, safe_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to download photos: {exc}")

    if not saved:
        raise HTTPException(status_code=404, detail="No photos found in this post")

    return {"saved": saved, "count": len(saved)}


@router.get("/whisper-transcriptions/{job_id}")
async def whisper_transcription_status(job_id: str):
    job = get_url_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcription job not found")
    return job


@router.post("/download")
async def download_video(request: DownloadRequest):
    try:
        safe_url = await validate_public_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    task_id = await initiate_download(safe_url, request.quality, request.format)
    return {"message": "Download started", "task_id": task_id}


@router.post("/social-download")
async def social_download_video(request: SocialDownloadRequest):
    try:
        safe_url = await validate_public_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    task_id = await initiate_download(safe_url, request.quality, "best")
    return {"message": "Social download started", "task_id": task_id}


@router.get("/status/{task_id}")
async def download_status(task_id: str):
    return get_download_status(task_id)


@router.get("/downloads")
async def download_list():
    return {"downloads": list_downloads(), "queue": queue_summary()}


@router.get("/downloads/queue")
async def downloads_queue():
    return queue_summary()


@router.get("/downloads/location")
async def download_location():
    return {"path": str(DOWNLOAD_DIR)}


@router.get("/downloads/{task_id}")
async def download_detail(task_id: str):
    status = get_download_status(task_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    return status


@router.delete("/downloads/{task_id}")
async def download_delete(task_id: str):
    if not delete_download(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Deleted"}


@router.post("/downloads/clear")
async def downloads_clear():
    clear_downloads()
    return {"message": "Cleared"}


@router.websocket("/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            status = get_download_status(task_id)
            await websocket.send_json(status)
            if status.get("status") in ["completed", "error", "not_found", "cancelled"]:
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    finally:
        try:
            if websocket.application_state.name != "DISCONNECTED":
                await websocket.close()
        except Exception:
            pass


@router.post("/cancel/{task_id}")
async def cancel_download(task_id: str):
    if not request_cancel(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Cancel requested"}


@router.post("/retry/{task_id}")
async def retry_download(task_id: str):
    try:
        retried_task_id = await retry_download_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not retried_task_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Retry queued", "task_id": retried_task_id}


@router.post('/reprocess/{task_id}')
async def reprocess_from_history(task_id: str):
    """Re-process a history entry. If the file already exists on disk, skip re-download."""
    task = download_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    filename = task.get('filename')
    url = task.get('url')
    quality = task.get('quality', 'best')
    format_ext = task.get('format', 'mp4')

    if not url:
        raise HTTPException(status_code=400, detail='No URL stored for this task')

    # If file already exists on disk — no need to re-download
    if filename:
        file_path = DOWNLOAD_DIR / Path(filename).name
        if file_path.exists():
            return {
                'message': 'File already exists in library',
                'task_id': task_id,
                'already_exists': True,
                'filename': file_path.name,
            }

    # File missing — start a fresh download (initiate_download will dedupe)
    try:
        new_task_id = await initiate_download(url, quality, format_ext)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        'message': 'Download started',
        'task_id': new_task_id,
        'already_exists': False,
    }
