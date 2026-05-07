# README_FIXES

This document records the final stable downloader fixes for this project.

## Verified tool versions

- `yt-dlp`: `2026.03.17`
- `node`: `v24.13.0`
- `ffmpeg`: required on PATH for merge/post-processing

## Core stability requirements

### 1) YouTube JS challenge solving (EJS)

Keep these options in yt-dlp config (`backend/services/downloader.py`):

- `"js_runtimes": {"node": {}}`
- `"remote_components": ["ejs:github"]`

Why: YouTube often requires JS challenge solving; Node runtime support prevents missing-format / extraction issues.

### 2) Cookies support

If `backend/cookies.txt` exists, it is passed as `cookiefile`.

Why: Some videos/regions/signals need browser-auth cookies for reliable extraction.

### 3) Quality map strategy (stable HD selection)

Use explicit format priority chains per quality (instead of a single fragile selector):

- `1080`: `137+140/248+251/399+140/bestvideo[height=1080]+bestaudio/best`
- `720`: `136+140/247+251/398+140/bestvideo[height=720]+bestaudio/best`
- `480`: `135+140/244+251/bestvideo[height=480]+bestaudio/best`
- `360`: `134+140/243+251/18`
- `240`: `133+140/242+250/best`
- `144`: `160+140/278+249/best`

Why: exact IDs can vary by video; ordered fallbacks preserve quality targets while avoiding silent low-quality collapse.

### 4) MP3 path

For audio downloads:

- `format`: `bestaudio`
- FFmpeg postprocessor extracts MP3 at configured bitrate.

### 5) Merge behavior

Keep:

- `merge_output_format = "mp4"` for non-MP3 outputs.

Why: ensures separate video+audio streams merge into a single playable file.

## Practical note

If debugging format issues again, test with a completely new URL and clear old downloaded files to avoid confusion from cache/history state.
