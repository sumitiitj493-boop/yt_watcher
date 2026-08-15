"""Clip Studio — cut precise clips from downloaded videos.

  - analyze a video (total duration, resolution, size)
  - cut a clip between two timestamps using ffmpeg (accurate re-encode)
  - save the clip into the Library and register it in the Clips section
  - optionally auto-add the clip file to a user-chosen playlist

Jobs run in a background thread and report progress (mirrors the audio
extractor / converter patterns). The clip file is written to DOWNLOAD_DIR so
it shows up in the Library immediately; the clips table keeps the metadata for
the dedicated Clips section.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from services.database import add_playlist_item, create_clip_row
from services.files import DOWNLOAD_DIR

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

CLIP_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.RLock()

VIDEO_EXTENSIONS = {"mp4", "webm", "mkv", "mov", "m4v", "avi", "mpeg", "mpg", "ts", "wmv", "3gp", "m4a"}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def is_video_file(filename: str) -> bool:
    ext = str(filename or "").rsplit(".", 1)[-1].lower() if "." in str(filename or "") else ""
    return ext in VIDEO_EXTENSIONS


def _seconds_label(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_eta(seconds) -> str:
    if seconds is None:
        return "…"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


def _probe_duration(path: Path) -> Optional[float]:
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _codecs_for_container(ext: str) -> tuple[str, str, str]:
    """Return (video_codec, audio_codec, audio_bitrate_flag) for a container.

    Used when re-encoding so the codecs always match the output container
    (e.g. webm cannot hold libx264/aac).
    """
    ext = (ext or "").lower().lstrip(".")
    if ext == "webm":
        return "libvpx-vp9", "libopus", "-b:a"
    if ext in ("avi",):
        return "mpeg4", "mp3", "-b:a"
    if ext in ("mpeg", "mpg"):
        return "mpeg2video", "mp2", "-b:a"
    if ext in ("wmv",):
        return "wmv2", "wmav2", "-b:a"
    # mp4 / mov / m4v / mkv / ts / 3gp / anything else
    return "libx264", "aac", "-b:a"


def _probe_streams(path: Path) -> dict:
    """Return the video/audio codecs of the source (for concat compatibility)."""
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "stream=index,codec_type,codec_name",
             "-of", "csv=p=0", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        vcodec = None
        acodec = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                ctype = parts[1]
                cname = parts[2]
            except IndexError:
                continue
            if ctype == "video" and vcodec is None:
                vcodec = cname
            elif ctype == "audio" and acodec is None:
                acodec = cname
        return {"video_codec": vcodec, "audio_codec": acodec}
    except Exception:
        return {"video_codec": None, "audio_codec": None}


def _probe_keyframes(path: Path, window_start: float, window_end: float) -> list[float]:
    """Return video keyframe timestamps (pts) within [window_start, window_end].

    Used by Smart mode to find the keyframe right after the exact start so the
    tiny start sliver can be re-encoded while the bulk is stream-copied.
    """
    try:
        cmd = [
            FFPROBE, "-v", "error",
            "-select_streams", "v:0",
            "-skip_frame", "nokey",
            "-show_entries", "frame=pts_time",
            "-of", "csv=p=0",
            "-read_intervals", f"{max(0.0, window_start):.3f}%{max(0.0, window_end):.3f}",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        times: list[float] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                times.append(float(line))
            except ValueError:
                continue
        return times
    except Exception:
        return []


def _concat_parts(parts: list[Path], out_path: Path) -> None:
    """Concatenate the parts with the concat demuxer (all h264/aac, no re-encode)."""
    list_file = out_path.with_suffix(out_path.suffix + ".concat.txt")
    lines = []
    for part in parts:
        escaped = str(part.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        subprocess.run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        try:
            list_file.unlink(missing_ok=True)
        except Exception:
            pass


def _run_smart_hybrid(job: dict, source: Path, out_path: Path, start: float, end: float) -> bool:
    """Smart mode v2: exact boundaries with a mostly stream-copied middle.

    - Re-encode ONLY the tiny sliver [start, first_keyframe_after_start]
      (usually < 1s) so the cut starts exactly at the requested timestamp,
      reporting LIVE progress (0-45%).
    - Stream-copy the bulk [first_keyframe, end] — `-c copy` is instant and
      the end boundary is already frame-exact with `-t` (45-90%).
    - Concatenate the two parts (no re-encode on concat) (90-99%).

    Returns True on success, False if the hybrid isn't applicable (falls back
    to the regular re-encode path with its own progress).
    """
    # Concat demuxer only reliably joins identical codecs. If the source isn't
    # h264+aac (e.g. webm/vp9/opus), skip the hybrid entirely and fall back to
    # the normal smart re-encode — otherwise part A (h264/aac) wouldn't concat
    # with part B (copied vp9/opus) and we'd waste time.
    streams = _probe_streams(source)
    vcodec = (streams.get("video_codec") or "").lower()
    acodec = (streams.get("audio_codec") or "").lower()
    if not (vcodec.startswith("h264") or vcodec in ("avc1", "avc")) or not (acodec.startswith("aac") or acodec in ("mp4a",)):
        return False

    probe_window = min(15.0, max(2.0, end - start))
    keys = _probe_keyframes(source, start, min(end + 1.0, start + probe_window * 2))
    # First keyframe at-or-after the exact start
    first_key = next((k for k in keys if k >= start - 0.001), None)
    if first_key is None or first_key >= end - 0.3:
        return False  # no copyable middle — fall back to full re-encode

    part_a = out_path.with_suffix(out_path.suffix + ".part_a.mp4")
    part_b = out_path.with_suffix(out_path.suffix + ".part_b.mp4")
    a_dur = first_key - start
    b_dur = end - first_key
    job_started = time.time()

    def _run_with_progress(cmd: list[str], total_media: float, progress_from: float, progress_to: float, msg: str) -> None:
        """Run ffmpeg, updating job progress smoothly from -> to as it decodes."""
        cmd = list(cmd) + ["-progress", "pipe:1", "-nostats"]
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

        phase_started = time.time()
        assert proc.stdout is not None
        for line in proc.stdout:
            stripped = line.strip()
            if stripped.startswith("out_time_ms="):
                try:
                    ms = int(stripped.split("=", 1)[1])
                except ValueError:
                    continue
                seconds = ms / 1_000_000
                fraction = min(1.0, seconds / total_media) if total_media > 0 else 1.0
                job["progress"] = round(progress_from + (progress_to - progress_from) * fraction)
                elapsed = time.time() - phase_started
                job["elapsed_seconds"] = round(time.time() - job_started)
                if seconds > 0.5 and elapsed > 0.5:
                    remaining = max(0.0, total_media - seconds)
                    speed = seconds / elapsed
                    job["eta_seconds"] = round(remaining / speed) if speed > 0 else None
                else:
                    job["eta_seconds"] = None
                if job.get("eta_seconds") is not None:
                    job["message"] = f"{msg} · ETA {_format_eta(job['eta_seconds'])}"
                else:
                    job["message"] = msg
        proc.wait()
        stderr_thread.join(timeout=5)
        if proc.returncode != 0:
            raise RuntimeError("".join(error_lines[-6:]).strip() or "ffmpeg exited with an error")

    try:
        job["message"] = "Precise start... (phase 1/3)"
        # Part A: re-encode only the start sliver (exact start). Both video AND
        # audio are re-encoded so both streams start at pts ~0 — if audio were
        # copied here it would keep its original pts and the concat would
        # misalign (making the container duration wrong by ~1s).
        _run_with_progress(
            [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{start:.3f}", "-i", str(source),
                "-t", f"{a_dur:.3f}",
                # ultrafast is fine here: part A is only the sub-keyframe
                # sliver (a few seconds max), so the size bloat that made
                # whole-clip ultrafast huge is negligible for this tiny piece.
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(part_a),
            ],
            a_dur,
            5,
            45,
            "Precise start... (phase 1/3)",
        )

        job["message"] = "Copying middle... (phase 2/3, instant)"
        # Part B: stream-copy the bulk (starts at a keyframe, exact end via -t)
        _run_with_progress(
            [
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{first_key:.3f}", "-i", str(source),
                "-t", f"{b_dur:.3f}",
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-movflags", "+faststart",
                str(part_b),
            ],
            b_dur,
            45,
            90,
            "Copying middle... (phase 2/3, instant)",
        )

        job["message"] = "Joining... (phase 3/3)"
        _concat_parts([part_a, part_b], out_path)
        job["progress"] = 99
        job["eta_seconds"] = None
        return True
    except Exception:
        return False
    finally:
        for part in (part_a, part_b):
            try:
                part.unlink(missing_ok=True)
            except Exception:
                pass


def analyze_file(filename: str) -> dict:
    """Return duration + metadata for a downloaded video (no cutting)."""
    if not ffmpeg_available():
        raise ValueError("ffmpeg was not found on this system. Install ffmpeg and restart the backend.")

    source = DOWNLOAD_DIR / Path(filename).name
    if not source.exists():
        raise FileNotFoundError("Video file not found")

    duration = _probe_duration(source)
    size = source.stat().st_size

    # Probe video/audio streams for resolution info.
    width = height = None
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(source)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        parts = result.stdout.strip().split("x")
        if len(parts) == 2:
            width = int(parts[0])
            height = int(parts[1])
    except Exception:
        pass

    return {
        "filename": source.name,
        "duration": duration,
        "duration_label": _seconds_label(duration or 0),
        "size_bytes": size,
        "width": width,
        "height": height,
        "available": True,
    }


def _unique_clip_path(source: Path, title: str) -> Path:
    ext = source.suffix or ".mp4"
    stem = (title or source.stem or "clip").strip() or "clip"
    safe = "".join(ch if ch.isalnum() or ch in " -_()" else "_" for ch in stem).strip() or "clip"
    candidate = DOWNLOAD_DIR / f"{safe} (clip).{ext.lstrip('.')}"
    index = 1
    while candidate.exists():
        candidate = DOWNLOAD_DIR / f"{safe} (clip) ({index}).{ext.lstrip('.')}"
        index += 1
    return candidate


def start_clip_job(
    filename: str,
    start_seconds: float,
    end_seconds: float,
    title: str = "",
    collection: str = "",
    target_playlist_id: Optional[int] = None,
    mode: str = "smart",
) -> str:
    """Queue a clip cut. Returns a job_id.

    ``mode``:
      - "fast"     : stream-copy (no re-encode) — nearly instant, but the cut
                     lands on the nearest keyframe (may be a second or two
                     before/after the exact timestamp).
      - "smart"    : hybrid — re-encode only the tiny start sliver, stream-copy
                     the bulk, concat. Exact timestamps, fast. Falls back to a
                     full re-encode if the source isn't h264/aac.
      - "accurate" : re-encode (libx264 veryfast) — exact timestamps, slower.
    """
    if not ffmpeg_available():
        raise ValueError("ffmpeg was not found on this system. Install ffmpeg and restart the backend.")

    source = DOWNLOAD_DIR / Path(filename).name
    if not source.exists():
        raise FileNotFoundError("Video file not found")

    mode = (mode or "smart").strip().lower()
    # Never hard-fail on an unknown mode — coerce to the recommended smart mode
    # so a stale frontend/backend mismatch can't cause 422 errors.
    if mode not in ("fast", "smart", "accurate"):
        mode = "smart"

    start = max(0.0, float(start_seconds or 0))
    end = float(end_seconds or 0)
    duration = _probe_duration(source) or 0
    if end <= start:
        raise ValueError("End time must be after start time")
    if duration and end > duration:
        end = duration
    if end - start <= 0:
        raise ValueError("Clip length must be more than 0 seconds")

    out_path = _unique_clip_path(source, title)
    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        "job_id": job_id,
        "source": source.name,
        "output": out_path.name,
        "title": (title or source.stem).strip(),
        "collection": (collection or "").strip(),
        "target_playlist_id": target_playlist_id,
        "start_seconds": start,
        "end_seconds": end,
        "clip_duration": round(end - start, 3),
        "mode": mode,
        "status": "queued",
        "progress": 0,
        "message": "Clip cut queued",
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "elapsed_seconds": 0,
        "filename": None,
        "size_bytes": None,
        "error": None,
    }
    with _JOBS_LOCK:
        CLIP_JOBS[job_id] = job

    threading.Thread(
        target=_run_clip_job,
        args=(job_id, source, out_path, start, end, title, collection, target_playlist_id, mode),
        daemon=True,
    ).start()
    return job_id


def _run_clip_job(job_id, source, out_path, start, end, title, collection, target_playlist_id, mode) -> None:
    job = CLIP_JOBS[job_id]
    started = time.time()
    job["started_at"] = started
    clip_duration = max(0.1, end - start)
    try:
        job["status"] = "cutting"
        mode_msg = {
            "fast": "Cutting clip (fast)...",
            "smart": "Cutting clip (smart: exact + fast)...",
            "accurate": "Cutting clip (accurate)...",
        }
        job["message"] = mode_msg.get(mode, "Cutting clip...")

        # Input seeking (-ss before -i) is dramatically faster than output
        # seeking — ffmpeg jumps to the timestamp via the index, then only
        # decodes/copies the short clip.
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}", "-i", str(source),
            "-t", f"{clip_duration:.3f}",
        ]

        if mode == "fast":
            # Stream copy: no re-encode, just copy the exact bytes between
            # keyframes. Nearly instant for any file size, but the cut lands
            # on the nearest keyframe (may be a second or two off).
            cmd += [
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-movflags", "+faststart",
            ]
        elif mode == "smart":
            # Best of both worlds v2 (hybrid): re-encode only the tiny start
            # sliver for exactness, stream-copy the bulk, then concat. Falls
            # back to a full re-encode (codec-aware) if the hybrid isn't
            # applicable for this file.
            if _run_smart_hybrid(job, source, out_path, start, end):
                cmd = []  # hybrid already wrote the output
            else:
                vcodec, acodec, aflag = _codecs_for_container(out_path.suffix)
                cmd += [
                    "-c:v", vcodec, "-preset", "veryfast", "-crf", "20",
                    "-c:a", acodec,
                ]
                if aflag:
                    cmd += [aflag, "128k"]
                cmd += ["-movflags", "+faststart"]
        else:
            # Accurate: re-encode video + audio so the cut is frame-exact.
            vcodec, acodec, aflag = _codecs_for_container(out_path.suffix)
            cmd += [
                "-c:v", vcodec, "-preset", "veryfast", "-crf", "23",
                "-c:a", acodec,
            ]
            if aflag:
                cmd += [aflag, "128k"]
            cmd += ["-movflags", "+faststart"]

        # The hybrid smart mode may have already produced the output file.
        hybrid_done = not cmd

        if not hybrid_done:
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
                    elapsed = time.time() - started
                    job["progress"] = min(99, round(seconds / clip_duration * 100))
                    job["elapsed_seconds"] = round(elapsed)
                    # ETA = remaining work / observed speed (only when we have
                    # meaningful progress and elapsed time).
                    if seconds > 0.5 and elapsed > 0.5:
                        remaining = max(0.0, clip_duration - seconds)
                        speed = seconds / elapsed  # media-seconds per wall-second
                        if speed > 0:
                            eta = remaining / speed
                            job["eta_seconds"] = round(eta)
                        else:
                            job["eta_seconds"] = None
                    else:
                        job["eta_seconds"] = None
                    if job.get("eta_seconds") is not None:
                        job["message"] = f"Cutting clip... {job['progress']}% · ETA {_format_eta(job['eta_seconds'])}"
                    else:
                        job["message"] = f"Cutting clip... {job['progress']}%"

            proc.wait()
            stderr_thread.join(timeout=5)

            if proc.returncode != 0 or not out_path.exists():
                err_text = "".join(error_lines[-8:]).strip() or "ffmpeg exited with an error"
                raise RuntimeError(err_text)
        elif not out_path.exists():
            raise RuntimeError("Hybrid cut produced no output file")

        size = out_path.stat().st_size

        # Register in the Clips section.
        row = create_clip_row(
            filename=out_path.name,
            source_filename=source.name,
            title=(title or source.stem).strip(),
            start_seconds=start,
            end_seconds=end,
            duration_seconds=round(clip_duration, 3),
            collection=(collection or "").strip(),
            size_bytes=size,
        )

        # Optionally add to a playlist too.
        playlist_error = None
        if target_playlist_id and row:
            try:
                add_playlist_item(target_playlist_id, out_path.name)
            except Exception as exc:
                playlist_error = str(exc)

        job.update({
            "status": "completed",
            "progress": 100,
            "message": "Clip saved",
            "filename": out_path.name,
            "size_bytes": size,
            "elapsed_seconds": round(time.time() - started),
            "completed_at": time.time(),
            "clip_id": row.get("id") if row else None,
            "playlist_error": playlist_error,
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


def get_clip_job(job_id: str) -> Optional[dict]:
    job = CLIP_JOBS.get(job_id)
    if job is None:
        return None
    return dict(job)
