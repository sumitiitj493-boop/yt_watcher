import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useNavigate, useLocation } from 'react-router-dom';
import {
  BadgeCheck,
  ChevronRight,
  Download,
  HardDrive,
  History,
  LibraryBig,
  Loader2,
  GraduationCap,
  MapPin,
  PlaySquare,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
  Music2,
  Plus,
} from 'lucide-react';

import './App.css';
import { api, API_BASE } from './lib/api';
import StudyMode from './pages/StudyMode';

const QUALITY_OPTIONS = ['best', '2160', '1440', '1080', '720', '480', '360', '240', '144'];
const FORMAT_OPTIONS = ['mp4', 'webm', 'mkv', 'mp3', 'm4a'];
const ACTIVE_STATUSES = new Set(['starting', 'downloading', 'processing']);
const ABOUT_SOCIAL_LINKS = [
  {
    label: 'GitHub',
    href: 'https://github.com/sumitiitj493-boop',
    handle: 'sumitiitj493-boop',
    Icon: GitHubMark,
    iconClass: 'about-social-icon--github',
  },
  {
    label: 'LinkedIn',
    href: 'https://www.linkedin.com/in/sumit-kumar-77bb5a39a/',
    handle: 'sumit-kumar-77bb5a39a',
    Icon: LinkedInMark,
    iconClass: 'about-social-icon--linkedin',
  },
  {
    label: 'Instagram',
    href: 'https://www.instagram.com/sumk.493/',
    handle: 'sumk.493',
    Icon: InstagramMark,
    iconClass: 'about-social-icon--instagram',
  },
];

const ABOUT_HIGHLIGHTS = [
  {
    label: 'Institute',
    value: 'IIT Jodhpur',
    Icon: GraduationCap,
  },
  {
    label: 'Program',
    value: 'B.Tech undergraduate',
    Icon: BadgeCheck,
  },
  {
    label: 'Branch',
    value: 'Artificial Intelligence & Data Science',
    Icon: Sparkles,
  },
  {
    label: 'Access',
    value: 'No login required',
    Icon: ShieldCheck,
  },
];

function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function LinkedInMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function InstagramMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
    </svg>
  );
}

function cleanTitle(value = '') {
  return value
    .split(/[\\/]/)
    .pop()
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim();
}

function formatBytes(bytes = 0) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function timeAgo(timestamp) {
  if (!timestamp) return 'just now';
  const delta = Date.now() / 1000 - timestamp;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return new Date(timestamp * 1000).toLocaleDateString();
}

function qualityLabel(value) {
  if (!value || value === 'best') return 'Best available';
  return `${value}p`;
}

function mediaExt(filename = '') {
  return filename.split('.').pop()?.toLowerCase() || '';
}

function isAudioExt(ext) {
  return ['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav'].includes(ext);
}

function isVideoExt(ext) {
  return ['mp4', 'webm', 'mkv', 'mov', 'avi'].includes(ext);
}

function isMediaFile(filename = '') {
  const ext = mediaExt(filename);
  return isAudioExt(ext) || isVideoExt(ext);
}

function safeFetchError(error, fallback) {
  return error?.response?.data?.detail || error?.response?.data?.error?.message || error?.message || fallback;
}

function detectPlatformFromString(value = '') {
  const s = String(value || '').toLowerCase();
  if (!s) return null;
  if (s.includes('instagram') || s.includes('insta')) return 'instagram';
  if (s.includes('facebook') || s.includes('fb.')) return 'facebook';
  return null;
}

