# YT Private Suite

A private local downloader, library, transcript, playlist, and clip studio for videos you save on your own machine.

## What It Does

- Download YouTube videos, playlists, multi-link batches, and supported social media posts.
- Save and search local media in the Library.
- Fetch, save, edit, refetch, and organize transcripts.
- Build playlists from downloaded files and play them continuously.
- Cut precise clips from downloaded videos.
- Extract audio and run local Whisper transcription workflows.
- Keep Instagram/social cookies local for private downloads that need a logged-in session.

## Local Ports

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8080`
- Vite proxies `/api` to the backend.

## Run On Windows

```bat
start.bat
```

The launcher checks Python and Node, installs missing dependencies, starts the backend and frontend, then opens `http://localhost:8080`.

For a dependency/startup check without launching:

```bat
start.bat --check
```

## Run On Linux Or macOS

```bash
chmod +x start.sh
./start.sh
```

## Manual Development Run

Backend:

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Private Files

The app stores downloads, logs, cookies, local databases, build output, virtual environments, and temporary files outside Git via `.gitignore`.

Cookie files must stay local:

- `backend/youtube_cookies.txt`
- `backend/instagram_cookies.txt`
- `backend/cookies.txt`

For YouTube members-only/private videos, the backend also tries local browser
cookies automatically when no cookie file is present, and when a YouTube 403
stream retry is needed. By default it tries `firefox,chrome,edge,brave,opera`.
Override this with `YOUTUBE_COOKIES_BROWSER=firefox,chrome` or disable it with
`YOUTUBE_COOKIES_BROWSER=off`.

## Final Checks

```bash
cd frontend
npm run lint
npm run build

cd ..
python -m compileall backend
```

Python tests live in `testing/`, but `pytest` is not included in `backend/requirements.txt` by default.

To run the test suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest testing
```
