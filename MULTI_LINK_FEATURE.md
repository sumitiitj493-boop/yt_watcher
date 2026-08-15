# Multi-Link Batch + Transcripts-Only Mode

Two additions to the batch download system:

## 1. Multi-link batch — paste many URLs at once

A new **"Download Many Links at Once"** panel on the Download page (above the
playlist panel):

- Paste as many URLs as you want, **one per line** — any platform (YouTube,
  Vimeo, Instagram, etc.).
- They go into the download queue **in the same order** you typed them.
- All the same options as the playlist feature:
  - **Quality / format**
  - **Download one by one** (sequential) — or uncheck to push all at once
  - **Also fetch YouTube auto transcript** for each link (parallel)
  - **Auto-save into which playlist?** (existing or create new)
  - **Save transcripts into folder** (empty = General / first-come-first-serve)
  - **Transcripts only** — fetch directly from YouTube, **no download, no Whisper**

Backend: `POST /api/multi-download` with `{ urls: [...], quality, format,
target_playlist_id, sequential, fetch_transcripts, transcript_folder,
transcripts_only }`. It creates the same batch object used by playlists, so the
progress card, cancel, retry and auto-save all work identically. YouTube ids are
extracted from each URL (`watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`) so
saved transcripts are keyed correctly; non-YouTube links still download fine.

## 2. Transcripts-only mode — whole-playlist transcripts without downloading

In the **playlist** panel (and the multi-link panel) there is now a
**"Transcripts only — fetch directly from YouTube, no download, no Whisper"**
checkbox:

- Pick your range/specific videos, tick transcripts-only, choose a folder →
- The backend fetches every selected video's **YouTube auto transcript directly**
  (fast) and saves it into the Transcript Saver under your folder.
- **No video download happens** (so no slow Whisper fallback ever).
- Works for a whole playlist in one go.

Backend: `transcripts_only: true` on `POST /api/playlist/download` (or
`/api/multi-download`). The batch's progress card shows transcript counts
(`3/3 transcripts saved → "My Folder"`) instead of download counts.

> This is exactly the fast path you wanted: as long as the link is available,
> transcripts come straight from YouTube captions — Whisper is never involved.

## Files changed

- `backend/models.py` — `MultiDownloadRequest`, `transcripts_only` on playlist request
- `backend/routes/playlist_batch.py` — `POST /api/multi-download`, passes `transcripts_only`
- `backend/services/playlist_batch.py` — `create_multi_batch`, shared
  `_create_batch_from_entries`, transcript-only phase/progress logic, cancel-aware
  transcript fetcher, real fetched titles for saved transcripts
- `frontend/src/App.jsx` — multi-link panel + progress card, transcripts-only
  checkboxes & wording in both panels

Apply the patch, then **restart the backend** (backend changed) and hard-refresh.