function platformPlaceholderDataUrl(platform, title = '') {
  if (platform === 'instagram') {
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'><defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'><stop offset='0' stop-color='#feda75'/><stop offset='0.3' stop-color='#fa7e1e'/><stop offset='0.6' stop-color='#d62976'/><stop offset='1' stop-color='#962fbf'/></linearGradient></defs><rect width='100%' height='100%' fill='url(#g)'/><g transform='translate(160,80) scale(1.2)' fill='white' opacity='0.95'><rect x='40' y='20' width='240' height='160' rx='36' ry='36' fill='rgba(255,255,255,0.06)' stroke='rgba(255,255,255,0.12)' stroke-width='6'/><circle cx='160' cy='100' r='40' fill='white' opacity='0.12'/></g><text x='32' y='320' font-family='Arial, Helvetica, sans-serif' font-size='22' fill='rgba(255,255,255,0.92)'>${escapeHtml(title || 'Instagram video')}</text></svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }
  if (platform === 'facebook') {
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'><rect width='100%' height='100%' fill='#1877f2'/><text x='48' y='220' font-family='Arial, Helvetica, sans-serif' font-size='200' fill='white' font-weight='700'>f</text><text x='32' y='320' font-family='Arial, Helvetica, sans-serif' font-size='22' fill='rgba(255,255,255,0.98)'>${escapeHtml(title || 'Facebook video')}</text></svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }
  return '';
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function MediaThumb({ videoId, title, filename }) {
  const [failed, setFailed] = useState(false);

  // if we have a YouTube id, try the thumbnail first
  if (videoId && !failed) {
    return (
      <img
        className="media-thumb"
        src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
        alt={title}
        loading="lazy"
        onError={() => setFailed(true)}
      />
    );
  }

  // detect platform from filename/title and render built-in platform thumbnail
  const platform = detectPlatformFromString(filename || title || '');
  if (platform) {
    const dataUrl = platformPlaceholderDataUrl(platform, title);
    return <img className="media-thumb" src={dataUrl} alt={`${platform} thumbnail`} loading="lazy" />;
  }

  return (
    <div className="media-thumb media-thumb--fallback" aria-hidden="true">
      <div className="media-thumb__title" title={title}>{title || 'Unknown'}</div>
    </div>
  );
}

function StatusPill({ status }) {
  const normalized = status || 'unknown';
  const labelMap = {
    completed: 'Complete',
    downloading: 'Downloading',
    processing: 'Processing',
    starting: 'Starting',
    error: 'Error',
    cancelled: 'Cancelled',
  };

  return <span className={`status-pill status-pill--${normalized}`}>{labelMap[normalized] || normalized}</span>;
}

function ProgressBar({ value = 0 }) {
  return (
    <div className="progress-track" aria-hidden="true">
      <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

function DownloadCard({ item, onDelete, onRetry, onCancel, compact = false, onProcess, showOpen = false }) {
  const title = item.title || cleanTitle(item.filename || 'Unknown');
  const progress = Number.isFinite(item.progress)
    ? item.progress
    : Number.parseFloat(String(item.percent || '0').replace('%', '')) || 0;
  const active = ACTIVE_STATUSES.has(item.status);
  const ext = mediaExt(item.filename || '');
  const format = String(item.format || '').toLowerCase();
  const showExt = ext && ext !== format;
  const showProgress = active;
  const downloadUrl = item.filename ? `${API_BASE}/files/download/${encodeURIComponent(item.filename)}` : '';

  return (
    <article className={`download-card ${active ? 'download-card--active' : ''} ${compact ? 'download-card--compact' : ''}`}>
      <MediaThumb videoId={item.video_id} title={title} filename={item.filename} />

      <div className="download-card__body">
        <div className="download-card__title-row">
          <h3 className="download-card__title">{title}</h3>
          <StatusPill status={item.status} />
        </div>

        <div className="download-card__meta">
          <span>{item.quality ? qualityLabel(item.quality) : 'Best available'}</span>
          <span>{item.format ? item.format.toUpperCase() : 'MP4'}</span>
          {showExt ? <span>{ext.toUpperCase()}</span> : null}
          <span>{timeAgo(item.created_at)}</span>
        </div>

        {showProgress && <ProgressBar value={progress} />}

        {showProgress ? (
          <div className="download-card__stats">
            {item.speed ? <span>{item.speed}</span> : null}
            {item.eta && item.status === 'downloading' ? <span>ETA {item.eta}</span> : null}
            {item.total_bytes ? <span>{formatBytes(item.total_bytes)}</span> : null}
            {item.progress !== undefined ? <span>{Math.min(100, Math.max(0, progress)).toFixed(1)}%</span> : null}
          </div>
        ) : null}

        {item.status === 'error' && item.error ? <p className="download-card__error">{item.error}</p> : null}
      </div>

      <div className="download-card__actions">
        {active ? (
          <button className="icon-button" type="button" title="Cancel" onClick={() => onCancel(item.task_id)}>
            <X size={15} />
          </button>
        ) : null}
        {item.status === 'error' ? (
          <button className="icon-button" type="button" title="Retry" onClick={() => onRetry(item)}>
            <RotateCcw size={15} />
          </button>
        ) : null}
        {!active && onProcess && item.url ? (
          <button className="icon-button" type="button" title="Process again" onClick={() => onProcess(item)}>
            <PlaySquare size={15} />
          </button>
        ) : null}
        {item.status === 'completed' && downloadUrl ? (
          <>
            <a className="icon-button" href={downloadUrl} download title="Download to disk" role="button">
              <Download size={15} />
            </a>
            {showOpen ? (
              <a className="icon-button" href={downloadUrl} target="_blank" rel="noopener noreferrer" title="Open file" role="button">
                <PlaySquare size={15} />
              </a>
            ) : null}
          </>
        ) : null}
        <button className="icon-button icon-button--danger" type="button" title="Delete" onClick={() => onDelete(item.task_id)}>
          <Trash2 size={15} />
        </button>
      </div>
    </article>
  );
}

function FileCard({ file, active, onSelect, onDelete }) {
  const title = file.title || cleanTitle(file.filename || 'Unknown file');
  const ext = (file.ext || mediaExt(file.filename || '')).toLowerCase();
  const downloadUrl = `${API_BASE}/files/download/${encodeURIComponent(file.filename)}`;

  return (
    <article className={`file-card ${active ? 'file-card--active' : ''}`} role="button" tabIndex={0} onClick={() => onSelect(file)} onKeyDown={(event) => {
      if (event.key === 'Enter') onSelect(file);
    }}>
      <div className="file-card__thumb">
        <MediaThumb videoId={file.video_id} title={title} filename={file.filename} />
      </div>

      <div className="file-card__body">
        <h3 className="file-card__title">{title}</h3>
        <p className="file-card__meta">{ext.toUpperCase() || 'FILE'} · {formatBytes(file.size)} · {timeAgo(file.created_at)}</p>
        <div className="file-card__actions">
          <a className="icon-button" href={downloadUrl} download title="Download file" onClick={(event) => event.stopPropagation()}>
            <Download size={15} />
          </a>
          <button className="icon-button" type="button" title="Add to playlist" onClick={(event) => { event.stopPropagation(); window.fetch(`${API_BASE}/playlist/add/${encodeURIComponent(file.filename)}`, { method: 'POST' }).then(() => { window.alert('Added to playlist'); }).catch(() => { window.alert('Failed to add to playlist'); }); }}>
            <Plus size={15} />
          </button>
          <button className="icon-button icon-button--danger" type="button" title="Delete file" onClick={(event) => {
            event.stopPropagation();
            onDelete(file.filename);
          }}>
            <Trash2 size={15} />
          </button>
        </div>
      </div>
    </article>
  );
}

function ToastStack({ toasts }) {
  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast--${toast.type}`}>
          <span className="toast__dot" />
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}

function SectionHeader({ title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        <p className="page-subtitle">{subtitle}</p>
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </div>
  );
}

function AboutPage() {
  const portraitUrl = `${API_BASE}/about/photo`;
  const [portraitFailed, setPortraitFailed] = useState(false);

  return (
    <div className="page-shell about-shell">
      <section className="panel about-hero">
        <div className="about-hero__copy">
          <div className="about-eyebrow">
            <Sparkles size={14} />
            About Me
          </div>

          <h1 className="about-title">Sumit Kumar</h1>

          <p className="about-lede">
            I am an IIT Jodhpur undergraduate currently pursuing B.Tech in Artificial Intelligence and Data Science.
            I like building fast, focused tools with a clean interface, calm visuals, and zero login friction.
          </p>

          <div className="about-badges">
            <span className="about-badge">
              <MapPin size={14} />
              IIT Jodhpur
            </span>
            <span className="about-badge">
              <ShieldCheck size={14} />
              No login required
            </span>
            <span className="about-badge">
              <BadgeCheck size={14} />
              All rights reserved
            </span>
          </div>

          <div className="about-cta">
            <Link className="primary-button" to="/download">
              <Download size={16} />
              Go to Download
            </Link>
            <a className="ghost-button" href="#about-links">
              <ChevronRight size={16} />
              Find me online
            </a>
          </div>
        </div>

        <div className="about-hero__visual">
          <div className="about-profile-card">
            <div className="about-profile-image-wrap">
              {portraitFailed ? (
                <span className="about-profile-placeholder" aria-hidden="true">SK</span>
              ) : (
                <img
                  className="about-profile-image"
                  src={portraitUrl}
                  alt="Sumit Kumar portrait"
                  loading="lazy"
                  onError={() => setPortraitFailed(true)}
                />
              )}
            </div>

            <div className="about-profile-info">
              <span className="about-profile-name">Sumit Kumar</span>
              <span className="about-profile-role">AI & Data Science</span>
            </div>
          </div>

          <div className="about-stat-grid">
            <div className="about-stat-chip">
              <span className="about-stat-chip__label">Institute</span>
              <strong className="about-stat-chip__value">IIT Jodhpur</strong>
            </div>
            <div className="about-stat-chip">
              <span className="about-stat-chip__label">Access</span>
              <strong className="about-stat-chip__value">Open</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="about-section-grid">
        <article className="panel about-card about-card--full about-story">
          <div className="about-section-eyebrow">My Story</div>
          <h2 className="about-section-title">Built for people who just want to read, stay, and download</h2>
          <div className="about-section-body">
            <p>
              My focus is simple: learn deeply, build clearly, and make tools feel effortless. I am currently pursuing
              B.Tech in Artificial Intelligence and Data Science at IIT Jodhpur, and I enjoy creating products that are
              practical, direct, and visually polished.
            </p>
            <p>
              This space is open to everyone. There is no login wall, no account setup, and no extra steps. Just open
              the link, read about me, and download what you need.
            </p>
          </div>

          <div className="about-story-divider" />

          <div className="about-story-footer">
            <span>Sumit Kumar</span>
            <span>All rights reserved.</span>
          </div>
        </article>

        <article className="panel about-card">
          <div className="about-section-eyebrow">At a Glance</div>
          <div className="about-glance-list">
            {ABOUT_HIGHLIGHTS.map(({ label, value, Icon }) => (
              <div key={label} className="about-glance-row">
                <div className="about-glance-icon">
                  <Icon size={14} />
                </div>
                <div>
                  <div className="about-glance-label">{label}</div>
                  <div className="about-glance-value">{value}</div>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel about-card" id="about-links">
          <div className="about-section-eyebrow">Find Me Online</div>
          <div className="about-social-grid">
            {ABOUT_SOCIAL_LINKS.map(({ label, href, handle, Icon, iconClass }) => (
              <a key={label} className="about-social-item" href={href} target="_blank" rel="noreferrer">
                <div className={`about-social-icon ${iconClass}`}>
                  <Icon size={16} />
                </div>
                <div>
                  <div className="about-social-platform">{label}</div>
                  <div className="about-social-handle">{handle || href.replace(/^https?:\/\//, '')}</div>
                </div>
                <span className="about-social-arrow" aria-hidden="true">
                  <ChevronRight size={14} />
                </span>
              </a>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}

function DownloadPage({ downloads, currentTaskId, onStartDownload, onStartSocialDownload, onDeleteDownload, onRetryDownload, onCancelDownload }) {
  const [url, setUrl] = useState('');
  const [quality, setQuality] = useState('1080');
  const [format, setFormat] = useState('mp4');
  const [socialUrl, setSocialUrl] = useState('');
  const [socialQuality, setSocialQuality] = useState('best');
  const [socialFormat, setSocialFormat] = useState('mp4');
  const [submitting, setSubmitting] = useState(false);
  const [socialSubmitting, setSocialSubmitting] = useState(false);
  const [mode, setMode] = useState('youtube'); // 'youtube' or 'social'
  const activeDownloads = downloads.filter((item) => ACTIVE_STATUSES.has(item.status));
  const currentTask = currentTaskId ? downloads.find((d) => d.task_id === currentTaskId) : null;

  const location = useLocation();
  useEffect(() => {
    const state = location?.state || {};
    if (state?.autoStart && state?.url) {
      const u = state.url;
      const q = state.quality || 'best';
      const f = state.format || 'mp4';
      setUrl(u);
      setQuality(q === '1080' ? '1080' : q);
      setFormat(f);
      (async () => {
        try {
          await onStartDownload({ url: u, quality: q, format: f });
          setUrl('');
        } catch (e) {
          // ignore errors here — they will be surfaced elsewhere
        }
      })();
    }
  }, [location, onStartDownload]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;

    setSubmitting(true);
    try {
      await onStartDownload({ url: trimmed, quality, format });
      setUrl('');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSocialSubmit = async (event) => {
    event.preventDefault();
    const trimmed = socialUrl.trim();
    if (!trimmed) return;
    if (!trimmed.includes('instagram.com') && !trimmed.includes('facebook.com') && !trimmed.includes('fb.com') && !trimmed.includes('fb.watch')) {
      pushToast('Only Instagram or Facebook links are supported', 'error');
      return;
    }

    setSocialSubmitting(true);
    try {
      await onStartSocialDownload({ url: trimmed, quality: socialQuality, format: socialFormat });
      setSocialUrl('');
    } catch (err) {
      // onStartSocialDownload surfaces errors as toasts; show a fallback
      pushToast('Failed to start social download', 'error');
    } finally {
      setSocialSubmitting(false);
    }
  };

  return (
    <div className="page-shell">
      <SectionHeader
        title="Download Video"
        subtitle="Paste a YouTube URL, process it, then choose to watch online or download the saved file."
      />

      {/* Toggle Switch */}
      <section className="panel panel--toggle">
        <div className="download-mode-toggle">
          <button
            className={`toggle-button ${mode === 'youtube' ? 'toggle-button--active' : ''}`}
            onClick={() => setMode('youtube')}
          >
            YouTube
          </button>
          <button
            className={`toggle-button ${mode === 'social' ? 'toggle-button--active' : ''}`}
            onClick={() => setMode('social')}
          >
            Social Media
          </button>
          <span className="toggle-slider" style={{
            left: mode === 'youtube' ? '0%' : '50%'
          }} />
        </div>
      </section>

      {/* YouTube Download Form */}
      {mode === 'youtube' && (
        <section className="panel panel--form">
          <form onSubmit={handleSubmit} className="download-form">
            <div className="field field--full">
              <label className="field__label" htmlFor="video-url">VIDEO URL</label>
              <input
                id="video-url"
                className="input"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                autoComplete="off"
                spellCheck="false"
              />
            </div>

            <div className="form-grid">
              <div className="field">
                <label className="field__label" htmlFor="quality">QUALITY</label>
                <select id="quality" className="select" value={quality} onChange={(event) => setQuality(event.target.value)}>
                  {QUALITY_OPTIONS.map((option) => (
                    <option key={option} value={option}>{qualityLabel(option)}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="field__label" htmlFor="format">FORMAT</label>
                <select id="format" className="select" value={format} onChange={(event) => setFormat(event.target.value)}>
                  {FORMAT_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option.toUpperCase()}</option>
                  ))}
                </select>
              </div>
            </div>

            <button className="primary-button" type="submit" disabled={submitting || !url.trim()}>
              {submitting ? <Loader2 className="spinner" size={16} /> : <Download size={16} />}
              {submitting ? 'Processing…' : 'Process Link'}
            </button>
          </form>
        </section>
      )}

      {/* Social Media Download Form */}
      {mode === 'social' && (
        <section className="panel panel--form social-download-panel">
          <div className="panel__header panel__header--stacked">
            <div>
          <div className="section-eyebrow section-eyebrow--soft">Public social video download</div>
              <h2 className="panel__title">Instagram & Facebook</h2>
                  <p className="panel__subtitle">
                Paste a public Instagram or Facebook link. This uses the same downloader engine, but keeps the feature
                separate from YouTube.
                  </p>
            </div>
            <span className="panel__badge panel__badge--soft">Social</span>
          </div>

          <form onSubmit={handleSocialSubmit} className="download-form">
            <div className="field field--full">
              <label className="field__label" htmlFor="social-url">PUBLIC LINK</label>
              <input
                id="social-url"
                className="input"
                value={socialUrl}
                onChange={(event) => setSocialUrl(event.target.value)}
                placeholder="https://instagram.com/... or https://facebook.com/..."
                autoComplete="off"
                spellCheck="false"
              />
            </div>

            <div className="form-grid">
              <div className="field">
                <label className="field__label" htmlFor="social-quality">QUALITY</label>
                <select id="social-quality" className="select" value={socialQuality} onChange={(event) => setSocialQuality(event.target.value)}>
                  {QUALITY_OPTIONS.map((option) => (
                    <option key={option} value={option}>{qualityLabel(option)}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="field__label" htmlFor="social-format">FORMAT</label>
                <select id="social-format" className="select" value={socialFormat} onChange={(event) => setSocialFormat(event.target.value)}>
                  {FORMAT_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option.toUpperCase()}</option>
                  ))}
                </select>
              </div>
            </div>

            <button className="primary-button" type="submit" disabled={socialSubmitting || !socialUrl.trim()}>
              {socialSubmitting ? <Loader2 className="spinner" size={16} /> : <Download size={16} />}
              {socialSubmitting ? 'Processing…' : 'Download Public Video'}
            </button>
          </form>
        </section>
      )}

      <section className="panel panel--list">
        <div className="panel__header">
          <div>
            <h2 className="panel__title">Active Downloads</h2>
            <p className="panel__subtitle">Live progress, ETA, and cancel controls.</p>
          </div>
          <span className="panel__badge">{activeDownloads.length}</span>
        </div>

        {activeDownloads.length === 0 && !currentTask ? (
          <div className="empty-state">
            <PlaySquare size={32} />
            <p>No active downloads right now.</p>
          </div>
        ) : (
          <div className="stack-list">
            {activeDownloads.map((item) => (
              <DownloadCard
                key={item.task_id}
                item={item}
                onDelete={onDeleteDownload}
                onRetry={onRetryDownload}
                onCancel={onCancelDownload}
              />
            ))}
            {currentTask && !ACTIVE_STATUSES.has(currentTask.status) ? (
              <DownloadCard
                key={currentTask.task_id}
                item={currentTask}
                onDelete={onDeleteDownload}
                onRetry={onRetryDownload}
                onCancel={onCancelDownload}
                showOpen
              />
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}

function HistoryPage({ downloads, onDeleteDownload, onRetryDownload, onCancelDownload, onRefreshDownloads, onClearDownloads, onProcessFromHistory }) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return downloads;

    return downloads.filter((item) => {
      const title = (item.title || cleanTitle(item.filename || '') || '').toLowerCase();
      const filename = (item.filename || '').toLowerCase();
      const url = (item.url || '').toLowerCase();
      const quality = String(item.quality || '').toLowerCase();
      const format = String(item.format || '').toLowerCase();
      const status = String(item.status || '').toLowerCase();
      return [title, filename, url, quality, format, status].some((value) => value.includes(needle));
    });
  }, [downloads, query]);

  return (
    <div className="page-shell">
      <SectionHeader
        title="Download History"
        subtitle="Search, retry, and manage completed or failed jobs."
        actions={(
          <>
            <button className="ghost-button" type="button" onClick={onRefreshDownloads}>
              <RefreshCw size={16} />
              Refresh
            </button>
            {downloads.length > 0 ? (
              <button className="ghost-button ghost-button--danger" type="button" onClick={onClearDownloads}>
                <Trash2 size={16} />
                Clear All
              </button>
            ) : null}
          </>
        )}
      />

      <section className="panel panel--toolbar">
        <div className="search-box">
          <Search size={16} className="search-box__icon" />
          <input
            className="input input--search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search history..."
          />
        </div>
      </section>

      <section className="panel panel--list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <History size={32} />
            <p>No downloads yet.</p>
          </div>
        ) : (
          <div className="stack-list">
            {filtered.map((item) => (
              <DownloadCard
                key={item.task_id}
                item={item}
                onDelete={onDeleteDownload}
                onRetry={onRetryDownload}
                onCancel={onCancelDownload}
                onProcess={onProcessFromHistory ? () => onProcessFromHistory({ url: item.url, quality: item.quality, format: item.format }) : undefined}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function LibraryPage({ files, onDeleteFile, onRefreshFiles, onClearFiles }) {
  const [query, setQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const mediaFiles = useMemo(() => files.filter((file) => isMediaFile(file.filename || '')), [files]);

  useEffect(() => {
    if (mediaFiles.length === 0) {
      setSelectedFile(null);
      return;
    }

    if (!selectedFile || !mediaFiles.some((file) => file.filename === selectedFile.filename)) {
      setSelectedFile(mediaFiles[0]);
    }
  }, [mediaFiles, selectedFile]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return mediaFiles;
    return mediaFiles.filter((file) => {
      const title = (file.title || cleanTitle(file.filename || '') || '').toLowerCase();
      const filename = (file.filename || '').toLowerCase();
      const ext = String(file.ext || '').toLowerCase();
      const videoId = String(file.video_id || '').toLowerCase();
      return [title, filename, ext, videoId].some((value) => value.includes(needle));
    });
  }, [mediaFiles, query]);

  const previewFile = selectedFile && filtered.some((file) => file.filename === selectedFile.filename)
    ? selectedFile
    : filtered[0] || null;

  const previewUrl = previewFile ? `${API_BASE}/stream/${encodeURIComponent(previewFile.filename)}` : '';
  const previewExt = previewFile ? mediaExt(previewFile.filename) : '';
  const previewTitle = previewFile ? previewFile.title || cleanTitle(previewFile.filename) : '';
  const previewThumbUrl = previewFile?.video_id ? `https://img.youtube.com/vi/${previewFile.video_id}/hqdefault.jpg` : '';

  // generate a thumbnail from the video's first frame when no external thumbnail is available
  const videoRef = useRef(null);
  const [generatedThumb, setGeneratedThumb] = useState('');

  useEffect(() => {
    setGeneratedThumb('');
    if (!previewUrl || !isVideoExt(previewExt) || previewFile?.video_id) return undefined;

    const video = videoRef.current;
    if (!video) return undefined;

    let mounted = true;

    const capture = () => {
      try {
        const w = video.videoWidth || 1280;
        const h = video.videoHeight || Math.round(w * 9 / 16);
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, w, h);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
        if (mounted) setGeneratedThumb(dataUrl);
      } catch (err) {
        // ignore capture errors
      }
    };

    const onLoaded = () => {
      try {
        // Some browsers need a tiny seek to populate the first frame
        if (video.duration && video.duration > 0) {
          const t = Math.min(0.05, Math.max(0, video.duration * 0.01));
          const onSeeked = () => {
            capture();
            video.removeEventListener('seeked', onSeeked);
          };
          video.addEventListener('seeked', onSeeked);
          try { video.currentTime = t; } catch (e) { capture(); }
        } else {
          capture();
        }
      } catch (e) {
        capture();
      }
    };

    video.addEventListener('loadedmetadata', onLoaded);
    if (video.readyState >= 2) onLoaded();

    return () => {
      mounted = false;
      video.removeEventListener('loadedmetadata', onLoaded);
    };
  }, [previewUrl, previewExt, previewFile?.video_id]);

  const previewPlatform = detectPlatformFromString((previewFile?.filename || '') + ' ' + (previewFile?.title || ''));
  const platformPlaceholder = previewPlatform ? platformPlaceholderDataUrl(previewPlatform, previewTitle) : '';
  const effectiveThumb = previewFile?.video_id ? previewThumbUrl : (generatedThumb || platformPlaceholder || '');

  const handleDeleteFile = useCallback(async (filename) => {
    const deletingPreview = previewFile?.filename === filename;
    if (deletingPreview) {
      setSelectedFile(null);
      await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
    }

    await onDeleteFile(filename);
  }, [filtered, mediaFiles, onDeleteFile, previewFile?.filename]);

  return (
    <div className="page-shell">
      <SectionHeader
        title="Library"
        subtitle={`${mediaFiles.length} saved file${mediaFiles.length === 1 ? '' : 's'} ready for playback and download.`}
        actions={(
          <>
            <button className="ghost-button" type="button" onClick={onRefreshFiles}>
              <RefreshCw size={16} />
              Refresh
            </button>
            {mediaFiles.length > 0 && onClearFiles ? (
              <button
                className="ghost-button ghost-button--danger"
                type="button"
                onClick={async () => {
                  const ok = window.confirm('Are you sure you want to delete ALL files? This cannot be undone.');
                  if (!ok) return;
                  // Pause and release any active preview players to allow file deletion on Windows
                  try {
                    const video = videoRef?.current;
                    if (video) {
                      video.pause();
                      video.removeAttribute('src');
                      try { video.load(); } catch (e) { /* ignore */ }
                    }
                    // stop any audio players as well
                    document.querySelectorAll('audio').forEach((a) => {
                      a.pause();
                      a.removeAttribute('src');
                      try { a.load(); } catch (e) { /* ignore */ }
                    });
                    // Give the browser a moment to release file handles
                    await new Promise((r) => setTimeout(r, 200));
                  } catch (e) {
                    // ignore UI errors
                  }
                  await onClearFiles();
                }}
              >
                <Trash2 size={16} />
                Clear All
              </button>
            ) : null}
          </>
        )}
      />

      <section className="panel panel--toolbar">
        <div className="search-box">
          <Search size={16} className="search-box__icon" />
          <input
            className="input input--search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search files..."
          />
        </div>
      </section>

      {previewFile ? (
        <section className="panel panel--preview">
          <div className="preview-media">
            {isVideoExt(previewExt) ? (
              <video
                ref={videoRef}
                className="preview-player"
                src={previewUrl}
                controls
                preload="metadata"
                poster={effectiveThumb || undefined}
              />
            ) : isAudioExt(previewExt) ? (
              <div className="preview-audio">
                <div className="preview-audio__art">
                  {previewFile.video_id ? (
                    <img src={`https://img.youtube.com/vi/${previewFile.video_id}/hqdefault.jpg`} alt={previewTitle} />
                  ) : (
                    <Music2 size={28} />
                  )}
                </div>
                <audio className="preview-audio__player" src={previewUrl} controls preload="metadata" />
              </div>
            ) : (
              <div className="empty-state empty-state--compact">
                <HardDrive size={30} />
                <p>Preview not available for this file type.</p>
              </div>
            )}
          </div>

          <div className="preview-meta">
            <div className="preview-thumb-card">
              {effectiveThumb ? (
                <img src={effectiveThumb} alt={`${previewTitle} thumbnail`} loading="lazy" />
              ) : (
                <div className="preview-thumb-card__fallback">
                  <div className="preview-thumb-card__title">{previewTitle}</div>
                </div>
              )}
            </div>

            <div>
              <h2 className="panel__title panel__title--tight">{previewTitle}</h2>
              <p className="panel__subtitle">{previewExt.toUpperCase()} · {formatBytes(previewFile.size)} · {timeAgo(previewFile.created_at)}</p>
            </div>
            <div className="preview-actions">
              <a className="ghost-button" href={`${API_BASE}/files/download/${encodeURIComponent(previewFile.filename)}`} download>
                <Download size={16} />
                Download
              </a>
              <button className="ghost-button ghost-button--danger" type="button" onClick={() => handleDeleteFile(previewFile.filename)}>
                <Trash2 size={16} />
                Remove
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <section className="panel panel--list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <LibraryBig size={32} />
            <p>Your library is empty.</p>
          </div>
        ) : (
          <div className="library-grid">
            {filtered.map((file) => (
              <FileCard
                key={file.filename}
                file={file}
                active={selectedFile?.filename === file.filename}
                onSelect={setSelectedFile}
                onDelete={handleDeleteFile}
                compact
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Sidebar({ downloads, files, storageBytes }) {
  const activeDownloads = downloads.filter((item) => ACTIVE_STATUSES.has(item.status)).length;

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand__mark">
          <PlaySquare size={18} />
        </div>
        <div>
          <h2 className="brand__title">YT Suite</h2>
          <p className="brand__subtitle">PRIVATE</p>
        </div>
      </div>

      <nav className="nav-stack" aria-label="Primary">
        <NavLink className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`} to="/about" end>
          <Sparkles size={18} />
          <span>About</span>
        </NavLink>

        <NavLink className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`} to="/download" end>
          <Download size={18} />
          <span>Download</span>
        </NavLink>

        <NavLink className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`} to="/history" end>
          <History size={18} />
          <span>History</span>
          {activeDownloads > 0 ? <span className="nav-link__badge">{activeDownloads}</span> : null}
        </NavLink>

        <NavLink className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`} to="/library" end>
          <LibraryBig size={18} />
          <span>Library</span>
          {files.length > 0 ? <span className="nav-link__badge">{files.length}</span> : null}
        </NavLink>
      </nav>

      <div className="sidebar__footer">
        <div className="usage-card">
          <div className="usage-card__label">Storage</div>
          <div className="usage-card__value">{formatBytes(storageBytes)}</div>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  const [downloads, setDownloads] = useState([]);
  const [files, setFiles] = useState([]);
  const [toasts, setToasts] = useState([]);
  const toastTimers = useRef([]);
  const [currentTaskId, setCurrentTaskId] = useState(null);

  const pushToast = useCallback((message, type = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((current) => [...current, { id, message, type }].slice(-4));
    const timer = window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 3600);
    toastTimers.current.push(timer);
  }, []);

  useEffect(() => () => {
    toastTimers.current.forEach((timer) => window.clearTimeout(timer));
    toastTimers.current = [];
  }, []);

  const refreshDownloads = useCallback(async () => {
    try {
      const response = await api.get('/downloads');
      setDownloads(Array.isArray(response.data?.downloads) ? response.data.downloads : []);
    } catch {
      // polling should stay quiet on transient failures
    }
  }, []);

  const refreshFiles = useCallback(async () => {
    try {
      const response = await api.get('/files');
      setFiles(Array.isArray(response.data?.files) ? response.data.files : []);
    } catch {
      // polling should stay quiet on transient failures
    }
  }, []);

  const activeDownloadCount = useMemo(
    () => downloads.filter((item) => ACTIVE_STATUSES.has(item.status)).length,
    [downloads],
  );

  useEffect(() => {
    refreshDownloads();
    refreshFiles();
  }, [refreshDownloads, refreshFiles]);

  useEffect(() => {
    if (!activeDownloadCount) return undefined;

    const downloadTimer = window.setInterval(() => {
      refreshDownloads();
      refreshFiles();
    }, 2000);
    return () => {
      window.clearInterval(downloadTimer);
    };
  }, [activeDownloadCount, refreshDownloads, refreshFiles]);

  const storageBytes = useMemo(() => files.reduce((sum, file) => sum + (file.size || 0), 0), [files]);

  const startDownload = useCallback(async ({ url, quality, format }) => {
    if (!startDownload._inProgress) startDownload._inProgress = false;
    if (startDownload._inProgress) return;
    startDownload._inProgress = true;
    try {
      const res = await api.post('/download', { url, quality, format });
      const tid = res?.data?.task_id;
      if (tid) setCurrentTaskId(tid);
      pushToast('Download started', 'success');
      await refreshDownloads();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to start download'), 'error');
    } finally {
      startDownload._inProgress = false;
    }
  }, [pushToast, refreshDownloads]);

  const startSocialDownload = useCallback(async ({ url, quality, format }) => {
    if (!startSocialDownload._inProgress) startSocialDownload._inProgress = false;
    if (startSocialDownload._inProgress) return;
    startSocialDownload._inProgress = true;
    try {
      const res = await api.post('/social-download', { url, quality, format });
      const tid = res?.data?.task_id;
      if (tid) setCurrentTaskId(tid);
      pushToast('Social download started', 'success');
      await refreshDownloads();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to start social download'), 'error');
    } finally {
      startSocialDownload._inProgress = false;
    }
  }, [pushToast, refreshDownloads]);

  const cancelDownload = useCallback(async (taskId) => {
    try {
      await api.post(`/cancel/${encodeURIComponent(taskId)}`);
      pushToast('Cancel requested', 'info');
      await refreshDownloads();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to cancel download'), 'error');
    }
  }, [pushToast, refreshDownloads]);

  const deleteDownload = useCallback(async (taskId) => {
    try {
      await api.delete(`/downloads/${encodeURIComponent(taskId)}`);
      pushToast('Download removed', 'info');
      // if we're deleting the currently tracked task, clear it
      if (taskId === currentTaskId) setCurrentTaskId(null);
      await refreshDownloads();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to delete download'), 'error');
    }
  }, [pushToast, refreshDownloads]);

  const clearDownloads = useCallback(async () => {
    try {
      await api.post('/downloads/clear');
      pushToast('History cleared', 'info');
      await refreshDownloads();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to clear history'), 'error');
    }
  }, [pushToast, refreshDownloads]);

  const retryDownload = useCallback(async (item) => {
    if (!item?.url) {
      pushToast('Cannot retry without the original URL', 'error');
      return;
    }

    await startDownload({
      url: item.url,
      quality: item.quality || 'best',
      format: item.format || 'mp4',
    });
  }, [pushToast, startDownload]);

  const deleteFile = useCallback(async (filename) => {
    try {
      await api.delete(`/delete/${encodeURIComponent(filename)}`);
      pushToast('File deleted', 'info');
      await refreshFiles();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to delete file'), 'error');
    }
  }, [pushToast, refreshFiles]);

  const navigate = useNavigate();

  const openDownloadFromHistory = useCallback(({ url, quality = 'best', format = 'mp4' }) => {
    if (!url) return;

    navigate('/download', { state: { url, quality, format, autoStart: true } });
  }, [navigate]);

  const reprocessInProgress = useRef(new Set());
  const reprocessFromHistory = useCallback(async (item) => {
    const taskId = item?.task_id;
    if (!taskId) return;
    if (reprocessInProgress.current.has(taskId)) return;
    reprocessInProgress.current.add(taskId);
    try {
      const resp = await api.post(`/reprocess/${encodeURIComponent(taskId)}`);
      const data = resp?.data || {};
      if (data.already_exists) {
        pushToast('File already exists in Library', 'info');
        await refreshFiles();
        navigate('/library');
      } else {
        const newId = data.task_id;
        if (newId) setCurrentTaskId(newId);
        pushToast('Download started', 'success');
        await refreshDownloads();
        navigate('/download');
      }
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to reprocess'), 'error');
    } finally {
      reprocessInProgress.current.delete(taskId);
    }
  }, [pushToast, refreshDownloads, refreshFiles, navigate]);

  const clearFiles = useCallback(async () => {
    try {
      const resp = await api.post('/files/clear');
      const data = resp?.data || {};
      const { deleted = 0, failed = [] } = data;
      if (failed && failed.length > 0) {
        pushToast(`Deleted ${deleted} files. ${failed.length} could not be deleted (in use).`, 'warning');
        console.warn('Failed to delete files:', failed);
      } else {
        pushToast('All files deleted', 'info');
      }
      await refreshFiles();
    } catch (error) {
      pushToast(safeFetchError(error, 'Failed to clear files'), 'error');
    }
  }, [pushToast, refreshFiles]);

  return (
    <div className="app-shell">
      <Sidebar downloads={downloads} files={files} storageBytes={storageBytes} />

      <main className="main-stage">
        <Routes>
          <Route path="/" element={<Navigate to="/about" replace />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/download" element={<DownloadPage downloads={downloads} currentTaskId={currentTaskId} onStartDownload={startDownload} onStartSocialDownload={startSocialDownload} onDeleteDownload={deleteDownload} onRetryDownload={retryDownload} onCancelDownload={cancelDownload} />} />
          <Route path="/history" element={<HistoryPage downloads={downloads} onDeleteDownload={deleteDownload} onRetryDownload={retryDownload} onCancelDownload={cancelDownload} onRefreshDownloads={refreshDownloads} onClearDownloads={clearDownloads} onProcessFromHistory={reprocessFromHistory} />} />
          <Route path="/library" element={<LibraryPage files={files} onDeleteFile={deleteFile} onRefreshFiles={refreshFiles} onClearFiles={clearFiles} />} />
          <Route path="/watch/:filename" element={<StudyMode />} />
          <Route path="*" element={<Navigate to="/download" replace />} />
        </Routes>
      </main>

      <ToastStack toasts={toasts} />
    </div>
  );
}
