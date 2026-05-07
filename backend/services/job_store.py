import json
import os
from pathlib import Path
from typing import Dict

from services.files import DOWNLOAD_DIR

JOBS_PATH = DOWNLOAD_DIR / "jobs.json"


def load_jobs() -> Dict[str, dict]:
    if not JOBS_PATH.exists():
        return {}
    try:
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_jobs(jobs: Dict[str, dict]) -> None:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = JOBS_PATH.with_suffix(JOBS_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, JOBS_PATH)
