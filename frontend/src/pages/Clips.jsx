import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  Clapperboard,
  Clock,
  Crop,
  Download,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Scissors,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { API_BASE, api } from '../lib/api';

const VIDEO_EXTS = new Set(['mp4', 'webm', 'mkv', 'mov', 'm4v', 'avi', 'mpeg', 'mpg', 'ts', 'wmv', '3gp']);

const formatSec = (sec) => {
  const s = Math.max(0, Number(sec) || 0);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const secs = Math.floor(s % 60);
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(secs).padStart(2, '0')}` : `${m}:${String(secs).padStart(2, '0')}`;
};

function fmtBytes(bytes) {
  if (!bytes) return '';
  const mb = bytes / 1024 / 1024;
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(1)} MB`;
}

export default function ClipsPage({ files, onNotify, onClipsChanged }) {
  const [clips, setClips] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCollection, setActiveCollection] = useState('all');
  const [clipQuery, setClipQuery] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [playingId, setPlayingId] = useState(null);

  // Creator state
  const videoFiles = useMemo(
    () => (files || []).filter((f) => VIDEO_EXTS.has((f.ext || String(f.filename || '').split('.').pop() || '').toLowerCase())),
    [files],
  );
  // Playlists (used to organize the video picker by folder)
  const [allPlaylists, setAllPlaylists] = useState([]);
  useEffect(() => {
    api.get('/playlists')
      .then((res) => setAllPlaylists(Array.isArray(res.data?.playlists) ? res.data.playlists : []))
      .catch(() => setAllPlaylists([]));
  }, []);
  // map filename -> playlist names it belongs to
  const [playlistItemsMap, setPlaylistItemsMap] = useState({});
  useEffect(() => {
    if (!allPlaylists.length) return;
    let active = true;
    Promise.all(allPlaylists.map((p) => api.get(`/playlists/${p.id}/items`).catch(() => ({ data: [] }))))
      .then((responses) => {
        if (!active) return;
        const map = {};
        responses.forEach((res, idx) => {
          const name = allPlaylists[idx]?.name || 'Playlist';
          (res.data || []).forEach((filename) => {
            if (!map[filename]) map[filename] = [];
            map[filename].push(name);
          });
        });
        setPlaylistItemsMap(map);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [allPlaylists]);

  // Search + folder filter for the video picker
  const [pickerQuery, setPickerQuery] = useState('');
  const [pickerFolder, setPickerFolder] = useState('all');
  const [pickerOpen, setPickerOpen] = useState(false);
  const pickerRef = useRef(null);

  const filteredVideoFiles = useMemo(() => {
    const needle = pickerQuery.trim().toLowerCase();
    return videoFiles.filter((f) => {
      if (pickerFolder !== 'all') {
        const folders = playlistItemsMap[f.filename] || [];
        if (pickerFolder === 'unfiled') {
          if (folders.length > 0) return false;
        } else if (!folders.includes(pickerFolder)) {
          return false;
        }
      }
      if (!needle) return true;
      const title = (f.title || f.filename || '').toLowerCase();
      const filename = (f.filename || '').toLowerCase();
      return title.includes(needle) || filename.includes(needle);
    });
  }, [videoFiles, pickerQuery, pickerFolder, playlistItemsMap]);

  const pickerFolders = useMemo(() => {
    const set = new Set();
    videoFiles.forEach((f) => {
      (playlistItemsMap[f.filename] || []).forEach((name) => set.add(name));
    });
    return ['all', 'unfiled', ...[...set].sort((a, b) => a.localeCompare(b))];
  }, [videoFiles, playlistItemsMap]);

  const folderLabel = (folder) => {
    if (folder === 'all') return 'All videos';
    if (folder === 'unfiled') return 'No folder';
    return folder;
  };

  useEffect(() => {
    const onClickOutside = (event) => {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) setPickerOpen(false);
    };
    if (pickerOpen) document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [pickerOpen]);

  const [selectedFile, setSelectedFile] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [startSec, setStartSec] = useState(0);
  const [endSec, setEndSec] = useState(60);
  const [startInput, setStartInput] = useState('0:00');
  const [endInput, setEndInput] = useState('1:00');
  const [clipTitle, setClipTitle] = useState('');
  const [collection, setCollection] = useState('');
  const [targetPlaylist, setTargetPlaylist] = useState('');
  const [clipMode, setClipMode] = useState('smart'); // 'fast' | 'smart' (recommended) | 'accurate'
  const [creating, setCreating] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const previewRef = useRef(null);
  const stopRef = useRef(false);

  const loadClips = useCallback(async () => {
    try {
      const res = await api.get('/clips');
      setClips(Array.isArray(res.data?.clips) ? res.data.clips : []);
    } catch {
      // quiet
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadClips().finally(() => setLoading(false));
    api.get('/playlists')
      .then((res) => setPlaylists(Array.isArray(res.data?.playlists) ? res.data.playlists : []))
      .catch(() => setPlaylists([]));
  }, [loadClips]);

  const collections = useMemo(() => {
    const set = new Set();
    clips.forEach((c) => set.add((c.collection || '').trim()));
    return ['all', ...[...set].filter(Boolean).sort((a, b) => a.localeCompare(b))];
  }, [clips]);

  const filtered = useMemo(() => {
    let list = clips;
    if (activeCollection !== 'all') {
      list = list.filter((c) => (c.collection || '').trim() === activeCollection);
    }
    const needle = clipQuery.trim().toLowerCase();
    if (needle) {
      list = list.filter((c) =>
        [c.title, c.collection, c.filename, c.source_filename]
          .filter(Boolean)
          .some((v) => String(v).toLowerCase().includes(needle)),
      );
    }
    return list;
  }, [clips, activeCollection, clipQuery]);

  const parseTime = (text) => {
    const parts = String(text || '').split(':').map((p) => parseFloat(p));
    if (parts.length === 1 && Number.isFinite(parts[0])) return parts[0];
    if (parts.length === 2 && parts.every(Number.isFinite)) return parts[0] * 60 + parts[1];
    if (parts.length === 3 && parts.every(Number.isFinite)) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return NaN;
  };

  const handleAnalyze = async () => {
    if (!selectedFile || analyzing) return;
    setAnalyzing(true);
    setError('');
    setAnalysis(null);
    try {
      const res = await api.post('/clips/analyze', { filename: selectedFile });
      const data = res.data || {};
      setAnalysis(data);
      setEndSec(Math.min(60, data.duration || 60));
      setEndInput(formatSec(Math.min(60, data.duration || 60)));
      if (!clipTitle) setClipTitle(String(selectedFile).replace(/\.\w+$/, '').replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, ''));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to analyze video');
    } finally {
      setAnalyzing(false);
    }
  };

  const duration = analysis?.duration || 0;

  const applyStartInput = () => {
    const v = parseTime(startInput);
    if (!Number.isFinite(v) || v < 0) return;
    const clamped = Math.min(v, endSec > 0 ? endSec - 0.5 : duration);
    setStartSec(Math.max(0, clamped));
  };

  const applyEndInput = () => {
    const v = parseTime(endInput);
    if (!Number.isFinite(v) || v <= 0) return;
    const clamped = Math.min(v, duration || v);
    setEndSec(Math.max(clamped, startSec + 0.5));
  };

  const handleStartSlider = (value) => {
    const v = Number(value);
    setStartSec(v);
    setStartInput(formatSec(v));
    if (previewRef.current && duration) previewRef.current.currentTime = v;
    if (endSec <= v) {
      const newEnd = Math.min(v + 5, duration || v + 5);
      setEndSec(newEnd);
      setEndInput(formatSec(newEnd));
    }
  };

  const handleEndSlider = (value) => {
    const v = Number(value);
    setEndSec(v);
    setEndInput(formatSec(v));
    if (previewRef.current && duration) previewRef.current.currentTime = v;
  };

  const handleCreate = async () => {
    if (!selectedFile || !analysis || creating || job) return;
    if (endSec <= startSec) {
      setError('End time must be after start time');
      return;
    }
    setCreating(true);
    setError('');
    try {
      const res = await api.post('/clips', {
        filename: selectedFile,
        start_seconds: startSec,
        end_seconds: endSec,
        title: clipTitle.trim(),
        collection: collection.trim(),
        target_playlist_id: targetPlaylist ? Number(targetPlaylist) : null,
        mode: clipMode,
      });
      stopRef.current = false;
      setJob({ job_id: res.data?.job_id, status: 'queued', progress: 0, message: 'Queued' });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to cut clip');
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    if (!job?.job_id) return undefined;
    let active = true;
    let timer = null;
    const poll = async () => {
      if (stopRef.current || !active) return;
      try {
        const res = await api.get(`/clips/job/${job.job_id}`);
        if (!active) return;
        setJob(res.data || {});
        if (['completed', 'error'].includes(res.data?.status)) {
          stopRef.current = true;
          if (res.data?.status === 'completed') {
            await loadClips();
            if (onClipsChanged) onClipsChanged();
          }
        } else {
          timer = window.setTimeout(poll, 1200);
        }
      } catch {
        if (!active) return;
        timer = window.setTimeout(poll, 2500);
      }
    };
    poll();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [job?.job_id, loadClips, onClipsChanged]);

  const resetCreator = () => {
    setJob(null);
    stopRef.current = false;
    setSelectedFile('');
    setAnalysis(null);
    setStartSec(0);
    setEndSec(60);
    setStartInput('0:00');
    setEndInput('1:00');
    setClipTitle('');
    setCollection('');
    setTargetPlaylist('');
    setError('');
  };

  // "New clip" — cut another clip from the SAME video: keep the source,
  // clear the range/job/title, and re-analyze instantly.
  const startNewClipFromSame = async () => {
    if (!selectedFile) return;
    setJob(null);
    stopRef.current = false;
    setStartSec(0);
    setEndSec(Math.min(60, duration || 60));
    setStartInput('0:00');
    setEndInput(formatSec(Math.min(60, duration || 60)));
    setClipTitle('');
    setCollection('');
    setTargetPlaylist('');
    setError('');
    setAnalysis(null);
    // Re-run the analysis so the timeline resets to the full video.
    try {
      const res = await api.post('/clips/analyze', { filename: selectedFile });
      setAnalysis(res.data || {});
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to re-analyze');
    }
  };

  const handleDelete = async (clip) => {
    if (confirmDeleteId === clip.id) {
      try {
        await api.delete(`/clips/${clip.id}`);
        setConfirmDeleteId(null);
        await loadClips();
        if (onClipsChanged) onClipsChanged();
      } catch {
        // quiet
      }
    } else {
      setConfirmDeleteId(clip.id);
      window.setTimeout(() => setConfirmDeleteId(null), 3000);
    }
  };

  const clipUrl = (clip) => `${API_BASE}/stream/${encodeURIComponent(clip.filename)}`;

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Clip Studio</h1>
          <p className="page-subtitle">
            Cut precise clips from any downloaded video. Pick the range on the timeline
            (or type exact timestamps), name it, and it's saved here — ready to play or download.
          </p>
        </div>
        <div className="page-header__actions">
          <button className="ghost-button" type="button" onClick={() => { loadClips(); }}>
            <RefreshCw size={16} /> Refresh
          </button>
          <span className="panel__badge panel__badge--soft">{clips.length} clip{clips.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      {/* Creator */}
      <section className="panel panel--form">
        <div className="panel__header panel__header--stacked">
          <div>
            <div className="section-eyebrow section-eyebrow--soft">Create a clip</div>
            <h2 className="panel__title">Cut a video clip</h2>
            <p className="panel__subtitle">
              Choose a downloaded video — the app analyzes its total length, then you select the
              exact range on a continuous timeline (or type timestamps) and cut.
            </p>
          </div>
          <span className="panel__badge panel__badge--soft">Scissors</span>
        </div>

        <div className="download-form">
          <div className="form-grid">
            <div className="field">
              <label className="field__label" htmlFor="clip-file">VIDEO</label>
              <div className="clip-picker" ref={pickerRef}>
                <button className="clip-picker__trigger" type="button" onClick={() => setPickerOpen((v) => !v)}>
                  <span className="clip-picker__trigger-text">
                    {selectedFile
                      ? videoFiles.find((f) => f.filename === selectedFile)?.title || selectedFile
                      : 'Select a downloaded video…'}
                  </span>
                  <span className="clip-picker__trigger-count">{videoFiles.length} video{videoFiles.length === 1 ? '' : 's'}</span>
                </button>

                {pickerOpen ? (
                  <div className="clip-picker__dropdown">
                    <div className="clip-picker__search">
                      <Search size={14} className="clip-picker__search-icon" />
                      <input
                        className="input input--search"
                        value={pickerQuery}
                        onChange={(event) => setPickerQuery(event.target.value)}
                        placeholder="Search videos by name…"
                        autoFocus
                      />
                    </div>
                    <div className="clip-picker__folders">
                      {pickerFolders.map((folder) => (
                        <button
                          key={folder}
                          type="button"
                          className={`clip-picker__folder ${pickerFolder === folder ? 'clip-picker__folder--active' : ''}`}
                          onClick={() => setPickerFolder(folder)}
                        >
                          {folderLabel(folder)}
                        </button>
                      ))}
                    </div>
                    <div className="clip-picker__list">
                      {filteredVideoFiles.length === 0 ? (
                        <div className="clip-picker__empty">No videos match</div>
                      ) : (
                        filteredVideoFiles.map((f) => (
                          <button
                            key={f.filename}
                            type="button"
                            className={`clip-picker__option ${selectedFile === f.filename ? 'clip-picker__option--active' : ''}`}
                            onClick={() => {
                              setSelectedFile(f.filename);
                              setAnalysis(null);
                              setError('');
                              setPickerOpen(false);
                            }}
                          >
                            <span className="clip-picker__option-title">{f.title || f.filename}</span>
                            {(playlistItemsMap[f.filename] || []).length > 0 ? (
                              <span className="clip-picker__option-folder">{playlistItemsMap[f.filename].join(', ')}</span>
                            ) : null}
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
            <div className="field">
              <label className="field__label" htmlFor="clip-title">CLIP TITLE</label>
              <input id="clip-title" className="input" value={clipTitle} onChange={(e) => setClipTitle(e.target.value)} placeholder="e.g. Intro Highlights" maxLength={200} />
            </div>
          </div>

          {selectedFile ? (
            <div className="transcript-actions">
              <button className="ghost-button" type="button" onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? <Loader2 className="spin" size={16} /> : <Clapperboard size={16} />}
                {analyzing ? 'Analyzing…' : analysis ? 'Re-analyze' : 'Analyze video'}
              </button>
            </div>
          ) : null}

          {error ? <p className="download-card__error">{error}</p> : null}

          {analysis ? (
            <div className="clip-creator">
              <div className="clip-creator__meta">
                <span className="status-pill status-pill--processing">Total: {analysis.duration_label}</span>
                {analysis.width ? <span className="status-pill status-pill--processing">{analysis.width}×{analysis.height}</span> : null}
                <span className="status-pill status-pill--processing">{fmtBytes(analysis.size_bytes)}</span>
              </div>

              {/* Preview player */}
              <div className="clip-creator__preview-wrap">
                <video
                  ref={previewRef}
                  className="clip-creator__preview"
                  src={`${API_BASE}/stream/${encodeURIComponent(selectedFile)}`}
                  controls
                  preload="metadata"
                />
                <span className="clip-creator__preview-time">
                  {startSec > 0 ? `${formatSec(startSec)} – ` : ''}{formatSec(endSec)} / {formatSec(duration)}
                </span>
              </div>

              {/* Timeline */}
              <div className="clip-creator__timeline">
                <div className="clip-creator__range-label">
                  <span>Start <strong>{formatSec(startSec)}</strong></span>
                  <span>End <strong>{formatSec(endSec)}</strong></span>
                  <span>Clip <strong className="clip-creator__len">{formatSec(Math.max(0, endSec - startSec))}</strong></span>
                </div>
                <div className="clip-creator__slider-row">
                  <input
                    type="range"
                    min={0}
                    max={duration || 1}
                    step={0.5}
                    value={startSec}
                    onChange={(e) => handleStartSlider(e.target.value)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                  <input
                    type="range"
                    min={0}
                    max={duration || 1}
                    step={0.5}
                    value={endSec}
                    onChange={(e) => handleEndSlider(e.target.value)}
                    style={{ accentColor: 'var(--accent-cool)' }}
                  />
                </div>
                <div className="clip-creator__time-inputs">
                  <label>
                    <Clock size={13} /> Start
                    <input className="input input--num" value={startInput} onChange={(e) => setStartInput(e.target.value)} onBlur={applyStartInput} onKeyDown={(e) => { if (e.key === 'Enter') applyStartInput(); }} placeholder="0:00" />
                  </label>
                  <label>
                    <Clock size={13} /> End
                    <input className="input input--num" value={endInput} onChange={(e) => setEndInput(e.target.value)} onBlur={applyEndInput} onKeyDown={(e) => { if (e.key === 'Enter') applyEndInput(); }} placeholder="1:00" />
                  </label>
                  <button
                    className="ghost-button ghost-button--small"
                    type="button"
                    onClick={() => { applyStartInput(); applyEndInput(); }}
                    title="Apply the typed timestamps to the timeline"
                  >
                    <Check size={14} /> Apply
                  </button>
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label className="field__label" htmlFor="clip-collection">COLLECTION (optional, like a folder)</label>
                  <input id="clip-collection" className="input" value={collection} onChange={(e) => setCollection(e.target.value)} placeholder="e.g. DBMS Course — empty = General" maxLength={120} />
                </div>
                <div className="field">
                  <label className="field__label" htmlFor="clip-playlist">ALSO ADD TO PLAYLIST (optional)</label>
                  <select id="clip-playlist" className="select" value={targetPlaylist} onChange={(e) => setTargetPlaylist(e.target.value)}>
                    <option value="">None</option>
                    {playlists.map((p) => (
                      <option key={p.id} value={String(p.id)}>{p.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {job ? (
                <div className="converter-progress">
                  <div className="converter-progress__row">
                    <span>{job.message || 'Cutting…'}</span>
                    <span className="converter-progress__right">
                      {job.eta_seconds != null && job.status !== 'completed' ? (
                        <span className="clip-progress__eta">⏱ {job.eta_seconds}s left</span>
                      ) : null}
                      <span>{job.progress ?? 0}%</span>
                    </span>
                  </div>
                  <div className="dock__bar">
                    <div className="dock__bar-fill" style={{ width: `${job.progress ?? 0}%` }} />
                  </div>
                  {job.status === 'completed' ? (
                    <div className="clip-creator__done-wrap">
                      <p className="clip-creator__done">✓ Clip saved{job.filename ? `: ${job.filename}` : ''}</p>
                      <button className="primary-button" type="button" onClick={startNewClipFromSame}>
                        <Plus size={16} /> New clip from same video
                      </button>
                    </div>
                  ) : job.status === 'error' ? (
                    <p className="download-card__error">{job.error}</p>
                  ) : null}
                </div>
              ) : (
                <>
                  <div className="clip-mode-toggle">
                    <button
                      type="button"
                      className={`clip-mode-toggle__btn ${clipMode === 'fast' ? 'clip-mode-toggle__btn--active' : ''}`}
                      onClick={() => setClipMode('fast')}
                    >
                      ⚡ Fast (instant)
                    </button>
                    <button
                      type="button"
                      className={`clip-mode-toggle__btn clip-mode-toggle__btn--recommended ${clipMode === 'smart' ? 'clip-mode-toggle__btn--active' : ''}`}
                      onClick={() => setClipMode('smart')}
                    >
                      ✨ Smart (exact) ★
                    </button>
                    <button
                      type="button"
                      className={`clip-mode-toggle__btn ${clipMode === 'accurate' ? 'clip-mode-toggle__btn--active' : ''}`}
                      onClick={() => setClipMode('accurate')}
                    >
                      🎯 Accurate (max precision)
                    </button>
                    <span className="clip-mode-toggle__hint">
                      {clipMode === 'fast'
                        ? 'No re-encode — copies instantly, cut lands on nearest keyframe (±1–2s).'
                        : clipMode === 'smart'
                          ? 'Recommended: exact timestamps — re-encodes only the tiny start sliver, stream-copies the rest (fast + exact).'
                          : 'Re-encodes video + audio — frame-exact, similar speed to Smart but re-encodes audio too.'}
                    </span>
                  </div>
                  <div className="transcript-actions">
                    <button className="primary-button" type="button" onClick={handleCreate} disabled={creating}>
                      {creating ? <Loader2 className="spin" size={16} /> : <Scissors size={16} />}
                      {creating ? 'Cutting…' : `Cut clip (${formatSec(Math.max(0, endSec - startSec))})`}
                    </button>
                    <button className="ghost-button" type="button" onClick={resetCreator}><X size={16} /> Reset</button>
                  </div>
                </>
              )}
            </div>
          ) : null}
        </div>
      </section>

      {/* Clips list */}
      <section className="panel panel--list">
        <div className="panel__header">
          <div>
            <h2 className="panel__title">Saved clips</h2>
            <p className="panel__subtitle">
              {filtered.length} clip{filtered.length === 1 ? '' : 's'}
              {activeCollection !== 'all' ? ` in "${activeCollection}"` : ''}
            </p>
          </div>
          <span className="panel__badge">{filtered.length}</span>
        </div>

        <div className="clips-toolbar">
          <div className="search-box">
            <Search size={15} className="search-box__icon" />
            <input
              className="input input--search"
              value={clipQuery}
              onChange={(event) => setClipQuery(event.target.value)}
              placeholder="Search clips by name…"
            />
          </div>
          <div className="transcript-folder-chips">
            {collections.map((c) => (
              <button
                key={c}
                type="button"
                className={`transcript-folder-chip ${activeCollection === c ? 'transcript-folder-chip--active' : ''}`}
                onClick={() => setActiveCollection(c)}
              >
                {c === 'all' ? 'All' : c}
                <span className="transcript-folder-chip__count">
                  {c === 'all' ? clips.length : clips.filter((x) => (x.collection || '').trim() === c).length}
                </span>
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="empty-state"><p>Loading clips…</p></div>
        ) : clips.length === 0 ? (
          <div className="empty-state">
            <Clapperboard size={32} />
            <p>No clips yet. Pick a video above, choose a range on the timeline, and cut your first clip!</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <p>{clipQuery.trim() ? 'No clips match your search.' : 'No clips in this collection yet.'}</p>
          </div>
        ) : (
          <div className="clips-grid">
            {filtered.map((clip) => (
              <article key={clip.id} className="download-card">
                <div className="clip-card">
                  <div className="clip-card__head">
                    <div className="clip-card__title">
                      <h3 className="download-card__title">{clip.title}</h3>
                      <span className="download-card__meta">
                        {clip.collection ? `${clip.collection} · ` : 'General · '}
                        {formatSec(clip.start_seconds)} → {formatSec(clip.end_seconds)} · {formatSec(clip.duration_seconds)} · {fmtBytes(clip.size_bytes)}
                      </span>
                    </div>
                    <div className="clip-card__actions">
                      <button className="icon-button" type="button" title={playingId === clip.id ? 'Pause' : 'Play'} onClick={() => setPlayingId(playingId === clip.id ? null : clip.id)}>
                        {playingId === clip.id ? <Pause size={15} /> : <Play size={15} />}
                      </button>
                      <a className="icon-button" href={`${API_BASE}/files/download/${encodeURIComponent(clip.filename)}`} download title="Download clip" onClick={(e) => e.stopPropagation()}>
                        <Download size={15} />
                      </a>
                      <button className={`icon-button ${confirmDeleteId === clip.id ? 'icon-button--danger clip-card__confirm' : 'icon-button--danger'}`} type="button" title={confirmDeleteId === clip.id ? 'Click again to confirm' : 'Delete clip'} onClick={() => handleDelete(clip)}>
                        {confirmDeleteId === clip.id ? <X size={15} /> : <Trash2 size={15} />}
                      </button>
                    </div>
                  </div>
                  {playingId === clip.id ? (
                    <video className="clip-card__player" src={clipUrl(clip)} controls autoPlay preload="metadata" />
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
