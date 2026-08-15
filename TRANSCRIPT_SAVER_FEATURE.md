# Transcripts Page (final design)

The saver is now a **proper page in the sidebar** — the natural fit for this app
(every feature here is a page: Download, History, Whisper, Library, Playlist…).
The floating-sphere/overlay experiment is removed.

---

## How it works

### The "Transcripts" page (sidebar → Transcripts)
- **Sidebar item "Transcripts"** with a live count badge (number of saved transcripts).
- Top panel: **Fetch & save** — paste a YouTube link (+ optional folder) and its auto
  transcript is fetched and saved instantly. No manual save step.
- **Search box** filters by title / text / URL / folder.
- **Folder chips** (All / General / each named folder) filter the list.
- Each saved transcript is a **card** showing the **first few lines** (like a preview).
  Click a card to **read the full transcript**; each card has **Copy**, **Edit** and
  **Delete** buttons.
- **Clear all** (click twice to confirm) empties everything; **Refresh** reloads.

### Automatic saving (you never save manually)
1. **URL Transcript panel (Download page):** paste a link and press **Get Transcript** →
   it fetches, shows the transcript, and **auto-saves it** to Transcripts (General
   folder) with a toast. A **View Transcripts** link next to the panel takes you to the page.
2. **Playlist batch downloads:** tick *"Also fetch YouTube auto transcript"* + enter a
   **folder name** → every video's transcript is fetched **in parallel** with the
   download and saved into that folder. Empty folder = **General** (first-come-first-serve).

### Persistence
Transcripts are stored in the SQLite `saved_transcripts` table. They survive video
deletion, cache clears and page reloads. The sidebar badge updates automatically.

---

## Files changed (this update)

- `frontend/src/pages/Transcripts.jsx` *(new)* — the page component.
- `frontend/src/App.jsx` — sidebar item + badge, `/transcripts` route, removed the
  floating sphere / overlay, URL-Transcript auto-save now notifies the badge, "View
  Transcripts" link.
- `frontend/src/App.css` — page styles; removed sphere/overlay styles.
- `TRANSCRIPT_SAVER_FEATURE.md` — this doc.

(Backend unchanged — the folder-capable `/api/transcript-saver` endpoints from the
previous update are reused as-is.)

## Apply order

1. `playlist_batch_feature_local.patch` (v1 — playlist range download)
2. `transcript_saver_feature.patch` (v2 — saver endpoints + batch auto-transcripts)
3. `transcript_saver_v3.patch` (v3 — folder support)
4. `transcript_saver_v4.patch` (this update — Transcripts page)

> If you already applied v1–v3, just apply `transcript_saver_v4.patch` now.
