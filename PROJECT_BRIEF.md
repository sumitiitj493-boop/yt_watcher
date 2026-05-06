# YT Private Suite — Project Brief

## What this is
A personal, local web application with two main features:
1. Download any YouTube video (any quality, format, subtitles, playlists)
2. Watch YouTube videos in a clean, ad-free environment with study tools

## Architecture
- Backend: Python FastAPI server (port 8000)
- Frontend: React/Vite app (port 5173)
- Engine: yt-dlp for all downloading
- Player: Plyr.js for video playback
- Database: SQLite for metadata and notes
- Runs fully locally — no cloud, no cost

## Key Features
- Download: URL input → quality/format picker → real-time progress → saved to /downloads
- Ad-free viewer: YouTube videos embedded via iframe API, ad domains blocked via browser extension
- Study mode: fullscreen player, notes panel with timestamps, A-B loop repeat
- Library: browse, search, play, delete downloaded videos
- Subtitles: auto-downloaded with every video

## File Structure
yt-private-suite/
│
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── routes/
│   │   ├── download.py      # /download, /status, /cancel
│   │   ├── library.py       # /files, /delete, /search
│   │   └── stream.py        # serve local video files
│   ├── services/
│   │   ├── downloader.py    # yt-dlp wrapper logic
│   │   └── database.py      # SQLite operations
│   ├── models.py            # Pydantic data models
│   ├── requirements.txt
│   └── downloads/           # your saved videos go here
│
├── frontend/
│   ├── src/
...
├── extension/               # Chrome extension (ad blocker)
│   ├── manifest.json
│   ├── background.js        # blocks ad domains
│   └── content.js           # hides ad elements on youtube.com
│
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── README.md

## How to run (development)
cd backend && uvicorn main:app --reload
cd frontend && npm run dev

## How to run (production)
docker-compose up
