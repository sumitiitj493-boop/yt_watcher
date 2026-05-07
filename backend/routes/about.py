from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()


def _resolve_photo_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "sumit_image.png",
        Path(__file__).resolve().parents[2] / "sumit_image.png",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise HTTPException(status_code=404, detail="Profile image not found")


@router.get("/about/photo")
def get_about_photo():
    photo_path = _resolve_photo_path()
    return FileResponse(
        str(photo_path),
        media_type="image/png",
        filename=photo_path.name,
        headers={"Cache-Control": "public, max-age=86400"},
    )