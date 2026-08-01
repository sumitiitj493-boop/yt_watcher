"""Attempt extraction with force_generic_extractor=True and provided cookie file."""
import sys
from pathlib import Path
import os
if len(sys.argv) < 2:
    print("Usage: insta_force_generic.py <url>")
    sys.exit(2)
url = sys.argv[1]
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
# not importing services; point cookiefile directly
cookiefile = BACKEND / "instagram_cookies.txt"

import yt_dlp

class SimpleLogger:
    def debug(self, msg):
        print("[yt-dlp debug]", msg)
    def warning(self, msg):
        print("[yt-dlp warn]", msg)
    def error(self, msg):
        print("[yt-dlp error]", msg)

ydl_opts = {
    'skip_download': True,
    'logger': SimpleLogger(),
    'force_generic_extractor': True,
}
if cookiefile.exists():
    ydl_opts['cookiefile'] = str(cookiefile)

print('Using cookiefile:', ydl_opts.get('cookiefile'))

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print('Extract succeeded:', info.get('id'), info.get('title'))
except Exception as e:
    print('Extract failed:', e)
    raise
