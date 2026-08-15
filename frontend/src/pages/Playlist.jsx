import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpenText,
  CheckCircle2,
  Download,
  Edit3,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Shuffle,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import { API_BASE, api } from '../lib/api';

const cleanTitle = (filename = '') => (
  filename
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

const mediaExt = (filename = '') => filename.split('.').pop()?.toLowerCase() || '';
const isAudio = (filename = '') => ['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav'].includes(mediaExt(filename));
const isImage = (filename = '') => ['jpg', 'jpeg', 'png', 'webp', 'gif'].includes(mediaExt(filename));
const extractVideoId = (filename = '') => {
  const match = String(filename).match(/\(([A-Za-z0-9_-]{11})\)/);
  return match ? match[1] : '';
};
const formatTime = (seconds = 0) => {
  const safe = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  return `${minutes}:${String(secs).padStart(2, '0')}`;
};

const transcriptWords = (text = '') => String(text).toLowerCase().match(/[a-z0-9']+/g) || [];

const trimRepeatedTranscriptPrefix = (previousText = '', currentText = '') => {
  const previousWords = transcriptWords(previousText);
  const currentWords = transcriptWords(currentText);
  if (!previousWords.length || !currentWords.length) return currentText;

  if (currentWords.length <= previousWords.length) {
    for (let index = 0; index <= previousWords.length - currentWords.length; index += 1) {
      if (currentWords.every((word, offset) => previousWords[index + offset] === word)) return '';
    }
  }

  const maxOverlap = Math.min(previousWords.length, currentWords.length, 50);
  let overlap = 0;
  for (let size = maxOverlap; size >= 1; size -= 1) {
    if (previousWords.slice(previousWords.length - size).every((word, index) => word === currentWords[index])) {
      overlap = size;
      break;
    }
  }

  if (overlap < 2) return currentText;
  if (overlap >= currentWords.length) return '';

  const wordMatches = [...String(currentText).matchAll(/[A-Za-z0-9']+/g)];
  return String(currentText).slice(wordMatches[overlap]?.index || 0).trim();
};

const transcriptSegmentsToText = (segments = []) => {
  const cleaned = [];
  for (const segment of segments || []) {
    let text = String(segment?.text || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const start = Number(segment?.start) || 0;
    const end = Number(segment?.end) || start;
    const previous = cleaned[cleaned.length - 1];
    if (previous && start <= previous.end + 12) {
      text = trimRepeatedTranscriptPrefix(previous.text, text);
      if (!text) {
        previous.end = Math.max(previous.end, end);
        continue;
      }
    }
    cleaned.push({ start, end, text });
  }
  return cleaned.map((segment) => `[${formatTime(segment.start)}] ${segment.text}`).join('\n');
};

const naturalCompare = (left, right) => {
  const leftParts = String(left).match(/\d+|\D+/g) || [];
  const rightParts = String(right).match(/\d+|\D+/g) || [];
  const length = Math.max(leftParts.length, rightParts.length);

  for (let index = 0; index < length; index += 1) {
    const leftPart = leftParts[index];
    const rightPart = rightParts[index];

    if (leftPart === undefined) return -1;
    if (rightPart === undefined) return 1;

    const leftNumber = Number(leftPart);
    const rightNumber = Number(rightPart);
    const leftIsNumber = Number.isFinite(leftNumber) && String(leftNumber) === leftPart;
    const rightIsNumber = Number.isFinite(rightNumber) && String(rightNumber) === rightPart;

    if (leftIsNumber && rightIsNumber && leftNumber !== rightNumber) {
      return leftNumber - rightNumber;
    }

    const comparison = leftPart.localeCompare(rightPart, undefined, { sensitivity: 'base' });
    if (comparison !== 0) return comparison;
  }

  return 0;
};

function PlaylistThumb({ file }) {
  const title = file.title || cleanTitle(file.filename || '');
  const videoId = file.video_id || extractVideoId(file.filename || '');

  if (isImage(file.filename || '')) {
    return (
      <img
        className="media-thumb"
        src={`${API_BASE}/stream/${encodeURIComponent(file.filename)}`}
        alt={title}
        loading="lazy"
        onError={(event) => {
          event.currentTarget.style.display = 'none';
        }}
      />
    );
  }

  if (videoId) {
    return (
      <img
        className="media-thumb"
        src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
        alt={title}
        loading="lazy"
        onError={(event) => {
          event.currentTarget.style.display = 'none';
        }}
      />
    );
  }

  return (
    <div className="media-thumb media-thumb--fallback" aria-hidden="true">
      <div className="media-thumb__title" title={title}>{title || 'Media'}</div>
    </div>
  );
}

export default function PlaylistPage({ files = [], onNotify, onLibraryChanged }) {
  // Multi-playlist state
  const [playlists, setPlaylists] = useState([]);                 // [{ id, name, created_at, item_count }]
  const [activePlaylistId, setActivePlaylistId] = useState(null);
  const [playlist, setPlaylist] = useState([]);                   // filenames of the active playlist
  const [isCreating, setIsCreating] = useState(false);            // inline "create playlist" form
  const [newPlaylistName, setNewPlaylistName] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);            // inline "rename playlist" form
  const [renameValue, setRenameValue] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);   // two-step delete guard

  // Add-from-library state (multi-select)
  const [selectedFilenames, setSelectedFilenames] = useState([]);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [addTarget, setAddTarget] = useState('current');          // 'current' | playlist-id | 'new'
  const [addNewName, setAddNewName] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  // Drag & drop reordering
  const suppressClickRef = useRef(false);
  const [dragIndex, setDragIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const handleDragStart = (index) => (event) => {
    setDragIndex(index);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (index) => (event) => {
    event.preventDefault();
    if (dragIndex !== null && dragOverIndex !== index) setDragOverIndex(index);
  };

  const handleDrop = (index) => async (event) => {
    event.preventDefault();
    const from = dragIndex;
    setDragIndex(null);
    setDragOverIndex(null);
    if (from === null || from === index || from < 0 || from >= playlist.length) return;
    // The browser fires a click after drop — suppress it so dropping doesn't start playback.
    suppressClickRef.current = true;
    const next = [...playlist];
    const [moved] = next.splice(from, 1);
    next.splice(index, 0, moved);
    setCurrentIndex(0);
    saveOrder(next);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  // Player state
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [useCompatiblePlayback, setUseCompatiblePlayback] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [transcriptStatus, setTranscriptStatus] = useState('Get Transcript');
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const playerRef = useRef(null);

  // Re-fetch transcripts for the active playlist (no download)
  const [trFolder, setTrFolder] = useState('');
  const [trRangeFrom, setTrRangeFrom] = useState('');
  const [trRangeTo, setTrRangeTo] = useState('');
  const [trSpecific, setTrSpecific] = useState('');
  const [trStarting, setTrStarting] = useState(false);
  const [trBatchId, setTrBatchId] = useState(null);
  const [trBatch, setTrBatch] = useState(null);

  // Find video by pasted subtitle
  const [subQuery, setSubQuery] = useState('');
  const [subSearching, setSubSearching] = useState(false);
  const [subResults, setSubResults] = useState(null); // { matches, count, fetched_missing, no_transcript }
  const [subError, setSubError] = useState('');
  const trStopRef = useRef(false);

  const trStatusLabel = (status) => {
    const map = {
      pending: 'Transcript queued',
      fetching: 'Fetching transcript…',
      saved: 'Transcript saved',
      unavailable: 'No transcript',
      error: 'Transcript error',
    };
    return map[status] || status || '—';
  };

  const trSelectionIndices = () => {
    if (!activePlaylist) return null;
    const total = playlist.length;
    if (trSpecific.trim()) {
      const wanted = new Set();
      const parts = trSpecific.split(/[,;\s]+/).filter(Boolean);
      for (const part of parts) {
        const range = part.match(/^(\d+)\s*-\s*(\d+)$/);
        if (range) {
          const a = parseInt(range[1], 10);
          const b = parseInt(range[2], 10);
          for (let i = Math.min(a, b); i <= Math.max(a, b); i += 1) {
            if (i >= 1 && i <= total) wanted.add(i);
          }
        } else if (/^\d+$/.test(part)) {
          const n = parseInt(part, 10);
          if (n >= 1 && n <= total) wanted.add(n);
        }
      }
      if (wanted.size === 0) return null;
      return [...wanted].sort((a, b) => a - b);
    }
    if (trRangeFrom.trim() || trRangeTo.trim()) {
      const from = parseInt(trRangeFrom, 10);
      const to = parseInt(trRangeTo, 10);
      if (!Number.isFinite(from) || !Number.isFinite(to)) return null;
      const low = Math.max(1, Math.min(from, to));
      const high = Math.min(total, Math.max(from, to));
      if (low > high) return null;
      const out = [];
      for (let i = low; i <= high; i += 1) out.push(i);
      return out;
    }
    return null; // null = all
  };

  const handleFetchTranscripts = async () => {
    if (!activePlaylistId || trStarting || trBatchId) return;
    const indices = trSelectionIndices();
    if (trSpecific.trim() && !indices) {
      notify('Enter valid item numbers (e.g. 1, 3, 5-8)', 'error');
      return;
    }
    if ((trRangeFrom.trim() || trRangeTo.trim()) && !indices) {
      notify('Enter both a From and a To item number', 'error');
      return;
    }
    setTrStarting(true);
    try {
      const res = await api.post(`/playlist/${activePlaylistId}/transcripts`, {
        indices,
        transcript_folder: trFolder.trim(),
      });
      trStopRef.current = false;
      setTrBatchId(res.data.batch_id);
      setTrBatch(null);
      notify(
        indices
          ? `Fetching ${indices.length} transcript${indices.length === 1 ? '' : 's'} (no download)…`
          : `Fetching transcripts for all ${res.data.task_count} items (no download)…`,
        'success',
      );
    } catch (err) {
      notify(err?.response?.data?.detail || 'Unable to fetch transcripts.', 'error');
    } finally {
      setTrStarting(false);
    }
  };

  useEffect(() => {
    if (!trBatchId) return undefined;
    let active = true;
    let timer = null;
    const poll = async () => {
      if (trStopRef.current || !active) return;
      try {
        const res = await api.get(`/playlist/batches/${trBatchId}`);
        if (!active) return;
        setTrBatch(res.data || {});
        if (['completed', 'partial', 'cancelled'].includes(res.data?.phase)) {
          trStopRef.current = true;
          setTrBatch((prev) => (prev ? { ...prev, finished: true } : prev));
        } else {
          timer = window.setTimeout(poll, 1500);
        }
      } catch {
        if (!active) return;
        timer = window.setTimeout(poll, 3000);
      }
    };
    poll();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [trBatchId]);

  const handleSubtitleSearch = async () => {
    const q = subQuery.trim();
    if (q.length < 2 || subSearching) return;
    setSubSearching(true);
    setSubError('');
    setSubResults(null);
    try {
      const res = await api.post('/search-by-transcript', {
        query: q,
        playlist_id: activePlaylistId,
        fetch_missing: true,
        limit: 20,
      });
      setSubResults(res.data || { matches: [], count: 0 });
    } catch (err) {
      setSubError(err?.response?.data?.detail || 'Unable to search transcripts');
    } finally {
      setSubSearching(false);
    }
  };

  const jumpToSubtitleMatch = (filename) => {
    const idx = playlist.findIndex((item) => item === filename);
    if (idx >= 0) {
      setCurrentIndex(idx);
      setIsPlaying(true);
      window.setTimeout(() => playerRef.current?.play?.(), 0);
    }
  };

  const resetTranscriptFetch = () => {
    setTrBatchId(null);
    setTrBatch(null);
    trStopRef.current = false;
    setTrFolder('');
    setTrRangeFrom('');
    setTrRangeTo('');
    setTrSpecific('');
  };

  const activePlaylist = playlists.find((item) => item.id === activePlaylistId) || null;

  const fileMap = useMemo(() => new Map(files.map((file) => [file.filename, file])), [files]);
  const playlistFiles = useMemo(
    () => playlist.map((filename) => fileMap.get(filename) || { filename, title: cleanTitle(filename), missing: true }),
    [fileMap, playlist],
  );
  const availableFiles = useMemo(
    () => files.filter((file) => !playlist.includes(file.filename)),
    [files, playlist],
  );
  const filteredAvailable = useMemo(() => {
    const needle = libraryQuery.trim().toLowerCase();
    if (!needle) return availableFiles;
    return availableFiles.filter((file) => {
      const title = (file.title || cleanTitle(file.filename || '')).toLowerCase();
      const filename = (file.filename || '').toLowerCase();
      return title.includes(needle) || filename.includes(needle);
    });
  }, [availableFiles, libraryQuery]);
  const currentFile = playlistFiles[currentIndex] || null;
  const currentUrl = currentFile?.filename
    ? `${API_BASE}/${isAudio(currentFile.filename) || !useCompatiblePlayback ? 'stream' : 'stream-compatible'}/${encodeURIComponent(currentFile.filename)}`
    : '';

  const notify = useCallback((message, type = 'info') => {
    if (onNotify) onNotify(message, type);
  }, [onNotify]);

  const loadPlaylists = useCallback(async () => {
    try {
      const response = await api.get('/playlists');
      const list = Array.isArray(response.data?.playlists) ? response.data.playlists : [];
      setPlaylists(list);
      setActivePlaylistId((current) => (
        current !== null && list.some((playlist) => playlist.id === current)
          ? current
          : (list[0]?.id ?? null)
      ));
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to load playlists', 'error');
    }
  }, [notify]);

  const loadItems = useCallback(async (playlistId) => {
    setIsLoading(true);
    try {
      const response = await api.get(`/playlists/${playlistId}/items`);
      setPlaylist(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to load playlist items', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch on mount
    loadPlaylists();
  }, [loadPlaylists]);

  useEffect(() => {
    if (activePlaylistId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- load items for the newly active playlist
      loadItems(activePlaylistId);
    } else {
      setPlaylist([]);
    }
  }, [activePlaylistId, loadItems]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- when no playlists remain, force the "new" target
    if (playlists.length === 0) setAddTarget('new');
  }, [playlists.length]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset player on file change
    setUseCompatiblePlayback(false);
  }, [currentFile?.filename]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset transcript state on file change
    setTranscriptStatus('Get Transcript');
    setTranscriptLoading(false);
  }, [currentFile?.filename]);

  useEffect(() => {
    if (playerRef.current) {
      playerRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate, currentFile?.filename]);

  useEffect(() => {
    if (currentIndex >= playlistFiles.length) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clamp index when list shrinks
      setCurrentIndex(Math.max(0, playlistFiles.length - 1));
    }
  }, [currentIndex, playlistFiles.length]);

  // --- Playlist management ------------------------------------------------
  const createPlaylist = async (name) => {
    const clean = name.trim();
    if (!clean) {
      notify('Enter a playlist name', 'error');
      return;
    }
    try {
      const response = await api.post('/playlists', { name: clean });
      const created = response.data?.playlist;
      await loadPlaylists();
      if (created?.id) setActivePlaylistId(created.id);
      setIsCreating(false);
      setNewPlaylistName('');
      notify(`Playlist "${clean}" created`, 'success');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to create playlist', 'error');
    }
  };

  const renamePlaylist = async (playlistId, name) => {
    const clean = name.trim();
    if (!clean) {
      notify('Enter a playlist name', 'error');
      return;
    }
    try {
      await api.patch(`/playlists/${playlistId}`, { name: clean });
      await loadPlaylists();
      setIsRenaming(false);
      setRenameValue('');
      notify('Playlist renamed', 'success');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to rename playlist', 'error');
    }
  };

  const deletePlaylist = async (playlistId) => {
    try {
      await api.delete(`/playlists/${playlistId}`);
      setConfirmDeleteId(null);
      if (activePlaylistId === playlistId) {
        setPlaylist([]);
        setCurrentIndex(0);
      }
      await loadPlaylists();
      notify('Playlist deleted', 'info');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to delete playlist', 'error');
    }
  };

  const handleDeleteClick = (playlist) => {
    if (confirmDeleteId === playlist.id) {
      deletePlaylist(playlist.id);
    } else {
      setConfirmDeleteId(playlist.id);
      notify(`Click delete again to confirm removing "${playlist.name}"`, 'info');
    }
  };

  const refreshAll = useCallback(async () => {
    await loadPlaylists();
    if (activePlaylistId) await loadItems(activePlaylistId);
  }, [loadPlaylists, loadItems, activePlaylistId]);

  // --- Adding items (multi-select, one click) -----------------------------
  const toggleSelectFile = (filename) => {
    setSelectedFilenames((current) => (
      current.includes(filename)
        ? current.filter((item) => item !== filename)
        : [...current, filename]
    ));
  };

  const selectAllFiltered = () => {
    setSelectedFilenames(filteredAvailable.map((file) => file.filename));
  };

  const clearSelection = () => setSelectedFilenames([]);

  const addSelected = async () => {
    const count = selectedFilenames.length;
    if (count === 0 || isAdding) return;
    setIsAdding(true);

    let targetId;
    let targetName;

    if (addTarget === 'current') {
      targetId = activePlaylistId;
      targetName = activePlaylist?.name || '';
    } else if (addTarget === 'new') {
      const clean = addNewName.trim();
      if (!clean) {
        notify('Enter a name for the new playlist', 'error');
        setIsAdding(false);
        return;
      }
      try {
        const created = await api.post('/playlists', { name: clean });
        targetId = created.data?.playlist?.id;
        targetName = created.data?.playlist?.name || clean;
      } catch (error) {
        notify(error?.response?.data?.detail || 'Unable to create playlist', 'error');
        setIsAdding(false);
        return;
      }
    } else {
      targetId = Number(addTarget);
      targetName = playlists.find((playlist) => playlist.id === targetId)?.name || 'playlist';
    }

    if (!targetId) {
      notify('Choose a playlist to add to', 'error');
      setIsAdding(false);
      return;
    }

    try {
      await api.post(`/playlists/${targetId}/items/batch`, { filenames: selectedFilenames });
      clearSelection();
      if (addTarget === 'new') {
        setAddTarget('current');
        setAddNewName('');
        setActivePlaylistId(targetId);
      }
      await loadPlaylists();
      // Only refresh the visible queue when the target is the active playlist.
      // (A brand-new playlist is activated above, which triggers its own load.)
      if (activePlaylistId === targetId) await loadItems(activePlaylistId);
      notify(`Added ${count} item${count === 1 ? '' : 's'} to "${targetName}"`, 'success');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to add items', 'error');
    } finally {
      setIsAdding(false);
    }
  };

  const [confirmRemoveFile, setConfirmRemoveFile] = useState(null); // two-step permanent delete guard

  const removeItem = async (filename) => {
    if (!activePlaylistId) return;
    if (confirmRemoveFile !== filename) {
      setConfirmRemoveFile(filename);
      notify('Click delete again to confirm — this also deletes the file from your device & Library', 'info');
      window.setTimeout(() => setConfirmRemoveFile((current) => (current === filename ? null : current)), 4000);
      return;
    }
    setConfirmRemoveFile(null);
    try {
      await api.delete(`/playlists/${activePlaylistId}/items/${encodeURIComponent(filename)}`);
      setPlaylist((current) => current.filter((item) => item !== filename));
      await loadPlaylists();
      if (onLibraryChanged) onLibraryChanged();
      notify('Removed from playlist & file deleted from device', 'success');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to remove item', 'error');
    }
  };

  // --- Ordering -----------------------------------------------------------
  const saveOrder = async (nextOrder) => {
    if (!activePlaylistId) return;
    setPlaylist(nextOrder);
    try {
      const response = await api.post(`/playlists/${activePlaylistId}/reorder`, nextOrder);
      setPlaylist(Array.isArray(response.data) ? response.data : nextOrder);
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to save playlist order', 'error');
      loadItems(activePlaylistId);
    }
  };

  const sortPlaylist = (direction) => {
    if (playlist.length < 2) return;
    const next = [...playlist].sort((left, right) => {
      const leftTitle = fileMap.get(left)?.title || cleanTitle(left);
      const rightTitle = fileMap.get(right)?.title || cleanTitle(right);
      return naturalCompare(leftTitle, rightTitle);
    });

    if (direction === 'desc') {
      next.reverse();
    }

    setCurrentIndex(0);
    saveOrder(next);
  };

  const moveItem = (index, direction) => {
    const target = index + direction;
    if (target < 0 || target >= playlist.length) return;
    const next = [...playlist];
    [next[index], next[target]] = [next[target], next[index]];
    saveOrder(next);
  };

  const shufflePlaylist = () => {
    const next = [...playlist];
    for (let i = next.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [next[i], next[j]] = [next[j], next[i]];
    }
    setCurrentIndex(0);
    saveOrder(next);
  };

  // --- Playback -----------------------------------------------------------
  const playIndex = (index) => {
    setCurrentIndex(index);
    setIsPlaying(true);
    window.setTimeout(() => playerRef.current?.play?.(), 0);
  };

  const playNext = () => {
    if (playlistFiles.length === 0) return;
    const nextIndex = currentIndex + 1 < playlistFiles.length ? currentIndex + 1 : 0;
    playIndex(nextIndex);
  };

  const togglePlay = () => {
    if (!playerRef.current) return;
    if (isPlaying) {
      playerRef.current.pause?.();
      setIsPlaying(false);
    } else {
      playerRef.current.play?.();
      setIsPlaying(true);
    }
  };

  const copyPlaylistTranscript = async () => {
    if (!currentFile?.filename || transcriptLoading) return;
    setTranscriptLoading(true);
    setTranscriptStatus('Getting...');
    try {
      const response = await api.get(`/transcript/${encodeURIComponent(currentFile.filename)}`);
      const segments = Array.isArray(response.data?.segments) ? response.data.segments : [];
      const transcriptText = transcriptSegmentsToText(segments);

      if (!transcriptText) {
        notify('No transcript available for this item', 'error');
        setTranscriptStatus('No Transcript');
        return;
      }

      await navigator.clipboard.writeText(transcriptText);
      setTranscriptStatus('Copied');
      notify('Transcript copied to clipboard', 'success');
      window.setTimeout(() => setTranscriptStatus('Get Transcript'), 1800);
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to get transcript', 'error');
      setTranscriptStatus('Get Transcript');
    } finally {
      setTranscriptLoading(false);
    }
  };

  const otherPlaylists = playlists.filter((playlist) => playlist.id !== activePlaylistId);

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Playlists</h1>
          <p className="page-subtitle">Create as many playlists as you like, add your saved library items to any of them, and play continuously.</p>
        </div>
        <div className="page-header__actions">
          <button className="ghost-button" type="button" onClick={refreshAll} title="Refresh playlists">
            <RefreshCw size={16} /> Refresh
          </button>
          <button className="ghost-button" type="button" onClick={() => sortPlaylist('asc')} disabled={playlist.length < 2}>
            Sort 1-9
          </button>
          <button className="ghost-button" type="button" onClick={() => sortPlaylist('desc')} disabled={playlist.length < 2}>
            Sort 9-1
          </button>
          <button className="ghost-button" type="button" onClick={shufflePlaylist} disabled={playlist.length < 2}>
            <Shuffle size={16} /> Shuffle
          </button>
        </div>
      </div>

      {/* Playlist switcher + management */}
      <section className="panel panel--playlists">
        <div className="playlist-bar">
          {playlists.map((playlist) => {
            const isActive = playlist.id === activePlaylistId;
            const isConfirming = confirmDeleteId === playlist.id;
            return (
              <div key={playlist.id} className={`playlist-chip-wrap ${isActive ? 'playlist-chip-wrap--active' : ''}`}>
                <button
                  className="playlist-chip"
                  type="button"
                  onClick={() => {
                    setConfirmDeleteId(null);
                    setActivePlaylistId(playlist.id);
                  }}
                >
                  <span className="playlist-chip__name">{playlist.name}</span>
                  <span className="playlist-chip__count">{playlist.item_count}</span>
                </button>
                {isActive ? (
                  <span className="playlist-chip__tools">
                    <button
                      className="icon-button"
                      type="button"
                      title="Rename playlist"
                      onClick={(event) => {
                        event.stopPropagation();
                        setIsRenaming(true);
                        setRenameValue(playlist.name);
                      }}
                    >
                      <Edit3 size={13} />
                    </button>
                    <button
                      className={`icon-button ${isConfirming ? 'icon-button--danger playlist-chip__confirm' : 'icon-button--danger'}`}
                      type="button"
                      title={isConfirming ? 'Click again to confirm deletion' : 'Delete playlist'}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDeleteClick(playlist);
                      }}
                    >
                      {isConfirming ? <X size={13} /> : <Trash2 size={13} />}
                    </button>
                  </span>
                ) : null}
              </div>
            );
          })}
          <button className="playlist-chip playlist-chip--new" type="button" onClick={() => setIsCreating(true)}>
            <Plus size={14} /> New playlist
          </button>
        </div>

        {isCreating ? (
          <div className="inline-form">
            <input
              className="input inline-form__input"
              type="text"
              value={newPlaylistName}
              onChange={(event) => setNewPlaylistName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') createPlaylist(newPlaylistName);
                if (event.key === 'Escape') {
                  setIsCreating(false);
                  setNewPlaylistName('');
                }
              }}
              placeholder="Playlist name"
              maxLength={120}
              autoFocus
            />
            <button className="primary-button" type="button" onClick={() => createPlaylist(newPlaylistName)}>
              Create
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                setIsCreating(false);
                setNewPlaylistName('');
              }}
            >
              Cancel
            </button>
          </div>
        ) : null}

        {isRenaming && activePlaylist ? (
          <div className="inline-form">
            <input
              className="input inline-form__input"
              type="text"
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') renamePlaylist(activePlaylist.id, renameValue);
                if (event.key === 'Escape') setIsRenaming(false);
              }}
              placeholder="New playlist name"
              maxLength={120}
              autoFocus
            />
            <button className="primary-button" type="button" onClick={() => renamePlaylist(activePlaylist.id, renameValue)}>
              Rename
            </button>
            <button className="ghost-button" type="button" onClick={() => setIsRenaming(false)}>
              Cancel
            </button>
          </div>
        ) : null}
      </section>

      {/* Add from library — asks which playlist (existing or brand new) */}
      <section className="panel panel--form">
        <div className="form-grid">
          <div className="field">
            <label className="field__label" htmlFor="playlist-target">ADD TO WHICH PLAYLIST?</label>
              <select
                id="playlist-target"
                className="select"
                value={addTarget}
                onChange={(event) => {
                  setAddTarget(event.target.value);
                  setConfirmDeleteId(null);
                }}
              >
                {activePlaylist ? (
                  <option value="current">Current playlist: {activePlaylist.name}</option>
                ) : null}
                {otherPlaylists.map((playlist) => (
                  <option key={playlist.id} value={String(playlist.id)}>{playlist.name}</option>
                ))}
                <option value="new">＋ Create new playlist…</option>
              </select>
            </div>
            {addTarget === 'new' ? (
              <div className="field">
                <label className="field__label" htmlFor="playlist-target-name">NEW PLAYLIST NAME</label>
                <input
                  id="playlist-target-name"
                  className="input"
                  type="text"
                  value={addNewName}
                  onChange={(event) => setAddNewName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') addSelected();
                  }}
                  placeholder="e.g. Workout Mix, Study, Road Trip…"
                  maxLength={120}
                  autoFocus
                />
              </div>
            ) : null}
            <div className="field field--full">
              <div className="multiselect-header">
                <label className="field__label" style={{ margin: 0 }}>
                  SELECT VIDEOS — {selectedFilenames.length} selected
                </label>
                <div className="multiselect-header__actions">
                  <button
                    className="ghost-button ghost-button--small"
                    type="button"
                    onClick={selectAllFiltered}
                    disabled={filteredAvailable.length === 0}
                  >
                    Select all
                  </button>
                  <button
                    className="ghost-button ghost-button--small"
                    type="button"
                    onClick={clearSelection}
                    disabled={selectedFilenames.length === 0}
                  >
                    Clear
                  </button>
                </div>
              </div>
              <div className="multiselect-search">
                <Search size={15} className="multiselect-search__icon" />
                <input
                  className="input input--search"
                  value={libraryQuery}
                  onChange={(event) => setLibraryQuery(event.target.value)}
                  placeholder="Search library..."
                />
              </div>
              <div className="multiselect-list">
                {filteredAvailable.length === 0 ? (
                  <div className="empty-state empty-state--compact">
                    <p>
                      {libraryQuery.trim()
                        ? 'No files match your search.'
                        : 'No files left to add — everything in your library is already in this playlist.'}
                    </p>
                  </div>
                ) : (
                  filteredAvailable.map((file) => {
                    const checked = selectedFilenames.includes(file.filename);
                    return (
                      <label
                        key={file.filename}
                        className={`multiselect-row ${checked ? 'multiselect-row--checked' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSelectFile(file.filename)}
                        />
                        <PlaylistThumb file={file} />
                        <span className="multiselect-row__title" title={file.title || cleanTitle(file.filename)}>
                          {file.title || cleanTitle(file.filename)}
                        </span>
                        <span className="multiselect-row__ext">{mediaExt(file.filename).toUpperCase()}</span>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
        </div>
        <button className="primary-button" type="button" onClick={addSelected} disabled={selectedFilenames.length === 0 || isAdding}>
          {isAdding ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
          {isAdding
            ? 'Adding…'
            : selectedFilenames.length > 0
              ? `Add ${selectedFilenames.length} item${selectedFilenames.length === 1 ? '' : 's'} to playlist`
              : 'Select videos to add'}
        </button>
      </section>

      {/* Re-fetch transcripts for the active playlist (no download) */}
      <section className="panel panel--form">
        <div className="panel__header panel__header--stacked">
          <div>
            <div className="section-eyebrow section-eyebrow--soft">Transcripts for this playlist</div>
            <h2 className="panel__title">Fetch Transcripts Again (no download)</h2>
            <p className="panel__subtitle">
              Deleted or forgot a transcript? The source link of every downloaded video is stored —
              so you can re-fetch the YouTube auto transcript for this playlist's items (all, a range,
              or specific ones) straight into the Transcript Saver. No re-download, no Whisper.
            </p>
          </div>
          <span className="panel__badge panel__badge--soft">{playlist.length} items</span>
        </div>

        {activePlaylistId ? (
          <div className="download-form">
            <div className="form-grid">
              <div className="field">
                <label className="field__label" htmlFor="tr-folder">SAVE INTO FOLDER (optional)</label>
                <input
                  id="tr-folder"
                  className="input"
                  value={trFolder}
                  onChange={(event) => setTrFolder(event.target.value)}
                  placeholder="e.g. dbms — empty = General (first come, first serve)"
                  maxLength={120}
                />
              </div>
            </div>

            <div className="playlist-batch-pick">
              <div className="playlist-batch-pick__range">
                <input
                  className="input input--num"
                  value={trRangeFrom}
                  onChange={(event) => setTrRangeFrom(event.target.value)}
                  placeholder="From #"
                  inputMode="numeric"
                />
                <span>to</span>
                <input
                  className="input input--num"
                  value={trRangeTo}
                  onChange={(event) => setTrRangeTo(event.target.value)}
                  placeholder="To #"
                  inputMode="numeric"
                />
              </div>
              <div className="playlist-batch-pick__typed">
                <input
                  className="input"
                  value={trSpecific}
                  onChange={(event) => setTrSpecific(event.target.value)}
                  placeholder="Or specific numbers: 1, 3, 5-8 (empty = ALL)"
                />
              </div>
            </div>

            <div className="transcript-actions">
              <button
                className="primary-button"
                type="button"
                onClick={handleFetchTranscripts}
                disabled={trStarting || !!trBatchId || playlist.length === 0}
              >
                {trStarting ? <Loader2 className="spin" size={16} /> : <BookOpenText size={16} />}
                {trStarting
                  ? 'Starting…'
                  : trSpecific.trim() || trRangeFrom.trim()
                    ? 'Fetch selected transcripts (no download)'
                    : `Fetch all ${playlist.length} transcript${playlist.length === 1 ? '' : 's'} (no download)`}
              </button>
              {trBatchId ? (
                <button className="ghost-button" type="button" onClick={resetTranscriptFetch}>
                  <X size={16} /> Reset
                </button>
              ) : null}
            </div>

            {/* Find a video by pasting its subtitle */}
            <div className="subtitle-search">
              <div className="subtitle-search__head">
                <Search size={14} />
                <span>Find a video by pasting a subtitle line</span>
              </div>
              <div className="subtitle-search__row">
                <input
                  className="input"
                  value={subQuery}
                  onChange={(event) => { setSubQuery(event.target.value); setSubResults(null); setSubError(''); }}
                  onKeyDown={(event) => { if (event.key === 'Enter') handleSubtitleSearch(); }}
                  placeholder="Paste any subtitle text from the video… (e.g. “mitochondria is the powerhouse”)"
                />
                <button className="ghost-button" type="button" onClick={handleSubtitleSearch} disabled={subSearching || subQuery.trim().length < 2}>
                  {subSearching ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
                  {subSearching ? 'Searching…' : 'Find video'}
                </button>
              </div>
              {subError ? <p className="download-card__error">{subError}</p> : null}
              {subResults ? (
                <div className="subtitle-search__results">
                  <p className="subtitle-search__summary">
                    {subResults.count > 0
                      ? `Found ${subResults.count} video${subResults.count === 1 ? '' : 's'} in this playlist`
                      : 'No matching video found'}
                    {subResults.fetched_missing > 0 ? ` · fetched ${subResults.fetched_missing} transcript${subResults.fetched_missing === 1 ? '' : 's'} to check` : ''}
                    {subResults.no_transcript > 0 && subResults.count === 0 ? ` · ${subResults.no_transcript} video${subResults.no_transcript === 1 ? '' : 's'} had no saved transcript` : ''}
                  </p>
                  {subResults.matches?.map((m) => (
                    <button key={m.filename} className="subtitle-search__match" type="button" onClick={() => jumpToSubtitleMatch(m.filename)}>
                      <span className="subtitle-search__match-title">{m.title}</span>
                      <span className="subtitle-search__match-snippet">“{m.snippet}”</span>
                      <span className="subtitle-search__match-cta">Play in playlist →</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {trBatchId ? (
              <div className="playlist-batch-progress">
                <div className="download-card__title-row">
                  <div>
                    <h3 className="panel__title panel__title--tight">
                      {trBatch?.phase === 'completed'
                        ? 'Transcripts ready ✓'
                        : trBatch?.phase === 'partial'
                          ? 'Finished — some unavailable'
                          : trBatch?.phase === 'cancelled'
                            ? 'Cancelled'
                            : 'Fetching transcripts…'}
                    </h3>
                    <p className="panel__subtitle">
                      {trBatch
                        ? `${trBatch.completed_count || 0}/${trBatch.total_count || 0} saved`
                          + (trBatch.failed_count ? ` · ${trBatch.failed_count} unavailable` : '')
                          + (trBatch.transcript_folder ? ` → "${trBatch.transcript_folder}"` : ' → General')
                        : 'Starting…'}
                    </p>
                  </div>
                  {trBatch && (trBatch.completed_count || 0) > 0 ? (
                    <Link
                      className="ghost-button"
                      to={trBatch.transcript_folder
                        ? `/transcripts?folder=${encodeURIComponent(trBatch.transcript_folder)}`
                        : '/transcripts'}
                    >
                      <BookOpenText size={16} /> View transcripts
                    </Link>
                  ) : null}
                </div>
                {trBatch ? (
                  <div className="playlist-batch-tasks">
                    {trBatch.tasks.map((task) => (
                      <div key={`${task.index}-${task.id || task.url}`} className={`playlist-batch-task playlist-batch-task--${task.status}`}>
                        <span className="playlist-batch-task__index">#{task.index}</span>
                        <span className="playlist-batch-task__title" title={task.title}>{task.title}</span>
                        <span className={`playlist-batch-task__tflag playlist-batch-task__tflag--${task.transcript_status}`}
                          title={task.transcript_error || trStatusLabel(task.transcript_status)}>
                          {task.transcript_status === 'saved' ? <CheckCircle2 size={13} /> : null}
                          {task.transcript_status === 'unavailable' || task.transcript_status === 'error'
                            ? <XCircle size={13} />
                            : task.transcript_status === 'fetching'
                              ? <Loader2 className="spin" size={13} />
                              : null}
                          {trStatusLabel(task.transcript_status)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state empty-state--compact"><p>Starting…</p></div>
                )}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="empty-state empty-state--compact">
            <p>Select a playlist above to fetch its transcripts.</p>
          </div>
        )}
      </section>

      {currentFile ? (
        <section className="panel panel--preview">
          <div className="preview-media">
            {isImage(currentFile.filename) ? (
              <img
                className="preview-image"
                src={`${API_BASE}/stream/${encodeURIComponent(currentFile.filename)}`}
                alt={currentFile.title || cleanTitle(currentFile.filename)}
              />
            ) : isAudio(currentFile.filename) ? (
              <div className="preview-audio">
                <div className="preview-audio__art">♪</div>
                <audio
                  ref={playerRef}
                  className="preview-audio__player"
                  src={currentUrl}
                  controls
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onEnded={playNext}
                  onLoadedMetadata={(event) => {
                    event.currentTarget.playbackRate = playbackRate;
                  }}
                />
              </div>
            ) : (
              <video
                ref={playerRef}
                className="preview-player"
                src={currentUrl}
                controls
                preload="metadata"
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={playNext}
                onLoadedMetadata={(event) => {
                  event.currentTarget.playbackRate = playbackRate;
                }}
                onError={() => {
                  if (!useCompatiblePlayback) setUseCompatiblePlayback(true);
                }}
              />
            )}
          </div>
          <div className="preview-meta">
            <div>
              <h2 className="panel__title panel__title--tight">{currentFile.title || cleanTitle(currentFile.filename)}</h2>
              <p className="panel__subtitle">Item {currentIndex + 1} of {playlistFiles.length}</p>
            </div>
            <div className="preview-actions">
              <label className="field__label" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                Speed
                <select className="select" value={playbackRate} onChange={(event) => setPlaybackRate(Number(event.target.value))} style={{ width: 110 }}>
                  {[0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map((rate) => (
                    <option key={rate} value={rate}>{rate}x</option>
                  ))}
                </select>
              </label>
              <button className="primary-button" type="button" onClick={copyPlaylistTranscript} disabled={transcriptLoading}>
                {transcriptStatus}
              </button>
              <button className="ghost-button" type="button" onClick={togglePlay}>
                {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                {isPlaying ? 'Pause' : 'Play'}
              </button>
              <button className="ghost-button" type="button" onClick={playNext}>Next</button>
              <a className="ghost-button" href={`${API_BASE}/files/download/${encodeURIComponent(currentFile.filename)}`} download>
                <Download size={16} /> Download
              </a>
            </div>
          </div>
        </section>
      ) : null}

      <section className="panel panel--list">
        <div className="panel__header">
          <div>
            <h2 className="panel__title">{activePlaylist ? activePlaylist.name : 'Queue'}</h2>
            <p className="panel__subtitle">
              {activePlaylist
                ? `${playlist.length} item${playlist.length === 1 ? '' : 's'} in this playlist.`
                : 'Create a playlist to get started.'}
            </p>
          </div>
          <span className="panel__badge">{playlist.length}</span>
        </div>

        {isLoading ? (
          <div className="empty-state"><p>Loading playlist...</p></div>
        ) : playlists.length === 0 ? (
          <div className="empty-state">
            <p>You have no playlists yet. Click “New playlist” above to create your first one.</p>
          </div>
        ) : playlistFiles.length === 0 ? (
          <div className="empty-state"><p>This playlist is empty. Add files from the library above.</p></div>
        ) : (
          <div className="stack-list">
            {playlistFiles.map((file, index) => (
              <article
                key={`${file.filename}-${index}`}
                className={`download-card ${index === currentIndex ? 'download-card--active' : ''} ${dragIndex === index ? 'download-card--dragging' : ''} ${dragOverIndex === index ? 'download-card--drop-target' : ''}`}
                role="button"
                tabIndex={0}
                draggable
                onClick={() => {
                  if (suppressClickRef.current) {
                    suppressClickRef.current = false;
                    return;
                  }
                  playIndex(index);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    playIndex(index);
                  }
                }}
                onDragStart={handleDragStart(index)}
                onDragOver={handleDragOver(index)}
                onDrop={handleDrop(index)}
                onDragEnd={handleDragEnd}
              >
                <PlaylistThumb file={file} />
                <div className="download-card__body">
                  <div className="download-card__title-row">
                    <h3 className="download-card__title">{file.title || cleanTitle(file.filename)}</h3>
                    {file.missing ? <span className="status-pill status-pill--error">Missing</span> : null}
                  </div>
                  <div className="download-card__meta">
                    <span>{mediaExt(file.filename).toUpperCase()}</span>
                    <span>#{index + 1}</span>
                  </div>
                </div>
                <div className="download-card__actions">
                  <button className="icon-button" type="button" onClick={(event) => { event.stopPropagation(); playIndex(index); }} title="Play"><Play size={15} /></button>
                  <button className="icon-button" type="button" onClick={(event) => { event.stopPropagation(); moveItem(index, -1); }} disabled={index === 0} title="Move up">↑</button>
                  <button className="icon-button" type="button" onClick={(event) => { event.stopPropagation(); moveItem(index, 1); }} disabled={index === playlist.length - 1} title="Move down">↓</button>
                  <button className="icon-button icon-button--danger" type="button" onClick={(event) => { event.stopPropagation(); removeItem(file.filename); }} title="Remove"><Trash2 size={15} /></button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
