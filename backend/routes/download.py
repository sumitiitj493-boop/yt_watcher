import asyncio
from fastapi import APIRouter, WebSocket, BackgroundTasks
from models import DownloadRequest
from services.downloader import initiate_download, get_download_status

router = APIRouter()

@router.post("/download")
async def download_video(request: DownloadRequest):
    task_id = await initiate_download(request.url, request.quality, request.format)
    return {"message": "Download started", "task_id": task_id}

@router.get("/status/{task_id}")
async def download_status(task_id: str):
    return get_download_status(task_id)

@router.websocket("/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            status = get_download_status(task_id)
            await websocket.send_json(status)
            if status.get("status") in ["completed", "error", "not_found"]:
                break
            await asyncio.sleep(1)
    finally:
        await websocket.close()

@router.post("/cancel/{task_id}")
async def cancel_download(task_id: str):
    return {"message": "Cancelled"}
