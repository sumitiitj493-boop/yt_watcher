import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

import yt_dlp

from services.files import DOWNLOAD_DIR, extract_video_id, resolve_download_path
from services.yt_dlp_options import PUBLIC_HTTP_HEADERS, add_generic_impersonation, apply_cookiefile

TRANSCRIPT_DIR = DOWNLOAD_DIR / "transcripts"
TRANSCRIPT_AUDIO_DIR = DOWNLOAD_DIR / "transcript_audio"
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MANUAL_TRANSCRIPT_JOBS: dict[str, dict] = {}
URL_TRANSCRIPT_JOBS: dict[str, dict] = {}
WHISPER_MODEL_CACHE: dict[tuple[str, str, str, int, int], Any] = {}
WHISPER_MODEL_LOCK = RLock()
WHISPER_TRANSCRIBE_LOCK = RLock()

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[A-Za-z0-9']+")

CAPTION_LANGUAGE_PRIORITY = (
    "en",
    "en-us",
    "en-gb",
    "en.*",
)
CAPTION_EXTENSION_PRIORITY = (
    "vtt",
    "srv3",
    "ttml",
    "json3",
)
LANGUAGE_NAMES = {
    "en": "English",
    "en-us": "English (US)",
    "en-gb": "English (UK)",
}


def _env_int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, "") or default)
    except ValueError:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _default_whisper_threads() -> int:
    # Leave a couple of threads free so the API and OS stay responsive.
    return max(1, min((os.cpu_count() or 4) - 2, 10))


def _whisper_compute_type(device: str) -> str:
    configured = os.environ.get("WHISPER_COMPUTE_TYPE")
    if configured:
        return configured
    if device.strip().lower().startswith("cuda"):
        return "float16"
    return "int8"


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


