import asyncio

from fastapi import APIRouter, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from models import DownloadRequest, SocialDownloadRequest
from services.downloader import (
    clear_downloads,
    delete_download,
    download_tasks,
    get_download_status,
    initiate_download,
    list_downloads,
    request_cancel,
    TERMINAL_STATUSES,
)
from pathlib import Path
from services.files import DOWNLOAD_DIR

router = APIRouter()


@router.post("/download")
async def download_video(request: DownloadRequest):
    task_id = await initiate_download(str(request.url), request.quality, request.format)
    return {"message": "Download started", "task_id": task_id}


@router.post("/social-download")
async def social_download_video(request: SocialDownloadRequest):
    task_id = await initiate_download(str(request.url), request.quality, request.format)
    return {"message": "Social download started", "task_id": task_id}


@router.get("/status/{task_id}")
async def download_status(task_id: str):
    return get_download_status(task_id)


@router.get("/downloads")
async def download_list():
    return {"downloads": list_downloads()}


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
    new_task_id = await initiate_download(url, quality, format_ext)
    return {
        'message': 'Download started',
        'task_id': new_task_id,
        'already_exists': False,
    }
