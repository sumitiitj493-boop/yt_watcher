from fastapi import APIRouter

router = APIRouter()

@router.get("/files")
async def list_files():
    return {"files": []}

@router.delete("/delete/{video_id}")
async def delete_file(video_id: str):
    return {"message": "Deleted"}

@router.get("/search")
async def search_files(query: str):
    return {"results": []}