def _duration_label(seconds: float | int | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _job_elapsed(job: dict) -> int:
    return max(0, int(time.time() - float(job.get("started_at") or job.get("created_at") or time.time())))


def _update_job_timing(job: dict, message: str | None = None, eta_seconds: int | None = None) -> None:
    elapsed_seconds = _job_elapsed(job)
    job["elapsed_seconds"] = elapsed_seconds
    if eta_seconds is not None:
        job["eta_seconds"] = max(0, int(eta_seconds))
    if message:
        eta = job.get("eta_seconds")
        suffix = f" Elapsed {_duration_label(elapsed_seconds)}"
        if eta is not None:
            suffix += f", ETA {_duration_label(int(eta))}"
        job["message"] = f"{message}.{suffix}."


def _terminal_transcription_label(job: dict | None, audio_path: Path) -> str:
    if job is None:
        return audio_path.name
    return str(job.get("filename") or job.get("url") or audio_path.name)


def _log_transcription_progress(job: dict | None, audio_path: Path, percent: float, *, force: bool = False) -> None:
    if job is None:
        return
    bucket = max(0, min(100, int(percent // 5) * 5))
    previous_bucket = int(job.get("_terminal_transcription_bucket") or 0)
    if not force and (bucket < 5 or bucket <= previous_bucket):
        return
    if force and bucket <= previous_bucket:
        return
    if force and previous_bucket == 0:
        milestones = [bucket]
    else:
        milestones = range(max(5, previous_bucket + 5), bucket + 1, 5)
    for next_bucket in milestones:
        print(
            f"[transcription] {next_bucket}% done - {_terminal_transcription_label(job, audio_path)}",
            flush=True,
        )
    job["_terminal_transcription_bucket"] = bucket


class _TerminalWhisperProgress:
    def __init__(self, total: float | int | None = None, *args: Any, job: dict | None = None, audio_path: Path | None = None, **kwargs: Any):
        self.total = float(total or 0.0)
        self.current = 0.0
        self.job = job
        self.audio_path = audio_path

    def update(self, amount: float | int = 1) -> None:
        self.current += float(amount or 0.0)
        if self.job is not None and self.audio_path is not None and self.total > 0:
            _log_transcription_progress(self.job, self.audio_path, (self.current / self.total) * 100)

    def close(self) -> None:
        pass


@contextmanager
def _capture_faster_whisper_progress(job: dict | None, audio_path: Path) -> Iterator[None]:
    if job is None:
        yield
        return
    import faster_whisper.transcribe as faster_whisper_transcribe  # type: ignore

    original_tqdm = faster_whisper_transcribe.tqdm

    def terminal_tqdm(*args: Any, **kwargs: Any) -> _TerminalWhisperProgress:
        return _TerminalWhisperProgress(*args, job=job, audio_path=audio_path, **kwargs)

    faster_whisper_transcribe.tqdm = terminal_tqdm
    try:
        yield
    finally:
        faster_whisper_transcribe.tqdm = original_tqdm


def _get_faster_whisper_model() -> tuple[Any, dict[str, Any]]:
    from faster_whisper import WhisperModel  # type: ignore

    model_name = os.environ.get("WHISPER_MODEL", "base")
    device = os.environ.get("WHISPER_DEVICE", "auto")
    compute_type = _whisper_compute_type(device)
    cpu_threads = _env_int("WHISPER_CPU_THREADS", _default_whisper_threads(), 1, os.cpu_count() or 16)
    num_workers = _env_int("WHISPER_NUM_WORKERS", 1, 1, 4)
    cache_key = (model_name, device, compute_type, cpu_threads, num_workers)

    with WHISPER_MODEL_LOCK:
        model = WHISPER_MODEL_CACHE.get(cache_key)
        if model is None:
            print(
                "[transcription] loading faster-whisper model "
                f"{model_name} ({device}, {compute_type}, cpu_threads={cpu_threads}, workers={num_workers})",
                flush=True,
            )
            model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                num_workers=num_workers,
            )
            WHISPER_MODEL_CACHE.clear()
            WHISPER_MODEL_CACHE[cache_key] = model
        return model, {
            "model": model_name,
            "device": device,
            "compute_type": compute_type,
            "cpu_threads": cpu_threads,
            "num_workers": num_workers,
        }


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


def _word_tokens_with_spans(text: str) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    for match in WORD_RE.finditer(text or ""):
        normalized = re.sub(r"[^a-z0-9]+", "", match.group(0).lower())
        if normalized:
            tokens.append((normalized, match.start(), match.end()))
    return tokens


def _remove_repeated_prefix(previous_text: str, current_text: str) -> str:
    previous_tokens = _word_tokens_with_spans(previous_text)
    current_tokens = _word_tokens_with_spans(current_text)
    if not previous_tokens or not current_tokens:
        return current_text

    previous_words = [token[0] for token in previous_tokens]
    current_words = [token[0] for token in current_tokens]

    if len(current_words) <= len(previous_words):
        for start_index in range(0, len(previous_words) - len(current_words) + 1):
            if previous_words[start_index:start_index + len(current_words)] == current_words:
                return ""

    max_overlap = min(len(previous_words), len(current_words), 40)
    best_overlap = 0
    for size in range(max_overlap, 0, -1):
        if previous_words[-size:] == current_words[:size]:
            best_overlap = size
            break

    if best_overlap < 3:
        return current_text
    if best_overlap >= len(current_tokens):
        return ""

    return current_text[current_tokens[best_overlap][1]:].strip()


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

            is_rolling_window = start <= previous["end"] + 8 or start <= previous["start"] + 15
            if is_rolling_window:
                trimmed_text = _remove_repeated_prefix(previous["text"], text)
                if not trimmed_text:
                    previous["end"] = max(previous["end"], end)
                    continue
                text = trimmed_text

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


def _parse_json3(json_text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(json_text)
    except Exception:
        return []

    segments: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        text_parts = []
        for seg in event.get("segs") or []:
            text = _clean_caption_text(str(seg.get("utf8") or ""))
            if text:
                text_parts.append(text)

        text = _clean_caption_text(" ".join(text_parts))
        if not text:
            continue

        start = float(event.get("tStartMs") or 0) / 1000
        duration = float(event.get("dDurationMs") or 0) / 1000
        end = start + max(duration, 0.1)
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})

    return _dedupe_segments(segments)


def _parse_caption_payload(text: str, ext: str) -> list[dict[str, Any]]:
    ext = (ext or "").lower()
    if ext == "json3":
        return _parse_json3(text)
    return parse_vtt(text)


def _caption_language_rank(language: str) -> tuple[int, str]:
    normalized = (language or "").lower()
    for index, preferred in enumerate(CAPTION_LANGUAGE_PRIORITY):
        if preferred.endswith(".*") and normalized.startswith(preferred[:-1]):
            return (index, normalized)
        if normalized == preferred:
            return (index, normalized)
    if normalized.startswith("en"):
        return (len(CAPTION_LANGUAGE_PRIORITY), normalized)
    return (len(CAPTION_LANGUAGE_PRIORITY) + 1, normalized)


def _caption_extension_rank(ext: str) -> int:
    normalized = (ext or "").lower()
    try:
        return CAPTION_EXTENSION_PRIORITY.index(normalized)
    except ValueError:
        return len(CAPTION_EXTENSION_PRIORITY)


def _caption_display_name(caption: dict[str, Any]) -> str:
    language = str(caption.get("language") or "").strip()
    normalized = language.lower()
    display_language = LANGUAGE_NAMES.get(normalized) or language or "Unknown language"
    kind = "auto captions" if caption.get("automatic") else "subtitles"
    return f"{display_language} {kind}"


def _caption_candidates(caption_groups: dict[str, Any], automatic: bool) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for language, formats in (caption_groups or {}).items():
        if not isinstance(formats, list):
            continue
        for caption_format in formats:
            if not isinstance(caption_format, dict) or not caption_format.get("url"):
                continue
            ext = str(caption_format.get("ext") or "").lower()
            if ext and ext not in CAPTION_EXTENSION_PRIORITY:
                continue
            candidates.append({
                "language": language,
                "url": caption_format["url"],
                "ext": ext or "vtt",
                "automatic": automatic,
                "name": caption_format.get("name") or "",
            })
    return candidates


def _pick_caption(subtitles: dict[str, Any], automatic: dict[str, Any]) -> dict[str, Any] | None:
    candidates = _caption_candidates(subtitles, automatic=False)
    candidates.extend(_caption_candidates(automatic, automatic=True))
    if not candidates:
        return None
    return _sort_caption_candidates(candidates)[0]


def _sort_caption_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (
            item["automatic"],
            _caption_language_rank(item["language"]),
            _caption_extension_rank(item["ext"]),
        ),
    )


def _fetch_caption_text(url: str, ydl: yt_dlp.YoutubeDL | None = None) -> str:
    if ydl is not None:
        response = ydl.urlopen(url)
        try:
            headers = getattr(response, "headers", None)
            charset = headers.get_content_charset() if headers and hasattr(headers, "get_content_charset") else None
            return response.read().decode(charset or "utf-8", errors="ignore")
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    request = urllib.request.Request(
        url,
        headers={
            **PUBLIC_HTTP_HEADERS,
            "Accept": "text/vtt,application/json,text/xml,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


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
                data["text"] = _transcript_text(data["segments"])
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


def _find_cached_transcript_payload(key: str, allowed_sources: set[str] | None = None) -> dict | None:
    json_candidates = sorted(TRANSCRIPT_DIR.glob(f"{key}*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in json_candidates:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if allowed_sources is not None and data.get("source") not in allowed_sources:
            continue
        if isinstance(data.get("segments"), list):
            data["segments"] = _dedupe_segments(data["segments"])
            if data["segments"]:
                data["available"] = True
            data["text"] = _transcript_text(data["segments"])
            data["cached"] = True
            return data

    subtitle_path = _find_downloaded_subtitle_file(key)
    if subtitle_path:
        if allowed_sources is not None and "cache" not in allowed_sources:
            return None
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
        if cached and cached.get("available") and cached.get("source") in {"whisper", "manual"}:
            return cached

        key = _safe_key(filename)
        cached = _find_cached_transcript_payload(key)
        if cached and cached.get("available") and cached.get("source") in {"whisper", "manual"}:
            return cached

    key = _safe_key(filename)
    try:
        audio_path = _download_tiny_audio_sync(filename)
        try:
            segments = _transcribe_with_faster_whisper(audio_path)
        except Exception:
            segments = _transcribe_with_whisper_cli(audio_path, key)
    except Exception as exc:
        return {"available": False, "source": "whisper", "reason": f"Whisper transcription failed: {exc}", "segments": [], "text": ""}

    if not segments:
        return {"available": False, "source": "whisper", "reason": "Whisper produced an empty transcript", "segments": [], "text": ""}
    return _save_transcript_by_key(
        key,
        "whisper",
        segments,
        {
            "filename": filename,
            "subtitle_name": "Whisper transcription",
            "transcript_method": "whisper",
        },
    )


async def fetch_online_transcript(filename: str, force: bool = False) -> dict:
    return await asyncio.to_thread(fetch_online_transcript_sync, filename, force)


def fetch_url_transcript_sync(url: str, force: bool = False) -> dict:
    url = str(url or "").strip()
    if not url:
        return {"available": False, "source": "youtube", "reason": "URL is required", "segments": [], "text": ""}

    fallback_key = f"url_{_safe_url_key(url)}"
    youtube_sources = {"youtube", "youtube_captions", "cache"}
    if not force:
        cached = _find_cached_transcript_payload(fallback_key, youtube_sources)
        if cached and cached.get("available"):
            cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
            return cached

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "no_warnings": True,
        "geo_bypass": True,
        "http_headers": PUBLIC_HTTP_HEADERS,
    }
    add_generic_impersonation(ydl_opts)
    apply_cookiefile(ydl_opts, url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}

            video_id = str(info.get("id") or "").strip()
            key = video_id or fallback_key
            if video_id and not force:
                cached = _find_cached_transcript_payload(key, youtube_sources)
                if cached and cached.get("available"):
                    cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
                    return cached

            captions = _sort_caption_candidates(
                _caption_candidates(info.get("subtitles") or {}, automatic=False)
                + _caption_candidates(info.get("automatic_captions") or {}, automatic=True)
            )
            if not captions:
                return {
                    "available": False,
                    "source": "youtube",
                    "reason": "No YouTube transcript or captions are available for this video. Use the Whisper section for manual transcription.",
                    "segments": [],
                    "text": "",
                }

            last_error = ""
            for caption in captions:
                try:
                    caption_text = _fetch_caption_text(caption["url"], ydl)
                    segments = _parse_caption_payload(caption_text, caption.get("ext") or "vtt")
                except Exception as exc:
                    last_error = str(exc)
                    continue
                if segments:
                    break
            else:
                reason = "YouTube captions were found, but no readable transcript text was available."
                if last_error:
                    reason = f"YouTube captions were found, but could not be loaded: {last_error}"
                return {
                    "available": False,
                    "source": "youtube",
                    "reason": f"{reason} Use the Whisper section for manual transcription.",
                    "segments": [],
                    "text": "",
                }
    except Exception as exc:
        return {"available": False, "source": "youtube", "reason": f"Unable to read YouTube captions: {exc}", "segments": [], "text": ""}

    if not segments:
        return {
            "available": False,
            "source": "youtube",
            "reason": "YouTube captions were found, but no readable transcript text was available. Use the Whisper section for manual transcription.",
            "segments": [],
            "text": "",
        }

    extra = {
        "title": (info.get("title") or "").strip(),
        "url": info.get("webpage_url") or url,
        "video_id": video_id,
        "subtitle_name": _caption_display_name(caption),
        "transcript_method": "youtube_captions",
        "direct": True,
    }
    data = _save_transcript_by_key(key, "youtube", segments, extra)
    if key != fallback_key:
        _save_transcript_by_key(fallback_key, "youtube", segments, extra)
    return data


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
            "format": "bestaudio/best",
            "outtmpl": (TRANSCRIPT_AUDIO_DIR / f"{key}.%(ext)s").as_posix(),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        apply_cookiefile(ydl_opts, url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if audio_path.exists():
            return audio_path

    # Fallback for non-YouTube/local files: extract compact speech-ready audio from existing media.
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
            "192k",
            str(audio_path),
        ],
        check=True,
    )
    return audio_path


def _find_audio_output(key: str) -> Path | None:
    candidates = sorted(
        TRANSCRIPT_AUDIO_DIR.glob(f"{key}.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 1024:
            return candidate
    return None


def _download_url_audio_sync(url: str, key: str, job: dict | None = None) -> tuple[Path, dict[str, Any]]:
    cached_audio = _find_audio_output(key)
    info: dict[str, Any] = {}
    if cached_audio:
        return cached_audio, info

    outtmpl = (TRANSCRIPT_AUDIO_DIR / f"{key}.%(ext)s").as_posix()
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "windowsfilenames": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "http_headers": PUBLIC_HTTP_HEADERS,
    }
    add_generic_impersonation(ydl_opts)
    apply_cookiefile(ydl_opts, url)

    def hook(data):
        if not job or data.get("status") != "downloading":
            return
        percent = str(data.get("_percent_str") or "").strip()
        speed = str(data.get("_speed_str") or "").strip()
        job.update({
            "status": "downloading_audio",
            "progress": 18,
        })
        _update_job_timing(job, f"Downloading best audio{f' ({percent})' if percent else ''}{f' at {speed}' if speed else ''}")

    if job is not None:
        ydl_opts["progress_hooks"] = [hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True) or {}

    audio_path = TRANSCRIPT_AUDIO_DIR / f"{key}.mp3"
    if audio_path.exists() and audio_path.stat().st_size > 1024:
        return audio_path, info

    found = _find_audio_output(key)
    if found:
        return found, info
    raise RuntimeError("Audio download finished but no usable audio file was produced")


def transcribe_url_with_whisper_sync(url: str, force: bool = False, job_id: str | None = None) -> dict:
    url = str(url or "").strip()
    if not url:
        return {"available": False, "source": "whisper", "reason": "URL is required", "segments": [], "text": ""}

    fallback_key = f"url_{_safe_url_key(url)}"
    if not force:
        cached = _find_cached_transcript_payload(fallback_key)
        if cached and cached.get("available") and cached.get("source") in {"whisper", "manual"}:
            cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
            return cached

    job = URL_TRANSCRIPT_JOBS.get(job_id or "")
    if job:
        job.update({"status": "downloading_audio", "progress": 10, "started_at": time.time()})
        _update_job_timing(job, "Downloading best audio for Whisper")

    info: dict[str, Any] = {}
    key = fallback_key
    try:
        audio_path, info = _download_url_audio_sync(url, fallback_key, job)
        video_id = str(info.get("id") or "").strip() if isinstance(info, dict) else ""
        if video_id:
            key = video_id
            better_audio_path = TRANSCRIPT_AUDIO_DIR / f"{key}{audio_path.suffix}"
            if not better_audio_path.exists():
                try:
                    audio_path.replace(better_audio_path)
                    audio_path = better_audio_path
                except Exception:
                    pass

            if not force:
                cached = _find_cached_transcript_payload(key)
                if cached and cached.get("available") and cached.get("source") in {"whisper", "manual"}:
                    cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
                    return cached

        if job:
            size_mb = round(audio_path.stat().st_size / 1024 / 1024, 2)
            estimated_total = max(60, min(900, int(size_mb * 35)))
            job.update({
                "status": "transcribing",
                "progress": 45,
                "audio_size_mb": size_mb,
                "transcribe_started_at": time.time(),
                "estimated_total_seconds": estimated_total,
                "eta_seconds": estimated_total,
            })
            _update_job_timing(job, f"Running Whisper on audio ({size_mb} MB)", estimated_total)

        try:
            segments = _transcribe_with_faster_whisper(audio_path, job=job)
        except Exception:
            segments = _transcribe_with_whisper_cli(audio_path, key)
    except Exception as exc:
        return {"available": False, "source": "whisper", "reason": f"Whisper transcription failed: {exc}", "segments": [], "text": ""}

    if not segments:
        return {"available": False, "source": "whisper", "reason": "Whisper produced an empty transcript", "segments": [], "text": ""}

    title = (info.get("title") or "").strip() if isinstance(info, dict) else ""
    webpage_url = (info.get("webpage_url") or url) if isinstance(info, dict) else url
    video_id = str(info.get("id") or "").strip() if isinstance(info, dict) else ""
    extra = {
        "title": title,
        "url": webpage_url,
        "video_id": video_id,
        "subtitle_name": "Whisper transcription",
        "transcript_method": "whisper",
        "direct": False,
    }
    data = _save_transcript_by_key(key, "whisper", segments, extra)
    if key != fallback_key:
        _save_transcript_by_key(fallback_key, "whisper", segments, extra)
    return data


def _transcribe_with_faster_whisper(audio_path: Path, job: dict | None = None) -> list[dict[str, Any]]:
    model, model_settings = _get_faster_whisper_model()
    beam_size = _env_int("WHISPER_BEAM_SIZE", 1, 1, 10)
    best_of = _env_int("WHISPER_BEST_OF", 1, 1, 10)
    vad_filter = _env_bool("WHISPER_VAD_FILTER", True)
    try:
        temperature = float(os.environ.get("WHISPER_TEMPERATURE", "0.0") or "0.0")
    except ValueError:
        temperature = 0.0

    segments = []
    with WHISPER_TRANSCRIBE_LOCK:
        with _capture_faster_whisper_progress(job, audio_path):
            segments_iter, info = model.transcribe(
                str(audio_path),
                log_progress=bool(job),
                beam_size=beam_size,
                best_of=best_of,
                temperature=temperature,
                vad_filter=vad_filter,
            )
            duration = float(getattr(info, "duration", 0.0) or 0.0)
            if job:
                job["whisper_settings"] = {
                    **model_settings,
                    "beam_size": beam_size,
                    "best_of": best_of,
                    "temperature": temperature,
                    "vad_filter": vad_filter,
                }
                job["_terminal_transcription_bucket"] = 0
                print(
                    f"[transcription] started - {_terminal_transcription_label(job, audio_path)}"
                    f"{f' ({_duration_label(duration)})' if duration > 0 else ''}",
                    flush=True,
                )
                print(
                    "[transcription] settings - "
                    f"model={model_settings['model']}, compute={model_settings['compute_type']}, "
                    f"threads={model_settings['cpu_threads']}, beam={beam_size}, best_of={best_of}, vad={vad_filter}",
                    flush=True,
                )
            for segment in segments_iter:
                text = _clean_caption_text(segment.text)
                if text:
                    segments.append({"start": round(float(segment.start), 3), "end": round(float(segment.end), 3), "text": text})
                if job and duration > 0:
                    covered = min(1.0, max(0.0, float(segment.end or 0.0) / duration))
                    progress = min(95, max(float(job.get("progress") or 45), 45 + covered * 50))
                    elapsed = max(1, time.time() - float(job.get("transcribe_started_at") or time.time()))
                    eta_seconds = int((elapsed / max(covered, 0.01)) - elapsed) if covered > 0 else None
                    job.update({"progress": round(progress, 1)})
                    _update_job_timing(job, "Running Whisper", eta_seconds)
            if job:
                _log_transcription_progress(job, audio_path, 100, force=True)
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
        job.update({"status": "downloading_audio", "progress": 12, "message": "Downloading best audio for transcription..."})
        audio_path = _download_tiny_audio_sync(filename)
        job.update({
            "status": "transcribing",
            "progress": 35,
            "transcribe_started_at": time.time(),
            "message": f"Transcribing from audio ({round(audio_path.stat().st_size / 1024 / 1024, 2)} MB)...",
        })
        try:
            segments = _transcribe_with_faster_whisper(audio_path, job=job)
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


async def start_url_whisper_transcription(url: str, force: bool = False) -> dict:
    url = str(url or "").strip()
    if not url:
        raise ValueError("URL is required")

    if not force:
        cached = _find_cached_transcript_payload(f"url_{_safe_url_key(url)}")
        if cached and cached.get("available") and cached.get("source") in {"whisper", "manual"}:
            cached["text"] = cached.get("text") or _transcript_text(cached.get("segments") or [])
            return {"already_done": True, "job_id": None, "result": cached}

    job_id = str(uuid.uuid4())
    URL_TRANSCRIPT_JOBS[job_id] = {
        "job_id": job_id,
        "url": url,
        "status": "queued",
        "progress": 0,
        "message": "Whisper transcription queued",
        "created_at": time.time(),
    }

    async def runner():
        job = URL_TRANSCRIPT_JOBS[job_id]
        try:
            result = await asyncio.to_thread(transcribe_url_with_whisper_sync, url, force, job_id)
            if result.get("available"):
                job.update({"status": "completed", "progress": 100, "message": "Whisper transcript ready", "result": result})
            else:
                reason = result.get("reason") or "Whisper transcription failed"
                job.update({"status": "error", "progress": 100, "message": reason, "error": reason, "result": result})
        except Exception as exc:
            job.update({"status": "error", "progress": 100, "message": str(exc), "error": str(exc)})

    asyncio.create_task(runner())
    return {"already_done": False, "job_id": job_id, "status": "queued"}


def get_url_transcription_job(job_id: str) -> dict | None:
    return URL_TRANSCRIPT_JOBS.get(job_id)
