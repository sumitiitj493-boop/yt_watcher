import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Check,
  Copy,
  Download,
  FileText,
  Loader2,
  PenLine,
  RefreshCw,
  Save,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../lib/api';
import Skeleton from '../components/Skeleton';

const folderLabel = (folder = '') => (folder && folder.trim() ? folder.trim() : 'General');

function formatDate(value) {
  if (!value) return '';
  try {
    return new Date(value * 1000).toLocaleDateString();
  } catch {
    return '';
  }
}

export default function TranscriptsPage({ onNotify, onTranscriptsChanged }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Fetch & save form
  const [fetchUrl, setFetchUrl] = useState('');
  const [fetchFolder, setFetchFolder] = useState('');
  const [fetching, setFetching] = useState(false);

  // Search + folder filter (folder may come from ?folder= in the URL,
  // e.g. when the batch progress card links "View transcripts")
  const [query, setQuery] = useState('');
  const [activeFolder, setActiveFolder] = useState(() => {
    const folder = searchParams.get('folder');
    return folder ? folder : 'all';
  });

  // Expand / edit / clear
  const [expandedId, setExpandedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editText, setEditText] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [copyStatusId, setCopyStatusId] = useState(null);
  const [copyAllStatus, setCopyAllStatus] = useState(false);
  const [confirmClearAll, setConfirmClearAll] = useState(false);

  const notify = useCallback((message, type = 'info', duration = 3600, action = null) => {
    if (onNotify) onNotify(message, type, duration, action);
  }, [onNotify]);

  const loadItems = useCallback(async () => {
    try {
      const res = await api.get('/transcript-saver');
      setItems(Array.isArray(res.data?.transcripts) ? res.data.transcripts : []);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load saved transcripts.');
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadItems().finally(() => setLoading(false));
  }, [loadItems]);

  const refresh = useCallback(async () => {
    await loadItems();
    if (onTranscriptsChanged) onTranscriptsChanged();
  }, [loadItems, onTranscriptsChanged]);

  const folders = useMemo(() => {
    const set = new Set();
    items.forEach((item) => set.add((item.folder || '').trim()));
    const list = [...set].sort((a, b) => {
      if (a === '') return -1;
      if (b === '') return 1;
      return a.localeCompare(b);
    });
    return ['all', ...list];
  }, [items]);

  const filtered = useMemo(() => {
    let list = items;
    if (activeFolder !== 'all') {
      list = list.filter((item) => (item.folder || '').trim() === activeFolder);
    }
    const needle = query.trim().toLowerCase();
    if (needle) {
      list = list.filter((item) =>
        [item.title, item.text, item.url, item.folder]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(needle)),
      );
    }
    return list;
  }, [items, activeFolder, query]);

  const selectFolder = (folder) => {
    setActiveFolder(folder);
    if (folder === 'all') {
      setSearchParams({}, { replace: true });
    } else {
      setSearchParams({ folder }, { replace: true });
    }
  };

  // All transcripts in the current view combined into one text (title separators).
  const combinedText = useMemo(() => {
    return filtered
      .map((item) => {
        const header = `==========\n${item.title || 'Transcript'}  ·  ${folderLabel(item.folder)}\n==========`;
        return `${header}\n${item.text || ''}`;
      })
      .join('\n\n\n');
  }, [filtered]);

  const handleCopyAll = async () => {
    if (!combinedText) return;
    try {
      await navigator.clipboard.writeText(combinedText);
      setCopyAllStatus(true);
      window.setTimeout(() => setCopyAllStatus(false), 1600);
      notify(`Copied ${filtered.length} transcript${filtered.length === 1 ? '' : 's'} to clipboard`, 'success');
    } catch {
      notify('Copy failed — try Download .txt instead', 'error');
    }
  };

  const handleDownloadAll = () => {
    if (!combinedText) return;
    const folderName = activeFolder === 'all' ? 'All-Transcripts' : (activeFolder || 'General');
    const safeName = folderName.replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '') || 'Transcripts';
    const blob = new Blob([combinedText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${safeName} (${filtered.length} transcripts).txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    notify(`Downloaded ${filtered.length} transcript${filtered.length === 1 ? '' : 's'} as .txt`, 'success');
  };

  const handleFetch = async () => {
    const trimmed = fetchUrl.trim();
    if (!trimmed || fetching) return;
    setFetching(true);
    setError('');
    try {
      const res = await api.post('/transcript-saver/fetch', { url: trimmed, folder: fetchFolder.trim() });
      const saved = res.data?.transcript;
      await refresh();
      notify(saved?.title ? `Saved: ${saved.title}` : 'Transcript fetched and saved', 'success');
      setFetchUrl('');
      setFetchFolder('');
      if (saved?.id) setExpandedId(saved.id);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to fetch transcript.');
    } finally {
      setFetching(false);
    }
  };

  const handleCopy = async (item) => {
    try {
      await navigator.clipboard.writeText(item.text || '');
      setCopyStatusId(item.id);
      window.setTimeout(() => setCopyStatusId(null), 1600);
    } catch {
      notify('Copy failed — select the text manually', 'error');
    }
  };

  const startEdit = (item) => {
    setEditingId(item.id);
    setEditTitle(item.title || '');
    setEditText(item.text || '');
    setExpandedId(item.id);
  };

  const saveEdit = async () => {
    if (!editingId || savingEdit) return;
    if (!editTitle.trim() || !editText.trim()) {
      notify('Title and text cannot be empty', 'error');
      return;
    }
    setSavingEdit(true);
    try {
      await api.patch(`/transcript-saver/${editingId}`, {
        title: editTitle.trim(),
        text: editText.trim(),
      });
      setEditingId(null);
      await refresh();
      notify('Transcript updated', 'success');
    } catch (err) {
      notify(err?.response?.data?.detail || 'Unable to update transcript.', 'error');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDelete = async (id) => {
    const item = items.find((entry) => entry.id === id);
    try {
      await api.delete(`/transcript-saver/${id}`);
      if (expandedId === id) setExpandedId(null);
      if (editingId === id) setEditingId(null);
      await refresh();
      // Offer undo while the toast is visible.
      if (item) {
        notify('Transcript deleted', 'info', 6000, {
          label: 'Undo',
          onClick: async () => {
            try {
              await api.post('/transcript-saver', {
                title: item.title || 'Transcript',
                text: item.text || '',
                url: item.url || '',
                folder: item.folder || '',
              });
              await refresh();
              notify('Transcript restored', 'success');
            } catch {
              notify('Could not restore transcript', 'error');
            }
          },
        });
      } else {
        notify('Transcript deleted', 'info');
      }
    } catch (err) {
      notify(err?.response?.data?.detail || 'Unable to delete transcript.', 'error');
    }
  };

  const handleClearAll = async () => {
    if (!confirmClearAll) {
      setConfirmClearAll(true);
      window.setTimeout(() => setConfirmClearAll(false), 4000);
      notify('Click "Clear all" again to confirm', 'info');
      return;
    }
    try {
      await api.delete('/transcript-saver');
      setConfirmClearAll(false);
      setExpandedId(null);
      setEditingId(null);
      await refresh();
      notify('All saved transcripts cleared', 'info');
    } catch (err) {
      notify(err?.response?.data?.detail || 'Unable to clear transcripts.', 'error');
    }
  };

  return (
    <div className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Transcripts</h1>
          <p className="page-subtitle">
            Every transcript you fetch is auto-saved here and stays forever — even after the video is
            deleted or the page reloads. Search, copy, edit or remove them anytime.
          </p>
        </div>
        <div className="page-header__actions">
          <button className="ghost-button" type="button" onClick={refresh}>
            <RefreshCw size={16} /> Refresh
          </button>
          {items.length > 0 ? (
            <button
              className={`ghost-button ${confirmClearAll ? 'ghost-button--danger' : ''}`}
              type="button"
              onClick={handleClearAll}
            >
              <Trash2 size={16} />
              {confirmClearAll ? 'Confirm clear all' : 'Clear all'}
            </button>
          ) : null}
        </div>
      </div>

      {/* Fetch & save */}
      <section className="panel panel--form">
        <div className="panel__header panel__header--stacked">
          <div>
            <div className="section-eyebrow section-eyebrow--soft">Quick save</div>
            <h2 className="panel__title">Fetch a transcript from YouTube</h2>
            <p className="panel__subtitle">
              Paste a YouTube link and its auto transcript is fetched and saved here instantly
              (no manual save needed).
            </p>
          </div>
          <span className="panel__badge panel__badge--soft">{items.length} saved</span>
        </div>
        <form
          className="download-form"
          onSubmit={(event) => {
            event.preventDefault();
            handleFetch();
          }}
        >
          <div className="transcript-fetch-row">
            <input
              className="input"
              value={fetchUrl}
              onChange={(event) => setFetchUrl(event.target.value)}
              placeholder="https://youtube.com/watch?v=..."
              autoComplete="off"
              spellCheck="false"
            />
            <input
              className="input transcript-fetch-folder"
              value={fetchFolder}
              onChange={(event) => setFetchFolder(event.target.value)}
              placeholder="Folder (optional, e.g. Calculus)"
              maxLength={120}
            />
            <button className="primary-button" type="submit" disabled={fetching || !fetchUrl.trim()}>
              {fetching ? <Loader2 className="spin" size={16} /> : <FileText size={16} />}
              {fetching ? 'Fetching…' : 'Fetch & save'}
            </button>
          </div>
          {error ? <p className="download-card__error">{error}</p> : null}
        </form>
      </section>

      {/* Toolbar: search + folder chips */}
      <section className="panel panel--toolbar">
        <div className="search-box">
          <Search size={15} className="search-box__icon" />
          <input
            className="input input--search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search transcripts…"
          />
        </div>
        <div className="transcript-folder-chips">
          {folders.map((folder) => (
            <button
              key={folder}
              type="button"
              className={`transcript-folder-chip ${activeFolder === folder ? 'transcript-folder-chip--active' : ''}`}
              onClick={() => selectFolder(folder)}
            >
              {folder === 'all' ? 'All' : folderLabel(folder)}
              <span className="transcript-folder-chip__count">
                {folder === 'all'
                  ? items.length
                  : items.filter((item) => (item.folder || '').trim() === folder).length}
              </span>
            </button>
          ))}
        </div>
        {filtered.length > 0 ? (
          <div className="transcript-bulk-actions">
            <button className="ghost-button ghost-button--small" type="button" onClick={handleCopyAll}>
              {copyAllStatus ? <Check size={14} /> : <Copy size={14} />}
              {copyAllStatus ? 'Copied!' : `Copy all (${filtered.length})`}
            </button>
            <button className="ghost-button ghost-button--small" type="button" onClick={handleDownloadAll}>
              <Download size={14} />
              Download .txt
            </button>
          </div>
        ) : null}
      </section>

      {/* List */}
      <section className="panel panel--list">
        <div className="panel__header">
          <div>
            <h2 className="panel__title">{activeFolder === 'all' ? 'All transcripts' : folderLabel(activeFolder)}</h2>
            <p className="panel__subtitle">
              {filtered.length} transcript{filtered.length === 1 ? '' : 's'}
              {query.trim() ? ` matching “${query.trim()}”` : ''}
            </p>
          </div>
          <span className="panel__badge">{filtered.length}</span>
        </div>

        {loading && items.length === 0 ? (
          <div className="stack-list" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton-card">
                <Skeleton className="skeleton-thumb" />
                <div className="skeleton-lines">
                  <Skeleton />
                  <Skeleton />
                  <Skeleton />
                </div>
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <p>
              No saved transcripts yet. Fetch one from the Download page (paste a link and press
              Get Transcript — it auto-saves here) or use the fetch box above.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <p>{query.trim() ? 'No transcripts match your search.' : 'No transcripts in this folder yet.'}</p>
          </div>
        ) : (
          <div className="stack-list">
            {filtered.map((item) => {
              const expanded = expandedId === item.id;
              const editing = editingId === item.id;
              const previewLines = (item.text || '').split('\n').slice(0, 3).join('\n');
              return (
                <article
                  key={item.id}
                  className={`download-card ${expanded ? 'download-card--active' : ''}`}
                >
                  <div className="transcript-item">
                    <div className="transcript-item__head">
                      <button
                        className="transcript-item__expand"
                        type="button"
                        onClick={() => setExpandedId(expanded ? null : item.id)}
                        title={expanded ? 'Collapse' : 'Read full transcript'}
                      >
                        <div className="transcript-item__title-wrap">
                          <h3 className="download-card__title">{item.title}</h3>
                          <span className="download-card__meta">
                            {folderLabel(item.folder)} · {item.source === 'youtube' ? 'YouTube auto' : 'Manual'} ·{' '}
                            {item.line_count} lines · {formatDate(item.updated_at)}
                            {item.video_id ? ` · ${item.video_id}` : ''}
                          </span>
                        </div>
                      </button>
                      <div className="transcript-item__actions">
                        <button className="icon-button" type="button" title="Copy full transcript" onClick={() => handleCopy(item)}>
                          {copyStatusId === item.id ? <Check size={15} /> : <Copy size={15} />}
                        </button>
                        <button className="icon-button" type="button" title="Edit" onClick={() => startEdit(item)}>
                          <PenLine size={15} />
                        </button>
                        <button className="icon-button icon-button--danger" type="button" title="Delete" onClick={() => handleDelete(item.id)}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>

                    {editing ? (
                      <div className="transcript-item__edit">
                        <input className="input" value={editTitle} onChange={(event) => setEditTitle(event.target.value)} maxLength={300} />
                        <textarea className="transcript-textarea" rows={8} value={editText} onChange={(event) => setEditText(event.target.value)} />
                        <div className="transcript-actions">
                          <button className="primary-button" type="button" onClick={saveEdit} disabled={savingEdit}>
                            {savingEdit ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
                            Save changes
                          </button>
                          <button className="ghost-button" type="button" onClick={() => setEditingId(null)}>
                            <X size={16} /> Cancel
                          </button>
                        </div>
                      </div>
                    ) : expanded ? (
                      <pre className="transcript-item__full">{item.text}</pre>
                    ) : (
                      <button
                        className="transcript-item__preview"
                        type="button"
                        onClick={() => setExpandedId(item.id)}
                        title="Click to read full transcript"
                      >
                        {previewLines}
                        <span className="transcript-item__more">… click to read full transcript</span>
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
