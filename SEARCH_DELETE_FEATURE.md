# Subtitle Search + Clean Deletion Model

Two improvements that fix the daily pain of big playlists and confusing deletes.

## 1. Find a video by pasting its subtitle

Inside the Playlist page's **"Fetch Transcripts Again"** panel there is now a
**"Find a video by pasting a subtitle line"** search:

- Paste any transcript/subtitle text (e.g. *"mitochondria is the powerhouse"*)
  and click **Find video**.
- The app searches the **saved transcripts** of the active playlist's videos
  (fast). If nothing matches and some videos have no saved transcript, it
  **fetches their YouTube transcripts on the fly** (small concurrency) and
  checks those too.
- Results show the matching video with a **snippet** of where the text appears;
  click a result → it **jumps to that video in the playlist and starts playing**.

Backend: `POST /api/search-by-transcript`
`{ query, playlist_id, fetch_missing: true, limit: 20 }`
→ `{ matches: [{filename, title, video_id, snippet, source}], checked, fetched_missing, no_transcript }`
(no `playlist_id` = search the whole Library.)

## 2. One consistent deletion model

Previously: deleting from a playlist kept the file on your PC and in the
Library; deleting from the Library left dangling playlist entries. Now:

| Action | Result |
|---|---|
| **Delete from a playlist** | File is **permanently deleted** from disk, Library, and every other playlist (two-click confirm warns you) |
| **Delete from Library** | File deleted **and removed from all playlists** |
| **Clear Library** | Same clean-up for every file |
| **File in a playlist** | **Hidden from the Library grid** by default (they "live" in the playlist) |

The Library toolbar has a **"Hide playlist files"** toggle (on by default) to
switch between *only non-playlist files* and *everything*. A file that's in a
playlist is flagged `in_playlist` in the API, and each Library card can show
which playlist it belongs to.

Backend changes:
- `DELETE /api/playlists/{id}/items/{filename}` now permanently deletes.
- `DELETE /api/delete/{filename}` and `/api/files/clear` remove the file from
  all playlists too.
- `GET /api/files?hide_playlist=1` returns only non-playlist files.
- New DB helpers: `find_saved_transcript_by_video_id`,
  `playlist_all_filenames`, `remove_file_from_all_playlists`.

## Files changed

- `backend/services/database.py` — helpers
- `backend/routes/library.py` — search endpoint, hide-playlist filter, permanent-delete helper
- `frontend/src/pages/Playlist.jsx` — subtitle search UI, two-click permanent delete
- `frontend/src/App.jsx` — Library "Hide playlist files" toggle
- `frontend/src/App.css` — subtitle search styles

Apply the patch, then **restart the backend** (backend changed) and hard-refresh.
