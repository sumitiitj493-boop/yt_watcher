import asyncio
import hashlib
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


def _safe_url_key(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:24]


def _transcript_text(segments: list[dict[str, Any]]) -> str:
    lines = []
    for segment in segments:
        text = _clean_caption_text(str(segment.get("text", "")))
        if text:
            lines.append(f"[{_seconds_to_display_time(float(segment.get('start', 0.0) or 0.0))}] {text}")
    return "\n".join(lines)


def _seconds_to_display_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds or 0.0))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


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


def _dedupe_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    for segment in segments:
        text = _clean_caption_text(str(segment.get("text", "")))
        if not text:
            continue

        start = round(float(segment.get("start", 0.0) or 0.0), 3)
        end = round(float(segment.get("end", start) or start), 3)

        if deduped:
            previous = deduped[-1]
            same_text = previous["text"] == text
            same_window = abs(previous["start"] - start) <= 0.5 and abs(previous["end"] - end) <= 0.5
            if same_text and same_window:
                previous["end"] = max(previous["end"], end)
                continue

        deduped.append({"start": start, "end": end, "text": text})
    return deduped


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
        if text:
            segments.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
            })
        index += 1
    return _dedupe_segments(segments)


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
            if isinstance(data.get("segments"), list):
                data["segments"] = _dedupe_segments(data["segments"])
                if data["segments"]:
                    data["available"] = True
            data["cached"] = True
            return data
        except Exception:
            pass
    if vtt_path.exists():
        segments = _dedupe_segments(parse_vtt(vtt_path.read_text(encoding="utf-8", errors="ignore")))
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
    segments = _dedupe_segments(segments)
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


def _save_transcript_by_key(key: str, source: str, segments: list[dict[str, Any]], extra: dict | None = None) -> dict:
    vtt_path = TRANSCRIPT_DIR / f"{key}.vtt"
    json_path = TRANSCRIPT_DIR / f"{key}.json"
    segments = _dedupe_segments(segments)
    _write_vtt_from_segments(vtt_path, segments)
    data = {
        "available": bool(segments),
        "source": source,
        "segments": segments,
        "text": _transcript_text(segments),
        "cached": True,
        "updated_at": time.time(),
    }
    if extra:
        data.update(extra)
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


def _find_cached_transcript_payload(key: str) -> dict | None:
    json_candidates = sorted(TRANSCRIPT_DIR.glob(f"{key}*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in json_candidates:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data.get("segments"), list):
            data["segments"] = _dedupe_segments(data["segments"])
            if data["segments"]:
                data["available"] = True
            data["cached"] = True
            return data

    subtitle_path = _find_downloaded_subtitle_file(key)
    if subtitle_path:
        segments = _dedupe_segments(parse_vtt(subtitle_path.read_text(encoding="utf-8", errors="ignore")))
        if segments:
            return {
                "available": True,
                "source": "cache",
                "segments": segments,
                "cached": True,
            }

    return None


def fetch_online_transcript_sync(filename: str, force: bool = False) -> dict:
    if not force:
        cached = _cached_transcript(filename)
        if cached:
            return cached

        key = _safe_key(filename)
        cached = _find_cached_transcript_payload(key)
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


def fetch_url_transcript_sync(url: str, force: bool = False) -> dict:
    url = str(url or "").strip()
    if not url:
        return {"available": False, "source": "url", "reason": "URL is required", "segments": [], "text": ""}

    fallback_key = f"url_{_safe_url_key(url)}"
    if not force:
        cached = _find_cached_transcript_payload(fallback_key)
        if cached and cached.get("available"):
            cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
            return cached

    outtmpl = (TRANSCRIPT_DIR / f"{fallback_key}.%(ext)s").as_posix()
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt/best",
        "subtitleslangs": ["en", "en.*"],
        "outtmpl": outtmpl,
        "noplaylist": True,
        "socket_timeout": 10,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = str(info.get("id") or "").strip()
            key = video_id or fallback_key
            if video_id and not force:
                cached = _find_cached_transcript_payload(key)
                if cached and cached.get("available"):
                    cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
                    return cached

            subtitles = info.get("subtitles") or {}
            automatic = info.get("automatic_captions") or {}
            if not subtitles and not automatic:
                return {"available": False, "source": "url", "reason": "No transcript for this video", "segments": [], "text": ""}

            ydl.download([url])
    except Exception as exc:
        return {"available": False, "source": "url", "reason": f"No transcript for this video: {exc}", "segments": [], "text": ""}

    subtitle_path = _find_downloaded_subtitle_file(key)
    if not subtitle_path:
        subtitle_path = _find_downloaded_subtitle_file(fallback_key)
    if not subtitle_path:
        return {"available": False, "source": "url", "reason": "No transcript for this video", "segments": [], "text": ""}

    segments = parse_vtt(subtitle_path.read_text(encoding="utf-8", errors="ignore"))
    if not segments:
        return {"available": False, "source": "url", "reason": "Transcript file was empty", "segments": [], "text": ""}

    title = (info.get("title") or "").strip() if isinstance(info, dict) else ""
    webpage_url = (info.get("webpage_url") or url) if isinstance(info, dict) else url
    return _save_transcript_by_key(key, "url", segments, {"title": title, "url": webpage_url})


async def fetch_url_transcript(url: str, force: bool = False) -> dict:
    return await asyncio.to_thread(fetch_url_transcript_sync, url, force)


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
    return _dedupe_segments(segments)


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
