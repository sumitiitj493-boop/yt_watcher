import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download, Edit3, Loader2, Pause, Play, Plus, RefreshCw, Search, Shuffle, Trash2, X } from 'lucide-react';
import { API_BASE, api } from '../lib/api';

const cleanTitle = (filename = '') => (
  filename
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

const mediaExt = (filename = '') => filename.split('.').pop()?.toLowerCase() || '';
const isAudio = (filename = '') => ['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav'].includes(mediaExt(filename));
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

export default function PlaylistPage({ files = [], onNotify }) {
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

  // Player state
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [useCompatiblePlayback, setUseCompatiblePlayback] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [transcriptStatus, setTranscriptStatus] = useState('Get Transcript');
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const playerRef = useRef(null);

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

  const removeItem = async (filename) => {
    if (!activePlaylistId) return;
    try {
      const response = await api.delete(`/playlists/${activePlaylistId}/items/${encodeURIComponent(filename)}`);
      setPlaylist(Array.isArray(response.data) ? response.data : playlist.filter((item) => item !== filename));
      await loadPlaylists();
      notify('Removed from playlist', 'info');
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

      {currentFile ? (
        <section className="panel panel--preview">
          <div className="preview-media">
            {isAudio(currentFile.filename) ? (
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
                className={`download-card ${index === currentIndex ? 'download-card--active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => playIndex(index)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    playIndex(index);
                  }
                }}
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
