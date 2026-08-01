import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AudioLines, CheckCircle2, Download, Loader2, Music, RefreshCw } from 'lucide-react';
import { API_BASE, api } from '../lib/api';
import LibraryPicker from '../components/LibraryPicker';

const VIDEO_EXTS = new Set(['mp4', 'webm', 'mkv', 'mov', 'avi', 'm4v']);
const LOSSLESS_FORMATS = new Set(['wav', 'flac', 'aiff']);

const FORMATS = [
  { value: 'mp3', label: 'MP3' },
  { value: 'm4a', label: 'M4A (AAC)' },
  { value: 'aac', label: 'AAC' },
  { value: 'ogg', label: 'OGG (Vorbis)' },
  { value: 'opus', label: 'OPUS' },
  { value: 'wav', label: 'WAV (lossless)' },
  { value: 'flac', label: 'FLAC (lossless)' },
  { value: 'aiff', label: 'AIFF (lossless)' },
];

const BITRATES = [
  { value: '96k', label: '96 kbps' },
  { value: '128k', label: '128 kbps' },
  { value: '192k', label: '192 kbps' },
  { value: '256k', label: '256 kbps' },
  { value: '320k', label: '320 kbps' },
];

const formatDuration = (seconds = 0) => {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

const formatBytes = (bytes = 0) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

export default function AudioExtractorPage({ files = [], onNotify }) {
  const videos = useMemo(
    () => (files || []).filter((file) => VIDEO_EXTS.has((file.ext || '').toLowerCase() || String(file.filename).split('.').pop()?.toLowerCase())),
    [files],
  );
  const [selectedFilename, setSelectedFilename] = useState('');
  const [format, setFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('192k');
  const [job, setJob] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');
  const [nowSeconds, setNowSeconds] = useState(() => Date.now() / 1000);
  const timerRef = useRef(null);

  const isActive = job && ['queued', 'extracting'].includes(job.status);
  const elapsed = job
    ? Math.max(0, Math.floor(nowSeconds - (job.started_at || job.created_at || nowSeconds)))
    : 0;
  const lossless = LOSSLESS_FORMATS.has(format);

  const notify = useCallback((message, type = 'info') => {
    if (onNotify) onNotify(message, type);
  }, [onNotify]);

  // Refresh the picker list when the job completes (new file appears in library).
  useEffect(() => {
    if (job?.status === 'completed') notify('Audio extracted and saved to your Library', 'success');
  }, [job?.status, notify]);

  useEffect(() => {
    if (!isActive) {
      window.clearInterval(timerRef.current);
      return undefined;
    }
    timerRef.current = window.setInterval(() => setNowSeconds(Date.now() / 1000), 1000);
    return () => window.clearInterval(timerRef.current);
  }, [isActive]);

  useEffect(() => {
    if (!job?.job_id || !isActive) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await api.get(`/extract-audio/${encodeURIComponent(job.job_id)}`);
        if (cancelled) return;
        setJob(response.data || null);
      } catch (pollError) {
        if (!cancelled) setError(pollError?.response?.data?.detail || 'Unable to check extraction status');
      }
    };
    poll();
    const timer = window.setInterval(poll, 800);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job?.job_id, isActive]);

  const startExtraction = async (event) => {
    event.preventDefault();
    if (!selectedFilename || isStarting || isActive) return;
    setIsStarting(true);
    setError('');
    setJob(null);
    setNowSeconds(Date.now() / 1000);
    try {
      const response = await api.post('/extract-audio', {
        filename: selectedFilename,
        format,
        bitrate: lossless ? '192k' : bitrate,
      });
      const data = response.data || {};
      setJob({ ...data, created_at: Date.now() / 1000 });
      notify('Audio extraction started', 'success');
    } catch (startError) {
      setError(startError?.response?.data?.detail || 'Unable to start audio extraction');
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Audio Extractor</h1>
          <p className="page-subtitle">
            Pick any saved video and convert it to audio (MP3, M4A, FLAC, WAV and more).
            The result is saved straight to your Library.
          </p>
        </div>
      </div>

      <section className="panel panel--form">
        <div className="form-grid">
          <div className="field field--full">
            <label className="field__label" htmlFor="extract-video">SELECT A VIDEO FROM LIBRARY</label>
            {videos.length > 0 ? (
              <>
                <LibraryPicker
                  files={videos}
                  value={selectedFilename}
                  onSelect={(filename) => {
                    setSelectedFilename(filename);
                    setError('');
                  }}
                  searchPlaceholder="Search videos..."
                />
                <p className="field__help field__help--inline">
                  Click a video to select it. {videos.length} video{videos.length === 1 ? '' : 's'} in your library.
                </p>
              </>
            ) : (
              <p className="field__help field__help--inline">
                No videos in your library yet. Download some first, then come back to convert them to audio.
              </p>
            )}
          </div>

          <div className="field">
            <label className="field__label" htmlFor="extract-format">AUDIO FORMAT</label>
            <select
              id="extract-format"
              className="select"
              value={format}
              onChange={(event) => setFormat(event.target.value)}
              disabled={isStarting || isActive}
            >
              {FORMATS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="extract-bitrate">BITRATE {lossless ? '(lossless — ignored)' : ''}</label>
            <select
              id="extract-bitrate"
              className="select"
              value={bitrate}
              onChange={(event) => setBitrate(event.target.value)}
              disabled={isStarting || isActive || lossless}
            >
              {BITRATES.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
        </div>

        {error ? <p className="download-card__error">{error}</p> : null}

        <button
          className="primary-button"
          type="button"
          onClick={startExtraction}
          disabled={!selectedFilename || isStarting || isActive}
        >
          {isStarting || isActive ? <Loader2 size={16} className="spin" /> : <AudioLines size={16} />}
          {isStarting ? 'Starting...'
            : isActive ? `Extracting... ${Math.round(job?.progress || 0)}%`
              : selectedFilename ? 'Extract Audio' : 'Select a video first'}
        </button>
      </section>

      {job ? (
        <section className="panel panel--list audio-extractor-job">
          <div className="panel__header">
            <div>
              <h2 className="panel__title">
                {job.status === 'completed' ? 'Extraction complete' : job.status === 'error' ? 'Extraction failed' : 'Extracting audio'}
              </h2>
              <p className="panel__subtitle">
                {job.source ? cleanSourceName(job.source) : ''} → <strong>{job.format?.toUpperCase()}</strong>
              </p>
            </div>
            <span className={`status-pill ${
              job.status === 'completed' ? 'status-pill--completed'
                : job.status === 'error' ? 'status-pill--error'
                  : 'status-pill--processing'
            }`}>
              {job.status}
            </span>
          </div>

          {job.status === 'error' ? (
            <p className="download-card__error">{job.error || job.message}</p>
          ) : null}

          {isActive ? (
            <div className="whisper-job-card">
              <div className="download-card__title-row">
                <div>
                  <h3 className="download-card__title">{job.message || 'Extracting audio...'}</h3>
                  <p className="download-card__meta">
                    {job.source_duration ? `Source ${formatDuration(job.source_duration)} · ` : ''}Elapsed {formatDuration(elapsed)}
                  </p>
                </div>
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${Math.min(100, Math.max(0, job.progress || 0))}%` }} />
              </div>
              <div className="whisper-job-stats">
                <span>{Math.min(100, Math.max(0, job.progress || 0)).toFixed(0)}%</span>
                <span>ffmpeg is running — this usually takes a few seconds to a minute</span>
              </div>
            </div>
          ) : null}

          {job.status === 'completed' && job.filename ? (
            <div className="audio-extractor-result">
              <CheckCircle2 size={22} />
              <div>
                <h3 className="panel__title panel__title--tight">{job.filename}</h3>
                <p className="panel__subtitle">
                  {formatBytes(job.size_bytes)} · saved to your Library · done in {formatDuration(job.elapsed_seconds)}
                </p>
              </div>
              <a className="primary-button" href={`${API_BASE}/files/download/${encodeURIComponent(job.filename)}`} download>
                <Download size={16} /> Download
              </a>
              <button
                className="ghost-button"
                type="button"
                onClick={() => { setJob(null); setSelectedFilename(''); }}
              >
                <RefreshCw size={16} /> Extract another
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      {!job && videos.length === 0 ? (
        <section className="panel panel--list">
          <div className="empty-state">
            <Music size={28} />
            <p>Download videos first, then convert them to audio here.</p>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function cleanSourceName(filename = '') {
  return String(filename)
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim() || filename;
}
