import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, ImageIcon, RefreshCw, Trash2, X } from 'lucide-react';
import { API_BASE, api } from '../lib/api';

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'webp', 'gif', 'avif']);

const mediaExt = (filename = '') => filename.split('.').pop()?.toLowerCase() || '';
const isImage = (filename = '') => IMAGE_EXTS.has(mediaExt(filename));

const cleanTitle = (filename = '') => (
  String(filename || '')
    .replace(/\.[^.]+$/, '')
    .replace(/\s*\([A-Za-z0-9_-]{11}\)\s*$/, '')
    .trim()
);

const formatBytes = (bytes = 0) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

// Group photos by their post (same base title). Files from one Instagram
// post share the same "Post by ..." prefix with different (id) suffixes.
function groupByPost(photos) {
  const groups = new Map();
  for (const photo of photos) {
    const key = cleanTitle(photo.filename);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(photo);
  }
  return [...groups.entries()].map(([title, items]) => ({
    title,
    items: items.sort((a, b) => (a.filename || '').localeCompare(b.filename || '')),
  }));
}

function PhotoLightbox({ photos, index, onClose, onDelete, onPrev, onNext }) {
  const photo = photos[index];
  if (!photo) return null;
  const streamUrl = `${API_BASE}/stream/${encodeURIComponent(photo.filename)}`;
  const downloadUrl = `${API_BASE}/files/download/${encodeURIComponent(photo.filename)}`;

  return (
    <div
      className="photo-lightbox"
      role="dialog"
      aria-modal="true"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="photo-lightbox__topbar">
        <span className="photo-lightbox__title" title={photo.filename}>{photo.filename}</span>
        <div className="photo-lightbox__actions">
          <a className="icon-button" href={downloadUrl} download title="Download" onClick={(event) => event.stopPropagation()}>
            <Download size={16} />
          </a>
          <button className="icon-button icon-button--danger" type="button" title="Delete" onClick={(event) => { event.stopPropagation(); onDelete(photo); }}>
            <Trash2 size={16} />
          </button>
          <button className="icon-button" type="button" title="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
      </div>

      <button className="photo-lightbox__nav photo-lightbox__nav--prev" type="button" onClick={onPrev} disabled={photos.length <= 1} aria-label="Previous photo">
        <ChevronLeft size={26} />
      </button>

      <img className="photo-lightbox__image" src={streamUrl} alt={photo.filename} />

      <button className="photo-lightbox__nav photo-lightbox__nav--next" type="button" onClick={onNext} disabled={photos.length <= 1} aria-label="Next photo">
        <ChevronRight size={26} />
      </button>

      <div className="photo-lightbox__footer">
        <span>{index + 1} / {photos.length}</span>
        <span>{formatBytes(photo.size)}</span>
      </div>
    </div>
  );
}

export default function PhotosPage({ files = [], onDeleteFile, onRefreshFiles, onNotify }) {
  const [localFiles, setLocalFiles] = useState(files);

  // Always fetch the freshest file list when this page is opened, so newly
  // downloaded photos appear immediately (the `files` prop can be stale).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await api.get('/files');
        if (!cancelled) setLocalFiles(Array.isArray(response.data?.files) ? response.data.files : []);
      } catch {
        // fall back to the prop
        if (!cancelled) setLocalFiles(files);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const photos = useMemo(
    () => (localFiles || []).filter((file) => isImage(file.filename || '')),
    [localFiles],
  );
  const groups = useMemo(() => groupByPost(photos), [photos]);
  const flatPhotos = useMemo(
    () => groups.flatMap((group) => group.items),
    [groups],
  );
  const [lightboxIndex, setLightboxIndex] = useState(null);

  const notify = useCallback((message, type = 'info') => {
    if (onNotify) onNotify(message, type);
  }, [onNotify]);

  const openLightbox = (flatIndex) => setLightboxIndex(flatIndex);
  const closeLightbox = () => setLightboxIndex(null);
  const prevPhoto = () => setLightboxIndex((current) => (current === null ? null : (current - 1 + flatPhotos.length) % flatPhotos.length));
  const nextPhoto = () => setLightboxIndex((current) => (current === null ? null : (current + 1) % flatPhotos.length));

  const handleDelete = async (photo) => {
    try {
      await onDeleteFile(photo.filename);
      setLightboxIndex(null);
      setLocalFiles((current) => current.filter((item) => item.filename !== photo.filename));
      notify('Photo deleted', 'info');
    } catch (error) {
      notify(error?.response?.data?.detail || 'Unable to delete photo', 'error');
    }
  };

  const handleRefresh = async () => {
    if (onRefreshFiles) await onRefreshFiles();
    try {
      const response = await api.get('/files');
      const list = Array.isArray(response.data?.files) ? response.data.files : [];
      setLocalFiles(list);
    } catch {
      // keep current list
    }
  };

  const handleKeyDown = (event) => {
    if (lightboxIndex === null) return;
    if (event.key === 'Escape') closeLightbox();
    if (event.key === 'ArrowLeft') prevPhoto();
    if (event.key === 'ArrowRight') nextPhoto();
  };

  return (
    <div className="page-shell" onKeyDown={handleKeyDown}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Photos</h1>
          <p className="page-subtitle">
            {photos.length > 0
              ? `${photos.length} photo${photos.length === 1 ? '' : 's'} saved from Instagram posts — click any to view.`
              : 'Photos you download from Instagram posts will appear here.'}
          </p>
        </div>
        <div className="page-header__actions">
          <button className="ghost-button" type="button" onClick={handleRefresh}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {photos.length === 0 ? (
        <section className="panel panel--list">
          <div className="empty-state">
            <ImageIcon size={30} />
            <p>
              No photos yet. On the Download page, paste an Instagram post URL and click{' '}
              <strong>“Download post photos”</strong> — the images will show up here.
            </p>
          </div>
        </section>
      ) : (
        groups.map((group) => (
          <section key={group.title} className="panel panel--list photo-group">
            <div className="panel__header">
              <div>
                <h2 className="panel__title">{group.title}</h2>
                <p className="panel__subtitle">{group.items.length} photo{group.items.length === 1 ? '' : 's'}</p>
              </div>
              <span className="panel__badge">{group.items.length}</span>
            </div>
            <div className="photo-grid">
              {group.items.map((photo) => {
                const flatIndex = flatPhotos.indexOf(photo);
                return (
                  <button
                    key={photo.filename}
                    className="photo-card"
                    type="button"
                    onClick={() => openLightbox(flatIndex)}
                    title={photo.filename}
                  >
                    <img
                      className="photo-card__img"
                      src={`${API_BASE}/stream/${encodeURIComponent(photo.filename)}`}
                      alt={photo.filename}
                      loading="lazy"
                    />
                    <span className="photo-card__meta">{formatBytes(photo.size)}</span>
                  </button>
                );
              })}
            </div>
          </section>
        ))
      )}

      {lightboxIndex !== null ? (
        <PhotoLightbox
          photos={flatPhotos}
          index={lightboxIndex}
          onClose={closeLightbox}
          onDelete={handleDelete}
          onPrev={prevPhoto}
          onNext={nextPhoto}
        />
      ) : null}
    </div>
  );
}
