import re
from pathlib import Path
from urllib.parse import unquote

DOWNLOAD_DIR = (Path(__file__).resolve().parent.parent / "downloads").resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
INSTAGRAM_TEMP_DIR = (DOWNLOAD_DIR / "_instagram_temp").resolve()

VIDEO_ID_RE = re.compile(r"\(([A-Za-z0-9_-]{11})\)")


def resolve_download_path(filename: str) -> Path:
    """Resolve a user-supplied filename to a real path inside the downloads area.

    Security: only paths inside DOWNLOAD_DIR (or the Instagram temp subfolder)
    are allowed; anything else raises ``ValueError``.

    Note: this returns the path even if the file does not exist yet — callers
    are responsible for checking existence and responding with 404. Raising on
    missing files would make every route return 400 instead of 404.
    """
    decoded = unquote(filename)
    candidate = (DOWNLOAD_DIR / decoded).resolve()

    # Guard against path traversal / absolute paths.
    if candidate == DOWNLOAD_DIR or DOWNLOAD_DIR not in candidate.parents:
        raise ValueError("Invalid filename")

    # Existing file in the main downloads folder.
    if candidate.exists():
        return candidate

    # Existing file in the Instagram temporary subfolder.
    temp_candidate = (INSTAGRAM_TEMP_DIR / decoded).resolve()
    if temp_candidate.parent == INSTAGRAM_TEMP_DIR and temp_candidate.exists():
        return temp_candidate

    return candidate


def extract_video_id(filename: str) -> str | None:
    match = VIDEO_ID_RE.search(filename)
    return match.group(1) if match else None


def clean_title(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"\.[^.]+$", "", name)
    name = re.sub(r"\s*\([A-Za-z0-9_-]{11}\)\s*$", "", name)
    return name.strip()
