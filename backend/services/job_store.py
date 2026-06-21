import json
from typing import Dict

from services.database import (
    clear_jobs_from_db,
    delete_job_from_db,
    load_jobs_from_db,
    save_jobs_to_db,
)
from services.files import DOWNLOAD_DIR

# Legacy path kept for one-time migration from older builds.
JOBS_PATH = DOWNLOAD_DIR / "jobs.json"


def _load_legacy_jobs() -> Dict[str, dict]:
    if not JOBS_PATH.exists():
        return {}
    try:
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_jobs() -> Dict[str, dict]:
    jobs = load_jobs_from_db()
    if jobs:
        return jobs

    legacy_jobs = _load_legacy_jobs()
    if legacy_jobs:
        save_jobs_to_db(legacy_jobs)
    return legacy_jobs


def save_jobs(jobs: Dict[str, dict]) -> None:
    save_jobs_to_db(jobs)


def delete_job(task_id: str) -> bool:
    return delete_job_from_db(task_id)


def clear_jobs() -> None:
    clear_jobs_from_db()
