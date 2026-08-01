"""Video -> audio extraction for files already saved in the library.

Runs ffmpeg in a background thread and reports progress via an in-memory
job dict (mirrors the Whisper job pattern). The resulting audio file is
written to DOWNLOAD_DIR, so it automatically appears in the Library.
"""
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from services.files import DOWNLOAD_DIR

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

EXTRACT_AUDIO_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.RLock()

# format -> (extension, ffmpeg audio codec, lossy)
AUDIO_FORMATS = {
    "mp3": ("mp3", "libmp3lame", True),
    "m4a": ("m4a", "aac", True),
    "aac": ("aac", "aac", True),
    "ogg": ("ogg", "libvorbis", True),
    "opus": ("opus", "libopus", True),
    "wav": ("wav", "pcm_s16le", False),
    "flac": ("flac", "flac", False),
    "aiff": ("aiff", "pcm_s16be", False),
}

SUPPORTED_BITRATES = ("96k", "128k", "192k", "256k", "320k")
DEFAULT_BITRATE = "192k"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _probe_duration(path: Path) -> Optional[float]:
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _unique_output_path(source: Path, ext: str) -> Path:
    stem = source.stem or source.name
    candidate = DOWNLOAD_DIR / f"{stem} (audio).{ext}"
    index = 1
    while candidate.exists():
        candidate = DOWNLOAD_DIR / f"{stem} (audio) ({index}).{ext}"
        index += 1
    return candidate


def start_audio_extraction(source: Path, output_format: str, bitrate: str = DEFAULT_BITRATE) -> str:
    """Queue an ffmpeg audio extraction. Returns a job_id."""
    if not ffmpeg_available():
        raise ValueError("ffmpeg was not found on this system. Install ffmpeg and restart the backend.")

    fmt = (output_format or "").strip().lower().lstrip(".")
    if fmt not in AUDIO_FORMATS:
        raise ValueError(f"Unsupported audio format '{fmt}'. Supported: {', '.join(sorted(AUDIO_FORMATS))}")

    ext, codec, lossy = AUDIO_FORMATS[fmt]
    bitrate = (bitrate or "").strip().lower()
    if lossy and bitrate not in SUPPORTED_BITRATES:
        raise ValueError(f"Unsupported bitrate '{bitrate}'. Supported: {', '.join(SUPPORTED_BITRATES)}")

    if not source.exists():
        raise FileNotFoundError("Source file not found")

    out_path = _unique_output_path(source, ext)
    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        "job_id": job_id,
        "source": source.name,
        "output": out_path.name,
        "format": fmt,
        "bitrate": bitrate,
        "status": "queued",
        "progress": 0,
        "message": "Audio extraction queued",
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "source_duration": None,
        "elapsed_seconds": 0,
        "filename": None,
        "size_bytes": None,
        "error": None,
    }
    with _JOBS_LOCK:
        EXTRACT_AUDIO_JOBS[job_id] = job

    threading.Thread(
        target=_run_extraction,
        args=(job_id, source, out_path, codec, lossy, bitrate),
        daemon=True,
    ).start()
    return job_id


def _run_extraction(job_id: str, source: Path, out_path: Path, codec: str, lossy: bool, bitrate: str) -> None:
    job = EXTRACT_AUDIO_JOBS[job_id]
    started = time.time()
    job["started_at"] = started
    try:
        duration = _probe_duration(source)
        job["source_duration"] = duration
        job["status"] = "extracting"
        job["message"] = "Extracting audio..."

        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source), "-vn",
        ]
        if lossy:
            cmd += ["-acodec", codec, "-b:a", bitrate]
        else:
            cmd += ["-acodec", codec]
        cmd += ["-progress", "pipe:1", "-nostats", str(out_path)]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        error_lines: list[str] = []

        def _read_stderr() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                error_lines.append(line)

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        assert proc.stdout is not None
        for line in proc.stdout:
            stripped = line.strip()
            if stripped.startswith("out_time_ms="):
                try:
                    ms = int(stripped.split("=", 1)[1])
                except ValueError:
                    continue
                seconds = ms / 1_000_000
                if duration and duration > 0:
                    job["progress"] = min(99, round(seconds / duration * 100))
                    job["message"] = f"Extracting audio... {job['progress']}%"
                job["elapsed_seconds"] = round(time.time() - started)

        proc.wait()
        stderr_thread.join(timeout=5)

        if proc.returncode != 0 or not out_path.exists():
            err_text = "".join(error_lines[-8:]).strip() or "ffmpeg exited with an error"
            raise RuntimeError(err_text)

        job.update({
            "status": "completed",
            "progress": 100,
            "message": "Audio extracted",
            "filename": out_path.name,
            "size_bytes": out_path.stat().st_size,
            "elapsed_seconds": round(time.time() - started),
            "completed_at": time.time(),
        })
    except Exception as exc:
        job.update({
            "status": "error",
            "message": str(exc),
            "error": str(exc),
            "elapsed_seconds": round(time.time() - started),
        })
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def get_audio_extraction_job(job_id: str) -> Optional[dict]:
    job = EXTRACT_AUDIO_JOBS.get(job_id)
    if job is None:
        return None
    result = dict(job)
    if result.get("status") in ("queued", "extracting"):
        result["elapsed_seconds"] = round(time.time() - (result.get("started_at") or result.get("created_at") or time.time()))
    return result
