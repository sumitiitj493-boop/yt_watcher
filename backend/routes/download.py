from fastapi import APIRouter

router = APIRouter()

@router.post("/download")
async def download_video(url: str):
    return {"message": "Download endpoint"}

@router.get("/status/{video_id}")
async def download_status(video_id: str):
    return {"status": "Downloading...", "id": video_id}

@router.post("/cancel/{video_id}")
async def cancel_download(video_id: str):
    return {"message": "Cancelled"}
