import { useState, useEffect } from 'react';
import { PlayCircle, Download as DownloadIcon, Trash2 } from 'lucide-react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export default function Library() {
  const [files, setFiles] = useState([]);

  const fetchFiles = async () => {
    try {
      const res = await axios.get(`${API_BASE}/files`);
      setFiles(res.data.files || []);
    } catch (err) {
      console.error('Error fetching files:', err);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleDelete = async (filename) => {
    try {
      await axios.delete(`${API_BASE}/delete/${filename}`);
      fetchFiles();
    } catch (err) {
      console.error('Error deleting file:', err);
    }
  };

  return (
    <div className="library-container">
      <h2>Your Video Library</h2>
      <button onClick={fetchFiles} className="refresh-btn">Refresh</button>
      <div className="video-grid">
        {files.length === 0 ? (
          <p>No downloaded videos yet.</p>
        ) : (
          files.map((file) => (
            <div key={file.filename} className="video-card">
              <div className="video-info">
                <h4>{file.filename}</h4>
                <p>{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
              <div className="actions">
                <button className="play-btn">
                  <PlayCircle size={20} />
                </button>
                <button onClick={() => handleDelete(file.filename)} className="delete-btn">
                  <Trash2 size={20} color="red" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
