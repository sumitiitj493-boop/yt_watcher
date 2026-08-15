# Playlist Batch Download — New Feature

Download any range (or specific videos) of a YouTube playlist with **just the playlist
link** — no need to paste every video URL. Each video goes through the download queue
**one by one**, and every finished video is **auto-saved into a playlist you choose**
(your existing playlists or a brand-new one).

---

## How to use it (Download page)

1. Open the **Download** page in the app.
2. Scroll to the **"Download a Range from a Playlist"** panel (at the bottom).
3. Paste **one playlist link**, e.g. `https://www.youtube.com/playlist?list=...`
   → click **Load playlist**. The app lists every video with its number, title and length.
4. Pick what to download:
   - **Range** → enter `From #` and `To #` → **Add range**
   - **Specific numbers** → type `1, 3, 5-8` → **Add**
   - Or just **tick/untick** any videos in the list
5. Choose **quality**, **format**, and under **"Auto-save into which playlist?"** pick
   one of your existing playlists (or **Create new playlist…**).
6. Keep **"Download one by one"** checked to wait for each video before starting the next.
   (Uncheck it to push everything into the queue at once.)
7. Click **Download N videos**.

The batch progress card shows every video's status (Waiting → Queued → Downloading →
Done → *In "My Playlist"*), overall progress, cancel / retry-failed / new-batch buttons,
and refreshes your Library automatically as files land.

---

## New backend endpoints

| Method | Endpoint                          | Purpose                                             |
| ------ | --------------------------------- | --------------------------------------------------- |
| POST   | `/api/playlist/entries`           | Resolve all videos of a playlist from a single URL  |
| POST   | `/api/playlist/download`          | Queue selected indices as a batch (sequential or parallel) |
| GET    | `/api/playlist/batches`           | List recent batches                                 |
| GET    | `/api/playlist/batches/{id}`      | Live status of one batch (per-video progress)       |
| POST   | `/api/playlist/batches/{id}/cancel` | Cancel queued/running tasks in a batch             |
| POST   | `/api/playlist/batches/{id}/retry` | Re-queue the failed/cancelled videos               |

`POST /api/playlist/download` body:

```json
{
  "url": "https://www.youtube.com/playlist?list=...",
  "indices": [1, 2, 3],
  "quality": "1080",
  "format": "mp4",
  "target_playlist_id": 1,
  "sequential": true
}
```

`target_playlist_id` is any local playlist id from `GET /api/playlists` (or `null` to skip auto-save).

---

## Files changed

**Backend**
- `backend/services/playlist_batch.py` *(new)* — playlist resolution, batch store,
  per-batch supervisor, auto-save hook.
- `backend/routes/playlist_batch.py` *(new)* — API endpoints.
- `backend/models.py` — `PlaylistEntriesRequest`, `PlaylistDownloadRequest`.
- `backend/main.py` — register the new router.

**Frontend**
- `frontend/src/App.jsx` — the batch panel UI + handlers + live polling.
- `frontend/src/App.css` — panel styles.
- `frontend/vite.config.js` — `allowedHosts: true` so preview/tunnel hosts work in dev.

**Test**
- `testing/test_playlist_batch_autosave.py` *(new)* — in-process end-to-end test of the
  auto-save path (run from the project root: `python testing/test_playlist_batch_autosave.py`).

---

## Notes & limits

- Only the playlist **link** is needed; the backend resolves the video list itself.
  Unavailable/private entries are skipped but don't break the rest.
- Batches are stored **in memory** (same as the download queue), so restarting the
  backend clears active batch tracking — in-flight downloads themselves are still safe
  (they persist in the download history).
- Videos that fail (e.g. members-only without cookies) are marked **Failed**; use
  **Retry failed** after fixing the cause (e.g. adding `youtube_cookies.txt`).
- Each downloaded video becomes a normal entry in your **Library** and download
  **History** too — it is only *additionally* linked into the chosen playlist.
- Large playlists are fetched in "flat" mode, so loading hundreds of videos is fast.
