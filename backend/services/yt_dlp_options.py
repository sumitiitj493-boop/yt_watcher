from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PUBLIC_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

DEFAULT_YOUTUBE_COOKIES_FILE = BACKEND_DIR / "youtube_cookies.txt"
DEFAULT_SOCIAL_COOKIES_FILE = BACKEND_DIR / "instagram_cookies.txt"
LEGACY_COOKIES_FILE = BACKEND_DIR / "cookies.txt"

YTDLP_SOCKET_TIMEOUT_SECONDS = max(10, int(os.environ.get("YTDLP_SOCKET_TIMEOUT_SECONDS", "25") or "25"))
YTDLP_EXTRACTOR_RETRIES = max(0, int(os.environ.get("YTDLP_EXTRACTOR_RETRIES", "1") or "1"))
YTDLP_RETRIES = max(0, int(os.environ.get("YTDLP_RETRIES", "3") or "3"))
YTDLP_FRAGMENT_RETRIES = max(0, int(os.environ.get("YTDLP_FRAGMENT_RETRIES", "3") or "3"))
YTDLP_STARTUP_TIMEOUT_SECONDS = max(0, int(os.environ.get("YTDLP_STARTUP_TIMEOUT_SECONDS", "180") or "180"))
YTDLP_YOUTUBE_HTTP_CHUNK_MB = max(0, int(os.environ.get("YTDLP_YOUTUBE_HTTP_CHUNK_MB", "10") or "10"))

YOUTUBE_AUTH_COOKIE_NAMES = {
    "SID",
    "HSID",
    "SSID",
    "APISID",
    "SAPISID",
    "LOGIN_INFO",
    "SIDCC",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "__Secure-1PSIDCC",
    "__Secure-3PSIDCC",
    "__Secure-1PSIDTS",
    "__Secure-3PSIDTS",
}


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate

    # The backend is normally launched from backend/, but tests/tools may run
    # from the project root. Prefer an existing path, otherwise resolve relative
    # to the backend directory for predictable local setup.
    cwd_candidate = Path.cwd() / candidate
    backend_candidate = BACKEND_DIR / candidate
    project_candidate = PROJECT_DIR / candidate
    for path in (cwd_candidate, backend_candidate, project_candidate):
        if path.exists():
            return path
    return backend_candidate


def youtube_cookies_file() -> Path:
    return _env_path("YOUTUBE_COOKIES_FILE", DEFAULT_YOUTUBE_COOKIES_FILE)


def social_cookies_file() -> Path:
    # Respect explicit env override first
    value = os.environ.get("SOCIAL_COOKIES_FILE")
    if value:
        return _env_path("SOCIAL_COOKIES_FILE", DEFAULT_SOCIAL_COOKIES_FILE)

    # Accept a small set of common filenames (including a misspelling) so users
    # who drop a file in the backend folder still get picked up without env vars.
    candidates = [
        BACKEND_DIR / "instagram_cookies.txt",
        BACKEND_DIR / "instagram_cookes.txt",
        BACKEND_DIR / "social_cookies.txt",
        BACKEND_DIR / "cookies.txt",
    ]
    for candidate in candidates:
        # Prefer an existing file in the repo/backend or cwd/project locations
        cwd_candidate = Path.cwd() / candidate.name
        project_candidate = PROJECT_DIR / candidate.name
        backend_candidate = candidate
        for path in (cwd_candidate, backend_candidate, project_candidate):
            if path.exists() and path.is_file():
                return path

    # Fallback to the default path when nothing else exists
    return DEFAULT_SOCIAL_COOKIES_FILE


def social_cookies_browsers() -> list[str]:
    """Browsers to pull Instagram/social cookies from, via yt-dlp
    ``cookiesfrombrowser``. Configure with SOCIAL_COOKIES_BROWSER
    (comma-separated, e.g. ``chrome,edge,firefox``)."""
    raw = os.environ.get("SOCIAL_COOKIES_BROWSER", "").strip()
    if not raw:
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def youtube_cookies_browsers() -> list[str]:
    """Browsers to pull YouTube cookies from when no usable file is present.

    Set YOUTUBE_COOKIES_BROWSER=off to disable this. Firefox is tried first
    because yt-dlp can usually read it more reliably than Chromium profiles on
    current Windows installs.
    """
    raw = os.environ.get("YOUTUBE_COOKIES_BROWSER", "firefox,chrome,edge,brave,opera").strip()
    if raw.lower() in {"", "off", "none", "false", "0"}:
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def is_youtube_url(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return (
        host in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
            "youtube-nocookie.com",
            "www.youtube-nocookie.com",
        }
        or host.endswith(".youtube.com")
    )


