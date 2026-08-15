# Stored Links + Playlist Transcript Re-fetch

Two features that make transcripts **never need a re-download**:

## 1. Every download stores its source link (until the file is deleted)

- When a download completes, the app now saves the **source URL** (and video id)
  in a new `file_links` table, keyed by filename.
- The link is removed automatically when the file is deleted.
- Even without a stored link, the app can **reconstruct** the YouTube URL from the
  video id that's always in the filename (`Title (VIDEOID).ext`), and backfills the
  stored link on first use.

## 2. "Fetch Transcripts Again" on the Playlist page (no download, no Whisper)

A new section on the **Playlist page**: pick any saved playlist (e.g. your "dbms"
playlist), choose **All / a range / specific item numbers**, optionally a **folder**
to save into the Transcript Saver, and hit **Fetch transcripts (no download)**.

- The backend reads the playlist's files, gets each one's stored link (or
  reconstructs it), and fetches the **YouTube auto transcript directly** —
  re-downloading nothing.
- Results stream into the Transcript Saver under your chosen folder (empty =
  General / first-come-first-serve).
- A progress card shows per-item status (saved / fetching / unavailable) and a
  **View transcripts** link that jumps to the Transcripts page, pre-filtered to
  that folder.
- This solves your exact scenario: **delete all "dbms" transcripts → re-fetch them
  all (or a range) in seconds.**

## Backend

- `POST /api/playlist/{playlist_id}/transcripts`
  body: `{ "indices": [1,3,5] | null, "transcript_folder": "dbms" }`
  (`indices` = 1-based item positions; omit/null = all)
- New DB table `file_links(filename PK, url, video_id, updated_at)` +
  `save_file_link / get_file_link / delete_file_link`.
- `downloader._mark_completed` stores the link on completion; `library.delete_file`
  removes it on delete.

## Files changed

- `backend/services/database.py` — `file_links` table + CRUD
- `backend/services/downloader.py` — store link on completion
- `backend/routes/library.py` — remove link on file delete
- `backend/services/playlist_batch.py` — `create_local_transcript_batch`
- `backend/routes/playlist_batch.py` — new endpoint
- `backend/models.py` — `PlaylistTranscriptsRequest`
- `frontend/src/pages/Playlist.jsx` — "Fetch Transcripts Again" section

Apply the patch, then **restart the backend** (backend changed) and hard-refresh.
