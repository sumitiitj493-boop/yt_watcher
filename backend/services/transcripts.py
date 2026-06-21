import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from services.files import DOWNLOAD_DIR, extract_video_id, resolve_download_path

TRANSCRIPT_DIR = DOWNLOAD_DIR / "transcripts"
TRANSCRIPT_AUDIO_DIR = DOWNLOAD_DIR / "transcript_audio"
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MANUAL_TRANSCRIPT_JOBS: dict[str, dict] = {}

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _safe_key(filename: str) -> str:
    video_id = extract_video_id(filename)
    if video_id:
        return video_id
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).stem)[:140]


def _seconds_to_vtt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds or 0.0))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def _vtt_time_to_seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def _clean_caption_text(text: str) -> str:
    text = TAG_RE.sub("", text or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_vtt(vtt_text: str) -> list[dict[str, Any]]:
    lines = vtt_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = TIMESTAMP_RE.search(line)
        if not match:
            index += 1
            continue
        start = _vtt_time_to_seconds(match.group("start"))
        end = _vtt_time_to_seconds(match.group("end"))
        index += 1
        text_lines = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1
        text = _clean_caption_text(" ".join(text_lines))
        if text and (not segments or segments[-1].get("text") != text or abs(segments[-1].get("start", 0) - start) > 0.5):
            segments.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
            })
        index += 1
    return segments