def is_instagram_url(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host == "instagram.com" or host.endswith(".instagram.com")


def instagram_error_help(error: str) -> str:
    """Turn a raw yt-dlp Instagram error into actionable guidance."""
    text = (error or "").lower()
    if any(marker in text for marker in ("app-bound", "appbound", "failed to decrypt", "dpapi", "decrypt", "keyring", "keychain")):
        return (
            "The browser cookie file could not be decrypted. Recent Chrome/Edge encrypt cookies "
            "(app-bound encryption) so yt-dlp cannot read them. Fix: 1) Use Firefox and set "
            "SOCIAL_COOKIES_BROWSER=firefox, OR 2) upload an instagram_cookies.txt file exported "
            "from your logged-in browser (see the 'Instagram login cookies' card on this page)."
        )
    if "empty media response" in text:
        return (
            "Instagram now blocks downloads unless you're logged in. Fix, easiest first: "
            "1) On this page, use the 'Instagram login cookies' card to upload an "
            "instagram_cookies.txt file exported from your logged-in browser (install the "
            "'Get cookies.txt LOCALLY' browser extension, log into Instagram, export cookies). "
            "2) Or set the backend environment variable SOCIAL_COOKIES_BROWSER=firefox "
            "(Firefox cookies work best — recent Chrome/Edge encrypt cookies and yt-dlp may not "
            "read them), then restart the backend. 3) Or save the cookies file directly to "
            "backend/instagram_cookies.txt."
        )
    if any(marker in text for marker in ("login", "sign in", "log in", "authentication", "not logged")):
        return (
            "Instagram requires login for this post. Log in on this PC and either set "
            "SOCIAL_COOKIES_BROWSER=firefox (or chrome/edge) and restart the backend, or upload "
            "a Netscape-format instagram_cookies.txt via the 'Instagram login cookies' card."
        )
    if "unsupported url" in text:
        return (
            "yt-dlp does not support this link. Make sure you pasted a direct post/reel/story URL "
            "from instagram.com."
        )
    return ""


def _candidate_cookie_paths(url: str) -> list[Path]:
    if is_youtube_url(url):
        candidates = [youtube_cookies_file(), LEGACY_COOKIES_FILE]
    else:
        # Allow a general legacy cookies.txt as a fallback for social platforms
        candidates = [social_cookies_file(), LEGACY_COOKIES_FILE]

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate.absolute())
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def get_cookiefile_for_url(url: str) -> Path | None:
    for candidate in _candidate_cookie_paths(url):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _read_cookie_lines(path: Path, max_bytes: int = 2_000_000) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    raw = path.read_bytes()[:max_bytes]
    return raw.decode("utf-8", errors="ignore").splitlines()


def _parse_netscape_cookie_names(path: Path) -> tuple[set[str], int]:
    names: set[str] = set()
    count = 0
    for raw_line in _read_cookie_lines(path):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        name = parts[5].strip()
        if name:
            names.add(name)
            count += 1
    return names, count


def cookiefile_report(url: str) -> dict[str, Any]:
    candidates = _candidate_cookie_paths(url)
    selected = get_cookiefile_for_url(url)
    expected = candidates[0] if candidates else None
    report: dict[str, Any] = {
        "platform": "youtube" if is_youtube_url(url) else "social",
        "expected_path": str(expected) if expected else "",
        "selected_path": str(selected) if selected else "",
        "exists": bool(selected),
        "candidate_paths": [str(path) for path in candidates],
        "is_netscape": False,
        "is_json": False,
        "cookie_count": 0,
        "auth_cookie_names": [],
        "has_auth_cookies": False,
        "size_bytes": 0,
        "modified_at": None,
        "age_seconds": None,
        "warning": "",
    }

    if not selected:
        if is_youtube_url(url):
            report["warning"] = (
                "No YouTube cookie file found. Public videos can still work, but "
                "members-only/private videos need backend/youtube_cookies.txt."
            )
        return report

    try:
        stat = selected.stat()
        report["size_bytes"] = stat.st_size
        report["modified_at"] = stat.st_mtime
        report["age_seconds"] = max(0, int(time.time() - stat.st_mtime))
    except OSError:
        pass

    lines = _read_cookie_lines(selected)
    first_content = ""
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped:
            first_content = stripped
            break

    if first_content.startswith("{") or first_content.startswith("["):
        report["is_json"] = True
        report["warning"] = (
            "Cookie file looks like JSON. yt-dlp needs Netscape/Mozilla cookies.txt format. "
            "Re-export cookies as Netscape format."
        )
        return report

    names, count = _parse_netscape_cookie_names(selected)
    auth_names = sorted(name for name in names if name in YOUTUBE_AUTH_COOKIE_NAMES or name.startswith("__Secure-"))
    report.update({
        "is_netscape": count > 0,
        "cookie_count": count,
        "auth_cookie_names": auth_names,
        "has_auth_cookies": bool(auth_names),
    })

    if count == 0:
        report["warning"] = (
            "Cookie file exists, but no Netscape cookie rows were detected. "
            "Export cookies in Netscape/Mozilla cookies.txt format."
        )
    elif is_youtube_url(url) and not auth_names:
        report["warning"] = (
            "YouTube cookie file exists, but it does not look logged-in. "
            "Export from the exact browser profile where the members-only video plays."
        )

    return report


