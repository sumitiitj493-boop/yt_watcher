import re
from pathlib import Path
from urllib.parse import unquote

DOWNLOAD_DIR = (Path(__file__).resolve().parent.parent / "downloads").resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
INSTAGRAM_TEMP_DIR = (DOWNLOAD_DIR / "_instagram_temp").resolve()

VIDEO_ID_RE = re.compile(r"\(([A-Za-z0-9_-]{11})\)")


def resolve_download_path(filename: str) -> Path:
    decoded = unquote(filename)
    candidate = (DOWNLOAD_DIR / decoded).resolve()
    if candidate != DOWNLOAD_DIR and DOWNLOAD_DIR in candidate.parents and candidate.exists():
        return candidate

    temp_candidate = (INSTAGRAM_TEMP_DIR / decoded).resolve()
    if temp_candidate.exists():
        return temp_candidate

    if candidate == DOWNLOAD_DIR or DOWNLOAD_DIR not in candidate.parents:
        raise ValueError("Invalid filename")
    raise ValueError("File not found")


def extract_video_id(filename: str) -> str | None:
    match = VIDEO_ID_RE.search(filename)
    return match.group(1) if match else None


def clean_title(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"\.[^.]+$", "", name)
    name = re.sub(r"\s*\([A-Za-z0-9_-]{11}\)\s*$", "", name)
    return name.strip()
