import { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import ReactPlayer from 'react-player';
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export default function StudyMode() {
  const { filename } = useParams();
  const [notes, setNotes] = useState([]);
  const [currentNote, setCurrentNote] = useState('');
  const playerRef = useRef(null);

  const handleAddNote = (e) => {
    e.preventDefault();
    if (!currentNote.trim()) return;
    
    // Get current time in seconds
    const time = playerRef.current ? Math.floor(playerRef.current.getCurrentTime()) : 0;
    
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
    if (playerRef.current) {
      playerRef.current.seekTo(time, 'seconds');
    }
  };

  return (
    <div className="study-mode">
      <div className="player-section">
        <h2>Now Watching: {filename}</h2>
        <div className="player-wrapper">
          <ReactPlayer
            ref={playerRef}
            url={`${API_BASE}/stream/${encodeURIComponent(filename)}`}
            width="100%"
            height="100%"
            controls
            playing
            config={{
                file: {
                    attributes: {
                        controlsList: "nodownload"
                    }
                }
            }}
          />
        </div>
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
