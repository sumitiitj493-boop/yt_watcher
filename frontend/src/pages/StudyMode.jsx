import { useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import ReactPlayer from 'react-player';
import { API_BASE } from '../lib/api';

const extractVideoId = (name) => {
  const match = name.match(/\(([A-Za-z0-9_-]{11})\)/);
  return match ? match[1] : '';
};

const cleanTitle = (name) => (
  name
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

export default function StudyMode() {
  const { filename } = useParams();
  const [notes, setNotes] = useState([]);
  const [currentNote, setCurrentNote] = useState('');
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
  const isAudio = ext === 'mp3' || ext === 'm4a';
  const title = useMemo(() => cleanTitle(decodedFilename), [decodedFilename]);
  const videoId = useMemo(() => extractVideoId(decodedFilename), [decodedFilename]);
  const mediaUrl = `${API_BASE}/stream/${encodeURIComponent(decodedFilename)}`;

  const handleAddNote = (e) => {
    e.preventDefault();
    if (!currentNote.trim()) return;
    
    // Get current time in seconds
    const time = isAudio
      ? Math.floor(audioRef.current?.currentTime || 0)
      : Math.floor(playerRef.current?.getCurrentTime() || 0);
    
    const newNote = {
      id: Date.now(),
      time,
      content: currentNote,
      timeString: new Date(time * 1000).toISOString().substring(14, 19)
    };
    
    setNotes([...notes, newNote].sort((a, b) => a.time - b.time));
    setCurrentNote('');
  };

  const seekTo = (time) => {
    if (isAudio && audioRef.current) {
      audioRef.current.currentTime = time;
      return;
    }
    playerRef.current?.seekTo(time, 'seconds');
  };

  return (
    <div className="study-mode">
      <div className="player-section">
        <h2>{isAudio ? `Now Playing: ${title}` : `Now Watching: ${title}`}</h2>
        {isAudio ? (
          <div className="audio-wrapper">
            <div className="audio-cover">
              {videoId ? (
                <img
                  src={`https://img.youtube.com/vi/${videoId}/hqdefault.jpg`}
                  alt={title}
                />
              ) : (
                <div className="audio-cover-fallback" />
              )}
            </div>
            <audio
              ref={audioRef}
              src={mediaUrl}
              controls
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
              config={{
                file: {
                  attributes: {
                    controlsList: 'nodownload',
                  },
                },
              }}
            />
          </div>
        )}
      </div>
      
      <div className="notes-section">
        <h3>Timestamp Notes</h3>
        
        <div className="notes-list">
          {notes.length === 0 ? (
            <p className="empty-notes">No notes yet. Start typing to add one!</p>
          ) : (
            notes.map(note => (
              <div key={note.id} className="note-card" onClick={() => seekTo(note.time)}>
                <span className="note-timestamp">{note.timeString}</span>
                <p className="note-content">{note.content}</p>
              </div>
            ))
          )}
        </div>

        <form onSubmit={handleAddNote} className="note-form">
          <input
            type="text"
            value={currentNote}
            onChange={(e) => setCurrentNote(e.target.value)}
            placeholder="Type a note here..."
          />
          <button type="submit">Save</button>
        </form>
      </div>
    </div>
  );
}
