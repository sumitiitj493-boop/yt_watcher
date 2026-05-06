import os
from fastapi import APIRouter
from services.downloader import DOWNLOAD_DIR

router = APIRouter()

@router.get("/files")
async def list_files():
    if not os.path.exists(DOWNLOAD_DIR):
        return {"files": []}
    files = os.listdir(DOWNLOAD_DIR)
    file_list = []
    for f in files:
        full_path = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(full_path):
            file_info = {
                "filename": f,
                "size": os.path.getsize(full_path)
            }
            file_list.append(file_info)
    return {"files": file_list}

@router.delete("/delete/{filename}")
async def delete_file(filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"message": "Deleted"}
    return {"error": "File not found"}

@router.get("/search")
async def search_files(query: str):
    if not os.path.exists(DOWNLOAD_DIR):
        return {"results": []}
    files = os.listdir(DOWNLOAD_DIR)
    results = [f for f in files if query.lower() in f.lower()]
    return {"results": results}