def _write_vtt_from_segments(path: Path, segments: list[dict[str, Any]]) -> None:
    lines = ["WEBVTT", ""]
    for idx, segment in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_seconds_to_vtt_time(segment['start'])} --> {_seconds_to_vtt_time(segment['end'])}")
        lines.append(str(segment["text"]).strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _cached_transcript(filename: str) -> dict | None:
    key = _safe_key(filename)
    json_path = TRANSCRIPT_DIR / f"{key}.json"
    vtt_path = TRANSCRIPT_DIR / f"{key}.vtt"
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data["cached"] = True
            return data
        except Exception:
            pass
    if vtt_path.exists():
        segments = parse_vtt(vtt_path.read_text(encoding="utf-8", errors="ignore"))
        return {
            "available": bool(segments),
            "source": "cache",
            "segments": segments,
            "cached": True,
        }
    return None


def _save_transcript(filename: str, source: str, segments: list[dict[str, Any]]) -> dict:
    key = _safe_key(filename)
    vtt_path = TRANSCRIPT_DIR / f"{key}.vtt"
    json_path = TRANSCRIPT_DIR / f"{key}.json"
    _write_vtt_from_segments(vtt_path, segments)
    data = {
        "available": bool(segments),
        "source": source,
        "segments": segments,
        "cached": True,
        "updated_at": time.time(),
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _youtube_url_for_filename(filename: str) -> str | None:
    video_id = extract_video_id(filename)
    if not video_id:
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def _find_downloaded_subtitle_file(key: str) -> Path | None:
    candidates = sorted(TRANSCRIPT_DIR.glob(f"{key}*.vtt"), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def fetch_online_transcript_sync(filename: str, force: bool = False) -> dict:
    if not force:
        cached = _cached_transcript(filename)
        if cached:
            return cached

    url = _youtube_url_for_filename(filename)
    if not url:
        return {"available": False, "source": "online", "reason": "No YouTube video id found for this file", "segments": []}

    key = _safe_key(filename)
    outtmpl = (TRANSCRIPT_DIR / f"{key}.%(ext)s").as_posix()
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt/best",
        "subtitleslangs": ["en", "en.*"],
        "outtmpl": outtmpl,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subtitles = info.get("subtitles") or {}
            automatic = info.get("automatic_captions") or {}
            if not subtitles and not automatic:
                return {"available": False, "source": "online", "reason": "No transcript for this video", "segments": []}
            ydl.download([url])
    except Exception as exc:
        return {"available": False, "source": "online", "reason": f"No transcript for this video: {exc}", "segments": []}

    subtitle_path = _find_downloaded_subtitle_file(key)
    if not subtitle_path:
        return {"available": False, "source": "online", "reason": "No transcript for this video", "segments": []}

    segments = parse_vtt(subtitle_path.read_text(encoding="utf-8", errors="ignore"))
    if not segments:
        return {"available": False, "source": "online", "reason": "Transcript file was empty", "segments": []}
    return _save_transcript(filename, "online", segments)


async def fetch_online_transcript(filename: str, force: bool = False) -> dict:
    return await asyncio.to_thread(fetch_online_transcript_sync, filename, force)


def _download_tiny_audio_sync(filename: str) -> Path:
    key = _safe_key(filename)
    audio_path = TRANSCRIPT_AUDIO_DIR / f"{key}.mp3"
    if audio_path.exists() and audio_path.stat().st_size > 1024:
        return audio_path

    url = _youtube_url_for_filename(filename)
    if url:
        ydl_opts = {
            "format": "worstaudio[abr<=64]/worstaudio/bestaudio[abr<=64]/bestaudio",
            "outtmpl": (TRANSCRIPT_AUDIO_DIR / f"{key}.%(ext)s").as_posix(),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "48",
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if audio_path.exists():
            return audio_path

    # Fallback for non-YouTube/local files: extract tiny audio from existing file.
    file_path = resolve_download_path(filename)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to extract audio for transcription")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(file_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "48k",
            str(audio_path),
        ],
        check=True,
    )
    return audio_path


def _transcribe_with_faster_whisper(audio_path: Path) -> list[dict[str, Any]]:
    from faster_whisper import WhisperModel  # type: ignore

    model_name = os.environ.get("WHISPER_MODEL", "base")
    device = os.environ.get("WHISPER_DEVICE", "auto")
    compute_type = os.environ.get("WHISPER_COMPUTE_TYPE", "default")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments_iter, _info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
    )
    segments = []
    for segment in segments_iter:
        text = _clean_caption_text(segment.text)
        if text:
            segments.append({"start": round(float(segment.start), 3), "end": round(float(segment.end), 3), "text": text})
    return segments


def _transcribe_with_whisper_cli(audio_path: Path, key: str) -> list[dict[str, Any]]:
    whisper = shutil.which("whisper")
    if not whisper:
        raise RuntimeError("Neither faster_whisper Python package nor whisper CLI is available")
    model_name = os.environ.get("WHISPER_MODEL", "base")
    subprocess.run(
        [
            whisper,
            str(audio_path),
            "--model",
            model_name,
            "--output_format",
            "vtt",
            "--output_dir",
            str(TRANSCRIPT_DIR),
        ],
        check=True,
    )
    produced = TRANSCRIPT_DIR / f"{audio_path.stem}.vtt"
    if not produced.exists():
        produced = TRANSCRIPT_DIR / f"{key}.vtt"
    if not produced.exists():
        raise RuntimeError("Whisper finished but no VTT transcript was produced")
    return parse_vtt(produced.read_text(encoding="utf-8", errors="ignore"))


def manual_transcribe_sync(filename: str, job_id: str) -> dict:
    key = _safe_key(filename)
    job = MANUAL_TRANSCRIPT_JOBS[job_id]
    try:
        job.update({"status": "downloading_audio", "progress": 12, "message": "Downloading tiny audio for transcription..."})
        audio_path = _download_tiny_audio_sync(filename)
        job.update({
            "status": "transcribing",
            "progress": 35,
            "message": f"Transcribing from tiny audio ({round(audio_path.stat().st_size / 1024 / 1024, 2)} MB)...",
        })
        try:
            segments = _transcribe_with_faster_whisper(audio_path)
        except Exception:
            segments = _transcribe_with_whisper_cli(audio_path, key)
        data = _save_transcript(filename, "manual", segments)
        job.update({"status": "completed", "progress": 100, "message": "Transcript ready", "result": data})
        return data
    except Exception as exc:
        job.update({"status": "error", "progress": 100, "message": str(exc), "error": str(exc)})
        raise


async def start_manual_transcription(filename: str) -> dict:
    # Validate path early.
    safe_path = resolve_download_path(filename)
    if not safe_path.exists():
        raise FileNotFoundError("Video file not found")

    existing = _cached_transcript(safe_path.name)
    if existing and existing.get("available"):
        return {"already_done": True, "job_id": None, "result": existing}

    job_id = str(uuid.uuid4())
    MANUAL_TRANSCRIPT_JOBS[job_id] = {
        "job_id": job_id,
        "filename": safe_path.name,
        "status": "queued",
        "progress": 0,
        "message": "Manual transcription queued",
        "created_at": time.time(),
    }

    async def runner():
        await asyncio.to_thread(manual_transcribe_sync, safe_path.name, job_id)

    asyncio.create_task(runner())
    return {"already_done": False, "job_id": job_id, "status": "queued"}


def get_manual_transcription_job(job_id: str) -> dict | None:
    return MANUAL_TRANSCRIPT_JOBS.get(job_id)
