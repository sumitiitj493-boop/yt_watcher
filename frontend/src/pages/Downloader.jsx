import { useEffect, useMemo, useState } from 'react';
import { api, wsBase } from '../lib/api';

const cleanTitle = (value) => (
  value
    .split(/[\\/]/)
    .pop()
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

export default function Downloader() {
  const [url, setUrl] = useState('');
  const [quality, setQuality] = useState('1080');
  const [format, setFormat] = useState('mp4');
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [ws, setWs] = useState(null);
  const [downloadDir, setDownloadDir] = useState('');

  const startDownload = async (e) => {
    e.preventDefault();
    if (!url) return;

    try {
      const res = await api.post('/download', { url, quality, format });
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
    const socket = new WebSocket(`${wsBase}/ws/status/${id}`);
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data);
      if (data.status === 'completed' || data.status === 'error') {
        socket.close();
      }
    };

    socket.onerror = () => {
      setStatus({ status: 'error', error: 'WebSocket error' });
    };
    
    setWs(socket);
  };

  const handleCancel = async () => {
    if (!taskId) return;
    try {
      await api.post(`/cancel/${taskId}`);
    } catch (err) {
      console.error('Cancel failed:', err);
    }
  };

  useEffect(() => {
    return () => {
      if (ws) ws.close();
    };
  }, [ws]);

  useEffect(() => {
    if (status?.status !== 'completed' || downloadDir) return;
    const fetchDir = async () => {
      try {
        const res = await api.get('/downloads/location');
        setDownloadDir(res.data.path || '');
      } catch (err) {
        console.error('Failed to fetch download path:', err);
      }
    };
    fetchDir();
  }, [status, downloadDir]);

  const percentValue = useMemo(() => {
    if (Number.isFinite(status?.progress)) {
      return Math.min(Math.max(status.progress, 0), 100);
    }
    if (!status?.percent) return 0;
    const parsed = Number.parseFloat(status.percent);
    return Number.isNaN(parsed) ? 0 : Math.min(Math.max(parsed, 0), 100);
  }, [status]);

  const percentLabel = useMemo(() => {
    if (Number.isFinite(status?.progress)) {
      return `${status.progress.toFixed(1)}%`;
    }
    return status?.percent || '0%';
  }, [status]);

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
          {status.title && <p><strong>Title:</strong> {cleanTitle(status.title)}</p>}
          {(status.status === 'downloading' || status.status === 'processing') && (
            <div className="progress-wrapper">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${percentValue}%` }} />
              </div>
              <div className="progress-stats">
                <span>{percentLabel}</span>
                {status.speed && <span>{status.speed}</span>}
                {status.eta && <span>ETA: {status.eta}</span>}
              </div>
            </div>
          )}
          {(status.status === 'downloading' || status.status === 'processing') && (
            <button type="button" className="cancel-btn" onClick={handleCancel}>
              Cancel Download
            </button>
          )}
          {status.status === 'completed' && downloadDir && (
            <div className="download-location">
              <span>Saved in: {downloadDir}</span>
              <button
                type="button"
                className="open-folder-btn"
                onClick={() => {
                  navigator.clipboard.writeText(downloadDir);
                }}
              >
                Copy Folder Path
              </button>
            </div>
          )}
          {status.error && <p className="error">{status.error}</p>}
        </div>
      )}
    </div>
  );
}
