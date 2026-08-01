import { useMemo, useState } from 'react';
import { Check, FileAudio, FileVideo, Search } from 'lucide-react';

const mediaExt = (filename = '') => filename.split('.').pop()?.toLowerCase() || '';
const AUDIO_EXTS = new Set(['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav', 'opus', 'aiff', 'aif']);

const cleanTitle = (filename = '') => (
  filename
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

const extractVideoId = (filename = '') => {
  const match = String(filename).match(/\(([A-Za-z0-9_-]{11})\)/);
  return match ? match[1] : '';
};

const formatBytes = (bytes = 0) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

function FileThumb({ file }) {
  const title = file.title || cleanTitle(file.filename || '');
  const videoId = file.video_id || extractVideoId(file.filename || '');

  if (videoId) {
    return (
      <img
        className="library-picker__thumb"
        src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
        alt={title}
        loading="lazy"
        onError={(event) => {
          event.currentTarget.style.display = 'none';
        }}
      />
    );
  }

  const ext = mediaExt(file.filename || '');
  const isAudio = AUDIO_EXTS.has(ext);
  return (
    <div className="library-picker__thumb library-picker__thumb--fallback" aria-hidden="true">
      {isAudio ? <FileAudio size={22} /> : <FileVideo size={22} />}
      <span>{ext.toUpperCase() || 'FILE'}</span>
    </div>
  );
}

/**
 * Visual file browser for choosing a saved file (e.g. in Whisper).
 * Shows thumbnails + titles from the backend downloads folder instead of
 * a text-only dropdown.
 */
export default function LibraryPicker({
  files = [],
  value = '',
  onSelect,
  searchPlaceholder = 'Search saved files...',
}) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return files;
    return files.filter((file) => {
      const title = (file.title || cleanTitle(file.filename || '')).toLowerCase();
      const filename = (file.filename || '').toLowerCase();
      return title.includes(needle) || filename.includes(needle);
    });
  }, [files, query]);

  return (
    <div className="library-picker">
      <div className="library-picker__search">
        <Search size={15} className="library-picker__search-icon" />
        <input
          className="input input--search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder}
        />
      </div>

      {filtered.length === 0 ? (
        <div className="library-picker__empty">
          {files.length === 0
            ? 'No saved files yet. Download some videos first, then you can transcribe them here.'
            : 'No files match your search.'}
        </div>
      ) : (
        <div className="library-picker__grid">
          {filtered.map((file) => {
            const selected = file.filename === value;
            return (
              <button
                key={file.filename}
                type="button"
                className={`library-picker__card ${selected ? 'library-picker__card--selected' : ''}`}
                onClick={() => onSelect?.(file.filename)}
                title={file.filename}
              >
                <FileThumb file={file} />
                <span className="library-picker__card-check" aria-hidden="true">
                  {selected ? <Check size={12} /> : null}
                </span>
                <span className="library-picker__card-title">
                  {file.title || cleanTitle(file.filename)}
                </span>
                <span className="library-picker__card-meta">
                  {mediaExt(file.filename).toUpperCase()} · {formatBytes(file.size)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
