import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download, Pause, Play, Shuffle, Trash2 } from 'lucide-react';
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
  const [playlist, setPlaylist] = useState([]);
  const [selectedFilename, setSelectedFilename] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [useCompatiblePlayback, setUseCompatiblePlayback] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const playerRef = useRef(null);

  const fileMap = useMemo(() => new Map(files.map((file) => [file.filename, file])), [files]);
  const playlistFiles = useMemo(
    () => playlist.map((filename) => fileMap.get(filename) || { filename, title: cleanTitle(filename), missing: true }),
    [fileMap, playlist],
  );
  const availableFiles = useMemo(
    () => files.filter((file) => !playlist.includes(file.filename)),
    [files, playlist],
  );
  const currentFile = playlistFiles[currentIndex] || null;
  const currentUrl = currentFile?.filename
    ? `${API_BASE}/${isAudio(currentFile.filename) || !useCompatiblePlayback ? 'stream' : 'stream-compatible'}/${encodeURIComponent(currentFile.filename)}`
    : '';

  const notify = useCallback((message, type = 'info') => {
    if (onNotify) onNotify(message, type);
  }, [onNotify]);

  const refreshPlaylist = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/playlist');
      setPlaylist(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to load playlist', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    refreshPlaylist();
  }, [refreshPlaylist]);

  useEffect(() => {
    setUseCompatiblePlayback(false);
  }, [currentFile?.filename]);

  useEffect(() => {
    if (playerRef.current) {
      playerRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate, currentFile?.filename]);

  useEffect(() => {
    if (currentIndex >= playlistFiles.length) {
      setCurrentIndex(Math.max(0, playlistFiles.length - 1));
    }
  }, [currentIndex, playlistFiles.length]);

  const saveOrder = async (nextOrder) => {
    setPlaylist(nextOrder);
    try {
      const response = await api.post('/playlist/reorder', nextOrder);
      setPlaylist(Array.isArray(response.data) ? response.data : nextOrder);
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to save playlist order', 'error');
      refreshPlaylist();
    }
  };

  const addSelected = async () => {
    if (!selectedFilename) return;
    try {
      const response = await api.post(`/playlist/add/${encodeURIComponent(selectedFilename)}`);
      setPlaylist(Array.isArray(response.data) ? response.data : [...playlist, selectedFilename]);
      setSelectedFilename('');
      notify('Added to playlist', 'success');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to add item', 'error');
    }
  };

  const removeItem = async (filename) => {
    try {
      const response = await api.delete(`/playlist/remove/${encodeURIComponent(filename)}`);
      setPlaylist(Array.isArray(response.data) ? response.data : playlist.filter((item) => item !== filename));
      notify('Removed from playlist', 'info');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to remove item', 'error');
    }
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

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Playlist</h1>
          <p className="page-subtitle">Build a private queue from your saved library, reorder it, and play continuously.</p>
        </div>
        <div className="page-header__actions">
          <button className="ghost-button" type="button" onClick={refreshPlaylist}>Refresh</button>
          <button className="ghost-button" type="button" onClick={shufflePlaylist} disabled={playlist.length < 2}>
            <Shuffle size={16} /> Shuffle
          </button>
        </div>
      </div>

      <section className="panel panel--form">
        <div className="form-grid">
          <div className="field field--full">
            <label className="field__label" htmlFor="playlist-add">ADD FROM LIBRARY</label>
            <select
              id="playlist-add"
              className="select"
              value={selectedFilename}
              onChange={(event) => setSelectedFilename(event.target.value)}
            >
              <option value="">Choose a saved file...</option>
              {availableFiles.map((file) => (
                <option key={file.filename} value={file.filename}>{file.title || cleanTitle(file.filename)}</option>
              ))}
            </select>
          </div>
        </div>
        <button className="primary-button" type="button" onClick={addSelected} disabled={!selectedFilename}>Add to Playlist</button>
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
            <h2 className="panel__title">Queue</h2>
            <p className="panel__subtitle">{playlist.length} item{playlist.length === 1 ? '' : 's'} in your playlist.</p>
          </div>
          <span className="panel__badge">{playlist.length}</span>
        </div>

        {isLoading ? (
          <div className="empty-state"><p>Loading playlist...</p></div>
        ) : playlistFiles.length === 0 ? (
          <div className="empty-state"><p>Your playlist is empty. Add files from the library above.</p></div>
        ) : (
          <div className="stack-list">
            {playlistFiles.map((file, index) => (
              <article key={`${file.filename}-${index}`} className={`download-card ${index === currentIndex ? 'download-card--active' : ''}`}>
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
                  <button className="icon-button" type="button" onClick={() => playIndex(index)} title="Play"><Play size={15} /></button>
                  <button className="icon-button" type="button" onClick={() => moveItem(index, -1)} disabled={index === 0} title="Move up">↑</button>
                  <button className="icon-button" type="button" onClick={() => moveItem(index, 1)} disabled={index === playlist.length - 1} title="Move down">↓</button>
                  <button className="icon-button icon-button--danger" type="button" onClick={() => removeItem(file.filename)} title="Remove"><Trash2 size={15} /></button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
