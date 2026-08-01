"""Dry-run extractor for an Instagram post to test cookie-based auth.
Run from repo root with the project's venv Python:
    .venv\Scripts\python.exe testing\insta_dryrun.py <url>
"""
import sys
from pathlib import Path
import os

if len(sys.argv) < 2:
    print("Usage: insta_dryrun.py <instagram_url>")
    sys.exit(2)

url = sys.argv[1]
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
# Make backend importable and run with backend cwd so relative paths resolve
sys.path.insert(0, str(BACKEND))
os.chdir(str(BACKEND))

import yt_dlp
from services import yt_dlp_options as ytd_opts

class SimpleLogger:
    def debug(self, msg):
        print("[yt-dlp debug]", msg)
    def warning(self, msg):
        print("[yt-dlp warn]", msg)
    def error(self, msg):
        print("[yt-dlp error]", msg)


def main():
    ydl_opts = {
        "noplaylist": True,
        "skip_download": True,
        "logger": SimpleLogger(),
        "quiet": False,
    }

    # Apply site-specific auth helpers (cookiefile / cookiesfrombrowser)
    try:
        ytd_opts.apply_reliable_ytdlp_options(ydl_opts, url)
        if not ytd_opts.is_youtube_url(url):
            ytd_opts.apply_social_auth_options(ydl_opts, url)
    except Exception as e:
        print("Error preparing ytdlp options:", e)
        return

    print("Using ytdlp options:")
    for k, v in list(ydl_opts.items()):
        if k == 'http_headers':
            print(f"  {k}: (headers)")
        else:
            print(f"  {k}: {v}")

    print("Cookie summary:", ytd_opts.pretty_cookie_summary(url))

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print("Extract succeeded:")
            print("  id:", info.get('id'))
            print("  title:", info.get('title'))
            print("  extractor:", info.get('extractor_key'))
            print("  is_live:", info.get('is_live'))
    except Exception as e:
        print("Extraction failed:")
        print(str(e))
        # Provide helpful Instagram guidance if available
        help_txt = ytd_opts.instagram_error_help(str(e))
        if help_txt:
            print("\nHelp:\n", help_txt)

if __name__ == '__main__':
    main()
