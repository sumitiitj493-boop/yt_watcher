# Clip Studio — cut precise clips from downloaded videos

A dedicated **Clips** section (sidebar → Clips) where you turn any downloaded
video into short, precise clips — like a mini video editor.

## How to use

### Cut a clip
1. Open **Clips** (sidebar).
2. In **"Cut a video clip"**, pick a downloaded video → click **Analyze video**.
   - The app shows the video's **total duration**, resolution and size.
   - A **preview player** appears so you can watch and scrub.
3. Select the exact range two ways:
   - **Continuous timeline** — two sliders (start & end) spanning the full
     duration; a live label shows `Start / End / Clip length`.
   - **Exact timestamps** — type `0:05` / `10` / `1:02:30` into the Start/End
     boxes and press Enter (or tab out). The sliders and labels sync.
4. Name the clip, optionally pick a **Collection** (like a folder — e.g.
   "DBMS Course") and optionally **also add it to a playlist**.
5. Click **Cut clip (0:05)** → live progress bar → clip saved.

### Your clips
- All saved clips appear below, filterable by **collection chips**.
- Each clip card: play inline, **download**, or **delete** (two-click confirm).
- The sidebar **Clips badge** shows how many clips you have.
- Clips also appear in the **Library** (they're files too) — the original video
  is never touched.

## Backend

- `POST /api/clips/analyze` `{filename}` → duration / resolution / size
- `POST /api/clips` `{filename, start_seconds, end_seconds, title, collection, target_playlist_id}` → job_id
- `GET /api/clips/job/{job_id}` → progress
- `GET /api/clips` → list of saved clips
- `DELETE /api/clips/{id}` → delete clip + file

Cutting uses ffmpeg with `-ss/-t` (accurate) + fast re-encode (`libx264
veryfast`), progress parsed from ffmpeg output. Clips are registered in a new
`clips` SQLite table (title, timestamps, collection, size, source) so they
survive restarts.

## Files changed

- `backend/services/clipper.py` *(new)* — analyze + cut engine
- `backend/services/database.py` — `clips` table + CRUD
- `backend/routes/clipper.py` *(new)* — endpoints
- `backend/models.py` — `ClipAnalyzeRequest`, `ClipCreateRequest`
- `backend/main.py` — register router
- `frontend/src/pages/Clips.jsx` *(new)* — the Clip Studio page
- `frontend/src/App.jsx` — sidebar item + badge + route
- `frontend/src/App.css` — styles

Apply the patch, then **restart the backend** (backend changed) and hard-refresh.
