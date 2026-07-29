"""Quick local pre-flight test for members-only YouTube access.

Usage:
    python check_youtube_access.py "https://www.youtube.com/watch?v=VIDEO_ID"

It prints cookie/tool diagnostics and tests metadata access with yt-dlp.
Cookie values are never printed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from either project root or backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.youtube_access import check_youtube_access_sync  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python check_youtube_access.py <youtube-url>")
        return 2

    result = check_youtube_access_sync(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
