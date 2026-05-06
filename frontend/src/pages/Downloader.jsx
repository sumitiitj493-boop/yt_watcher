import { useState } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

export default function Downloader() {
  const [url, setUrl] = useState('');
  const [quality, setQuality] = useState('1080');
  const [format, setFormat] = useState('mp4');
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [ws, setWs] = useState(null);

  const startDownload = async (e) => {
    e.preventDefault();
    if (!url) return;

    try {
      const res = await axios.post(`${API_BASE}/download`, { url, quality, format });
      const newTaskId = res.data.task_id;
      setTaskId(newTaskId);
      connectWebSocket(newTaskId);
    } catch (err) {
      console.error('Download failed to start:', err);
      alert('Failed to start download');
    }
  };

  const connectWebSocket = (id) => {
    if (ws) ws.close();
    const socket = new WebSocket(`ws://localhost:8000/api/ws/status/${id}`);
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data);
      if (data.status === 'completed' || data.status === 'error') {
        socket.close();
      }
    };
    
    setWs(socket);
  };

  return (
    <div className="downloader-container">
      <h2>Download Video</h2>
      <form onSubmit={startDownload} className="download-form">
        <input 
          type="text" 
          placeholder="Paste YouTube URL here..." 
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required 
        />
        <div className="options">
          <select value={quality} onChange={(e) => setQuality(e.target.value)}>
            <option value="best">Best (auto)</option>
            <option value="2160">4K (2160p)</option>
            <option value="1080">1080p</option>
            <option value="720">720p</option>
            <option value="480">480p</option>
            <option value="360">360p</option>
          </select>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="mp4">MP4</option>
            <option value="webm">WebM</option>
            <option value="mp3">Audio (MP3)</option>
          </select>
        </div>
        <button type="submit" disabled={!url || (status && status.status === 'downloading')}>
          Start Download
        </button>
      </form>

      {status && (
        <div className="status-container">
          <h3>Status: <span className="status-label">{status.status}</span></h3>
          {status.title && <p><strong>Title:</strong> {status.title}</p>}
          {(status.status === 'downloading' || status.status === 'processing') && (
            <div className="progress-wrapper">
              <div className="progress-stats">
                <span>{status.percent}</span>
                {status.speed && <span>{status.speed}</span>}
                {status.eta && <span>ETA: {status.eta}</span>}
              </div>
            </div>
          )}
          {status.error && <p className="error">{status.error}</p>}
        </div>
      )}
    </div>
  );
}
