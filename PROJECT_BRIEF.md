# YT Private Suite - Project Brief

## Purpose

YT Private Suite is a personal local web app for saving, organizing, studying, and clipping video content on your own machine.

## Architecture

- Backend: FastAPI on port `8000`
- Frontend: React/Vite on port `8080`
- Downloader: `yt-dlp`
- Database: SQLite managed by backend services
- Storage: local `backend/downloads/`
- Scope: private/local use

## Core Features

- Video and playlist downloads with progress tracking.
- Multi-link batch downloads.
- Local media library with search, delete, preview, storage, and playlist actions.
- Saved transcripts with folders, editing, search, refetch, and URL fetch.
- Local playlist manager with continuous playback.
- Clip Studio for precise video clipping and clip history.
- Audio extraction and Whisper transcription flows.
- Instagram/social cookie support for logged-in downloads.
- Browser extension files for optional YouTube ad hiding.

## Important Paths

```text
backend/main.py                     FastAPI app entry point
backend/models.py                   API request/response models
backend/routes/                     HTTP and websocket route modules
backend/services/                   Download, transcript, clip, file, and database logic
frontend/src/App.jsx                Main app shell and route wiring
frontend/src/pages/                 Feature pages
frontend/src/components/            Shared UI components
testing/                            Backend/API tests and repro scripts
extension/                          Optional browser extension
```

## Run Locally

Windows:

```bat
start.bat
```

Linux/macOS:

```bash
./start.sh
```

Open `http://localhost:8080`.

## Notes

This project is intentionally local-first. Keep cookies, downloads, logs, virtual environments, generated builds, and SQLite databases out of Git.
