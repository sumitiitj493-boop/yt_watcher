import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.downloader import DOWNLOAD_DIR

router = APIRouter()

@router.get("/stream/{video_id}")
async def stream_video(video_id: str):
    file_path = os.path.join(DOWNLOAD_DIR, video_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(file_path, media_type="video/mp4")
