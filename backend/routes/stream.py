from fastapi import APIRouter

router = APIRouter()

@router.get("/stream/{video_id}")
async def stream_video(video_id: str):
    return {"message": "Stream endpoint"}
