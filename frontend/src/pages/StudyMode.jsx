import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import ReactPlayer from 'react-player';
import { API_BASE, api } from '../lib/api';

const SPEED_OPTIONS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

const extractVideoId = (name = '') => {
  const match = String(name).match(/\(([A-Za-z0-9_-]{11})\)/);
  return match ? match[1] : '';
};

const cleanTitle = (name = '') => (
  String(name)
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

const formatTime = (seconds = 0) => {
  const safe = Math.max(0, Number(seconds) || 0);
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
};

export default function StudyMode() {
  const { filename } = useParams();
  const [notes, setNotes] = useState([]);
  const [currentNote, setCurrentNote] = useState('');
  const [noteError, setNoteError] = useState('');
  const [isSavingNote, setIsSavingNote] = useState(false);
  const [isLoadingNotes, setIsLoadingNotes] = useState(false);
  const [loopStart, setLoopStart] = useState(null);
  const [loopEnd, setLoopEnd] = useState(null);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [useCompatiblePlayback, setUseCompatiblePlayback] = useState(false);
  const playerRef = useRef(null);
  const audioRef = useRef(null);

  const decodedFilename = useMemo(() => {
    if (!filename) return '';
    try {
      return decodeURIComponent(filename);
    } catch {
      return filename;
    }
  }, [filename]);

  const ext = useMemo(() => decodedFilename.split('.').pop()?.toLowerCase() || '', [decodedFilename]);
  const isAudio = ['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav'].includes(ext);
  const title = useMemo(() => cleanTitle(decodedFilename), [decodedFilename]);
  const videoId = useMemo(() => extractVideoId(decodedFilename), [decodedFilename]);
  const encodedFilename = encodeURIComponent(decodedFilename);
  const mediaUrl = `${API_BASE}/${isAudio || !useCompatiblePlayback ? 'stream' : 'stream-compatible'}/${encodedFilename}`;

  const getCurrentTime = useCallback(() => (
    isAudio
      ? Math.floor(audioRef.current?.currentTime || 0)
      : Math.floor(playerRef.current?.getCurrentTime?.() || 0)
  ), [isAudio]);

  const seekTo = useCallback((time) => {
    if (isAudio && audioRef.current) {
      audioRef.current.currentTime = time;
      audioRef.current.play?.();
      return;
    }
    playerRef.current?.seekTo?.(time, 'seconds');
  }, [isAudio]);

  const refreshNotes = useCallback(async () => {
    if (!decodedFilename) return;
    setIsLoadingNotes(true);
    setNoteError('');
    try {
      const response = await api.get(`/files/${encodedFilename}/notes`);
      setNotes(Array.isArray(response.data?.notes) ? response.data.notes : []);
    } catch (error) {
      setNoteError(error?.response?.data?.detail || 'Unable to load notes.');
    } finally {
      setIsLoadingNotes(false);
    }
  }, [decodedFilename, encodedFilename]);

  useEffect(() => {
    setUseCompatiblePlayback(false);
    refreshNotes();
  }, [decodedFilename, refreshNotes]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = playbackRate;
  }, [playbackRate, isAudio]);

  const handleAddNote = async (event) => {
    event.preventDefault();
    const content = currentNote.trim();
    if (!content || isSavingNote) return;

    setIsSavingNote(true);
    setNoteError('');
    try {
      const response = await api.post(`/files/${encodedFilename}/notes`, {
        time_seconds: getCurrentTime(),
        content,
      });
      const newNote = response.data?.note;
      if (newNote) {
        setNotes((items) => [...items, newNote].sort((a, b) => a.time_seconds - b.time_seconds));
      }
      setCurrentNote('');
    } catch (error) {
      setNoteError(error?.response?.data?.detail || 'Unable to save note.');
    } finally {
      setIsSavingNote(false);
    }
  };

  const deleteNote = async (noteId) => {
    setNoteError('');
    try {
      await api.delete(`/notes/${encodeURIComponent(noteId)}`);
      setNotes((items) => items.filter((note) => note.id !== noteId));
    } catch (error) {
      setNoteError(error?.response?.data?.detail || 'Unable to delete note.');
    }
  };

  const markLoopStart = () => setLoopStart(getCurrentTime());
  const markLoopEnd = () => setLoopEnd(getCurrentTime());
  const clearLoop = () => {
    setLoopStart(null);
    setLoopEnd(null);
  };

  const handleProgress = ({ playedSeconds }) => {
    if (loopStart === null || loopEnd === null || loopEnd <= loopStart) return;
    if (playedSeconds >= loopEnd) seekTo(loopStart);
  };

  const handleAudioTimeUpdate = () => {
    if (loopStart === null || loopEnd === null || loopEnd <= loopStart) return;
    if ((audioRef.current?.currentTime || 0) >= loopEnd) seekTo(loopStart);
  };

  return (
    <div className="study-mode">
      <div className="player-section">
        <h2>{isAudio ? `Now Playing: ${title}` : `Now Watching: ${title}`}</h2>

        <div className="study-toolbar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <button type="button" className="ghost-button" onClick={markLoopStart}>Set A: {loopStart === null ? '--' : formatTime(loopStart)}</button>
          <button type="button" className="ghost-button" onClick={markLoopEnd}>Set B: {loopEnd === null ? '--' : formatTime(loopEnd)}</button>
          <button type="button" className="ghost-button" onClick={clearLoop}>Clear Loop</button>
          <label className="field__label" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
            Speed
            <select className="select" value={playbackRate} onChange={(event) => setPlaybackRate(Number(event.target.value))} style={{ width: 110 }}>
              {SPEED_OPTIONS.map((rate) => <option key={rate} value={rate}>{rate}x</option>)}
            </select>
          </label>
        </div>

        {isAudio ? (
          <div className="audio-wrapper">
            <div className="audio-cover">
              {videoId ? <img src={`https://img.youtube.com/vi/${videoId}/hqdefault.jpg`} alt={title} /> : <div className="audio-cover-fallback" />}
            </div>
            <audio
              ref={audioRef}
              src={mediaUrl}
              controls
              onLoadedMetadata={() => {
                if (audioRef.current) audioRef.current.playbackRate = playbackRate;
              }}
              onTimeUpdate={handleAudioTimeUpdate}
            />
          </div>
        ) : (
          <div className="player-wrapper">
            <ReactPlayer
              ref={playerRef}
              url={mediaUrl}
              width="100%"
              height="100%"
              controls
              playing
              playbackRate={playbackRate}
              onProgress={handleProgress}
              onError={() => {
                if (!useCompatiblePlayback) setUseCompatiblePlayback(true);
              }}
              config={{ file: { attributes: { controlsList: 'nodownload' } } }}
            />
          </div>
        )}
      </div>

      <div className="notes-section">
        <h3>Timestamp Notes</h3>
        {noteError ? <p className="error">{noteError}</p> : null}

        <div className="notes-list">
          {isLoadingNotes ? (
            <p className="empty-notes">Loading notes...</p>
          ) : notes.length === 0 ? (
            <p className="empty-notes">No notes yet. Add one while watching.</p>
          ) : (
            notes.map((note) => (
              <div key={note.id} className="note-card">
                <button type="button" className="note-card__main" onClick={() => seekTo(note.time_seconds)}>
                  <span className="note-timestamp">{formatTime(note.time_seconds)}</span>
                  <span className="note-content">{note.content}</span>
                </button>
                <button type="button" className="icon-button icon-button--danger" onClick={() => deleteNote(note.id)} aria-label="Delete note">×</button>
              </div>
            ))
          )}
        </div>

        <form onSubmit={handleAddNote} className="note-form">
          <input
            type="text"
            value={currentNote}
            onChange={(e) => setCurrentNote(e.target.value)}
            placeholder="Write note at current timestamp..."
          />
          <button type="submit" disabled={isSavingNote || !currentNote.trim()}>{isSavingNote ? 'Saving...' : 'Save'}</button>
        </form>
      </div>
    </div>
  );
}
