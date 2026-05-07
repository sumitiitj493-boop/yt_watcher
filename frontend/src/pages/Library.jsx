import { useMemo, useState, useEffect } from 'react';
import { RotateCcw, Trash2 } from 'lucide-react';
import { api } from '../lib/api';

const cleanTitle = (filename) => (
  filename
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

const formatDate = (value) => {
  if (!value) return '';
  const date = new Date(value * 1000);
  return date.toLocaleString();
};

export default function Library() {
  const [history, setHistory] = useState([]);
  const [query, setQuery] = useState('');

  const fetchHistory = async () => {
    try {
      const res = await api.get('/downloads');
      setHistory(res.data.downloads || []);
    } catch (err) {
      console.error('Error fetching history:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleDelete = async (taskId) => {
    if (!taskId) {
      console.error('Missing task id for delete');
      return;
    }
    try {
      await api.delete(`/downloads/${encodeURIComponent(taskId)}`);
      fetchHistory();
    } catch (err) {
      console.error('Error deleting history item:', err);
    }
  };

  const handleRedownload = async (item) => {
    if (!item.url) return;
    try {
      await api.post('/download', {
        url: item.url,
        quality: item.quality || 'best',
        format: item.format || 'mp4',
      });
      fetchHistory();
    } catch (err) {
      console.error('Error re-downloading:', err);
    }
  };

  const handleClear = async () => {
    try {
      await api.post('/downloads/clear');
      fetchHistory();
    } catch (err) {
      console.error('Error clearing history:', err);
    }
  };

  const filteredHistory = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return history;
    return history.filter((item) => {
      const title = item.title || cleanTitle(item.filename || '');
      return title.toLowerCase().includes(term);
    });
  }, [history, query]);

  return (
    <div className="library-container">
      <h2>Download History</h2>
      <div className="library-toolbar">
        <div className="library-search">
          <input
            type="text"
            placeholder="Search history..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <button onClick={fetchHistory} className="refresh-btn">Refresh</button>
        <button onClick={handleClear} className="refresh-btn danger">Clear History</button>
      </div>
      <div className="history-list">
        {filteredHistory.length === 0 ? (
          <p>No download history yet.</p>
        ) : (
          filteredHistory.map((item) => {
            const title = item.title || cleanTitle(item.filename || 'Unknown');
            const thumbUrl = item.video_id
              ? `https://img.youtube.com/vi/${item.video_id}/mqdefault.jpg`
              : '';
            return (
              <div
                key={item.task_id || item.created_at || item.filename || title}
                className="history-card"
                onClick={() => handleRedownload(item)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') handleRedownload(item);
                }}
              >
                <div className="history-thumb">
                  {thumbUrl ? (
                    <img
                      src={thumbUrl}
                      alt={title}
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = 'none';
                      }}
                    />
                  ) : (
                    <div className="history-thumb-fallback" />
                  )}
                </div>
                <div className="history-info">
                  <h4>{title}</h4>
                  <p>{item.status || 'unknown'} · {item.quality || 'best'} · {item.format || 'mp4'}</p>
                  <p className="muted">{formatDate(item.created_at)}</p>
                </div>
                <div className="history-actions">
                  <button
                    className="delete-btn"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleDelete(item.task_id);
                    }}
                  >
                    <Trash2 size={18} />
                  </button>
                  <span className="redo-icon" title="Click card to download again">
                    <RotateCcw size={16} />
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