def validate_cookiefile_for_ytdlp(url: str, *, require_youtube_auth: bool = False) -> dict[str, Any]:
    report = cookiefile_report(url)
    if not report["exists"]:
        if require_youtube_auth and is_youtube_url(url):
            raise RuntimeError(
                "YouTube cookies are required for members-only/private videos. "
                f"Save Netscape-format cookies to {report['expected_path']}"
            )
        return report

    if report["is_json"]:
        raise RuntimeError(
            f"Cookie file {report['selected_path']} looks like JSON. "
            "yt-dlp needs Netscape/Mozilla cookies.txt format."
        )
    if not report["is_netscape"]:
        raise RuntimeError(
            f"Cookie file {report['selected_path']} is not in a readable Netscape cookies.txt format."
        )
    if require_youtube_auth and is_youtube_url(url) and not report["has_auth_cookies"]:
        raise RuntimeError(
            "YouTube cookie file was found, but it does not contain logged-in auth cookies. "
            "Export from the same browser/profile where the members-only video plays."
        )
    return report


def apply_cookiefile(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    cookies_file = get_cookiefile_for_url(url)
    if cookies_file:
        ydl_opts["cookiefile"] = str(cookies_file)
    return ydl_opts


def apply_cookiesfrombrowser(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    """Pass cookies straight from a local browser profile (e.g. Chrome/Edge
    where the user is logged into Instagram). This is the easiest fix for
    Instagram's "empty media response" auth wall: no file to export."""
    if "cookiefile" in ydl_opts:
        return ydl_opts
    browsers = social_cookies_browsers()
    if not browsers:
        return ydl_opts
    ydl_opts["cookiesfrombrowser"] = (browsers[0], None, None, None)
    return ydl_opts


def apply_youtube_auth_options(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    """Authentication helpers for YouTube URLs.

    Prefer an uploaded Netscape cookie file when present. If there is no cookie
    file, fall back to the local logged-in browser profile so users do not need
    to keep exporting cookies for ordinary authenticated downloads.
    """
    if not is_youtube_url(url):
        return ydl_opts
    apply_cookiefile(ydl_opts, url)
    if "cookiefile" not in ydl_opts:
        browsers = youtube_cookies_browsers()
        if browsers:
            ydl_opts["cookiesfrombrowser"] = (browsers[0], None, None, None)
    return ydl_opts


def apply_social_auth_options(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    """Authentication helpers for non-YouTube (Instagram / social) URLs."""
    if is_youtube_url(url):
        return ydl_opts
    apply_cookiefile(ydl_opts, url)
    apply_cookiesfrombrowser(ydl_opts, url)
    return ydl_opts


def _merge_extractor_args(ydl_opts: dict[str, Any], ie_key: str, values: dict[str, list[str]]) -> None:
    extractor_args = dict(ydl_opts.get("extractor_args") or {})
    existing = dict(extractor_args.get(ie_key) or {})
    for key, value in values.items():
        existing.setdefault(key, value)
    extractor_args[ie_key] = existing
    ydl_opts["extractor_args"] = extractor_args


def _configured_js_runtimes() -> dict[str, dict[str, str | None]]:
    configured = os.environ.get("YTDLP_JS_RUNTIMES", "node,deno,bun").strip()
    if configured.lower() in {"", "off", "none", "false", "0"}:
        return {}

    runtimes: dict[str, dict[str, str | None]] = {}
    for entry in configured.split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, _, path = entry.partition(":")
        name = name.strip().lower()
        if not name:
            continue
        config: dict[str, str | None] = {}
        if path.strip():
            config["path"] = path.strip()
        runtimes[name] = config
    return runtimes


def apply_youtube_runtime_options(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    if not is_youtube_url(url):
        return ydl_opts

    runtimes = _configured_js_runtimes()
    if runtimes:
        ydl_opts.setdefault("js_runtimes", runtimes)

    remote_components = os.environ.get("YTDLP_REMOTE_COMPONENTS", "ejs:github").strip()
    if remote_components.lower() not in {"", "off", "none", "false", "0"}:
        ydl_opts.setdefault(
            "remote_components",
            [component.strip() for component in remote_components.split(",") if component.strip()],
        )

    # yt-dlp's default TV fallback can extract media URLs that later fail with
    # HTTP 403 for authenticated/member videos. Exclude it unless overridden.
    configured_clients = os.environ.get("YTDLP_YOUTUBE_PLAYER_CLIENTS", "default,-tv_downgraded").strip()
    if configured_clients.lower() not in {"", "off", "none", "false", "0"}:
        _merge_extractor_args(
            ydl_opts,
            "youtube",
            {"player_client": [client.strip() for client in configured_clients.split(",") if client.strip()]},
        )

    configured_webpage_client = os.environ.get("YTDLP_YOUTUBE_WEBPAGE_CLIENT", "").strip()
    if configured_webpage_client:
        _merge_extractor_args(ydl_opts, "youtube", {"webpage_client": [configured_webpage_client]})

    return ydl_opts


def add_generic_impersonation(ydl_opts: dict[str, Any]) -> dict[str, Any]:
    """Enable yt-dlp's generic extractor Cloudflare impersonation retry."""
    extractor_args = dict(ydl_opts.get("extractor_args") or {})
    generic_args = dict(extractor_args.get("generic") or {})
    generic_args.setdefault("impersonate", ["chrome"])
    extractor_args["generic"] = generic_args
    ydl_opts["extractor_args"] = extractor_args
    return ydl_opts


def apply_reliable_ytdlp_options(ydl_opts: dict[str, Any], url: str) -> dict[str, Any]:
    """Apply shared, conservative yt-dlp defaults used by metadata/download/Whisper.

    This intentionally does not force authentication. If a YouTube cookie file is
    present it is used; otherwise public videos still work. Diagnostics expose
    whether cookies look usable for members-only videos without printing values.
    """
    headers = dict(PUBLIC_HTTP_HEADERS)
    headers.update(dict(ydl_opts.get("http_headers") or {}))
    ydl_opts["http_headers"] = headers

    ydl_opts.setdefault("retries", YTDLP_RETRIES)
    ydl_opts.setdefault("fragment_retries", YTDLP_FRAGMENT_RETRIES)
    ydl_opts.setdefault("extractor_retries", YTDLP_EXTRACTOR_RETRIES)
    ydl_opts.setdefault("socket_timeout", YTDLP_SOCKET_TIMEOUT_SECONDS)
    ydl_opts.setdefault("geo_bypass", True)
    ydl_opts.setdefault("nocheckcertificate", False)

    add_generic_impersonation(ydl_opts)
    apply_youtube_runtime_options(ydl_opts, url)
    if is_youtube_url(url):
        if YTDLP_YOUTUBE_HTTP_CHUNK_MB > 0:
            ydl_opts.setdefault("http_chunk_size", YTDLP_YOUTUBE_HTTP_CHUNK_MB * 1024 * 1024)
        apply_youtube_auth_options(ydl_opts, url)
    else:
        apply_social_auth_options(ydl_opts, url)
    return ydl_opts


def tool_runtime_report() -> dict[str, Any]:
    """Return safe local tool diagnostics without cookie values."""
    report: dict[str, Any] = {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffmpeg_path": shutil.which("ffmpeg") or "",
        "js_runtimes_configured": list(_configured_js_runtimes().keys()),
        "node_path": shutil.which("node") or "",
        "node_version": "",
    }
    node = shutil.which("node")
    if node:
        try:
            report["node_version"] = subprocess.check_output([node, "--version"], text=True, timeout=3).strip()
        except Exception:
            report["node_version"] = "unknown"
    try:
        import yt_dlp  # type: ignore

        report["yt_dlp_version"] = getattr(yt_dlp.version, "__version__", "unknown")
    except Exception:
        report["yt_dlp_version"] = "not installed"
    return report


def safe_cookie_report_for_response(report: dict[str, Any]) -> dict[str, Any]:
    """Strip any fields that could accidentally expose cookie values.

    The current report never contains values, but keeping a response-specific
    sanitizer makes diagnostics safer to extend later.
    """
    safe = dict(report)
    safe["auth_cookie_names"] = list(safe.get("auth_cookie_names") or [])
    return safe


def pretty_cookie_summary(url: str) -> str:
    report = cookiefile_report(url)
    if not report["exists"]:
        return f"cookies=no expected={report['expected_path']}"
    auth = len(report.get("auth_cookie_names") or [])
    return (
        f"cookies=yes file={report['selected_path']} netscape={report['is_netscape']} "
        f"rows={report['cookie_count']} auth_names={auth}"
    )
