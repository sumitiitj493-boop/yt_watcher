# Premium UI Upgrade

Four quality-of-life features added to the whole app (they work on every page):

## 1. Command palette — `Ctrl+K` (or `Cmd+K`)
- Press **Ctrl+K** anywhere → a fuzzy-search palette opens (VS Code / Spotify style).
- Search across **pages** (Download, Transcripts, Playlist, Library, History, Whisper,
  Audio Extractor, Photos), **quick actions** (toggle theme, open downloads folder,
  start a new download), your **recent downloads** and **saved transcripts**.
- Arrow keys to navigate, **Enter** to run, **Esc** to close. Clicking outside closes it.

## 2. Keyboard shortcuts
- `?` opens a shortcuts help modal (also lists them all).
- Single-letter navigation (when not typing): **D** Download, **T** Transcripts,
  **P** Playlist, **L** Library, **H** History, **W** Whisper, **A** Audio Extractor.
- `Esc` closes popups/overlays.

## 3. Download manager dock
- A floating **green pill (bottom-right)** appears whenever anything is downloading —
  including videos queued by playlist batches.
- Click it to expand: every active download with title, live progress bar, % and a
  per-item **cancel** button. "Open History" link at the bottom.
- Auto-collapses when the queue empties. The app now polls downloads continuously
  (cheap) so the dock and the sidebar History badge stay accurate at all times.

## 4. Scroll polish
- **Scroll-to-top button** (bottom-left) appears once you scroll down the page —
  click to smooth-scroll back to the top.
- **Scroll resets to top automatically** when you switch pages (previously you could
  land mid-page after navigating).

---

## Files changed

- `frontend/src/components/CommandPalette.jsx` *(new)*
- `frontend/src/components/DownloadDock.jsx` *(new)*
- `frontend/src/components/ShortcutsModal.jsx` *(new)*
- `frontend/src/App.jsx` — wiring, hotkeys, scroll handling, unconditional download polling
- `frontend/src/App.css` — styles for all of the above

No backend changes. After applying: **hard refresh (Ctrl+F5)** — no backend restart needed.

## Apply order (full list)

1. `playlist_batch_feature_local.patch`
2. `transcript_saver_feature.patch`
3. `transcript_saver_v3.patch`
4. `transcript_saver_v4.patch`
5. `transcript_saver_v5.patch`
6. `transcript_saver_v6.patch`
7. `sidebar_scroll.patch`
8. `ui_premium.patch` (this one)
