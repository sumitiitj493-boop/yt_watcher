import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Plus, X } from 'lucide-react';
import { api } from '../lib/api';

/**
 * Modal shown when the user wants to add file(s) to a playlist.
 * Lets them pick an existing playlist or type a name to create a new one,
 * exactly like YouTube's "Save to playlist" dialog.
 *
 * Props:
 *  - items: [{ filename, title }]  — one or many files to add
 */
export default function PlaylistPicker({ items = [], onClose, onAdded }) {
  const filenames = items.map((item) => item.filename).filter(Boolean);
  const single = filenames.length === 1;
  const displayName = single
    ? (items[0]?.title || items[0]?.filename || 'this item')
    : `${filenames.length} items selected`;

  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [mode, setMode] = useState('existing'); // 'existing' | 'new'
  const [newName, setNewName] = useState('');
  const [error, setError] = useState('');
  const newNameRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/playlists');
      const list = Array.isArray(response.data?.playlists) ? response.data.playlists : [];
      setPlaylists(list);
      setSelectedId((current) => (
        current !== null && list.some((playlist) => playlist.id === current)
          ? current
          : (list[0]?.id ?? null)
      ));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load playlists');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (mode === 'new') newNameRef.current?.focus();
  }, [mode]);

  const submit = async () => {
    if (submitting || filenames.length === 0) return;
    setError('');
    let targetId;
    let targetName;

    if (mode === 'new') {
      const name = newName.trim();
      if (!name) {
        setError('Enter a name for the new playlist');
        newNameRef.current?.focus();
        return;
      }
      setSubmitting(true);
      try {
        const created = await api.post('/playlists', { name });
        targetId = created.data?.playlist?.id;
        targetName = created.data?.playlist?.name || name;
      } catch (err) {
        setError(err?.response?.data?.detail || 'Unable to create playlist');
        setSubmitting(false);
        return;
      }
    } else {
      targetId = selectedId;
      targetName = playlists.find((playlist) => playlist.id === selectedId)?.name || '';
    }

    if (!targetId) {
      setError('Choose a playlist first');
      setSubmitting(false);
      return;
    }

    try {
      if (single) {
        await api.post(`/playlists/${targetId}/items`, { filename: filenames[0] });
      } else {
        await api.post(`/playlists/${targetId}/items/batch`, { filenames });
      }
      onAdded?.(targetName);
      onClose?.();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to add item to playlist');
      setSubmitting(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="playlist-picker-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div className="modal-card">
        <div className="modal-card__header">
          <h2 id="playlist-picker-title">Add to playlist</h2>
          <button className="icon-button" type="button" onClick={onClose} title="Close" aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <p className="modal-card__subtitle" title={displayName}>
          {single ? displayName : `${displayName} — choose a playlist or create one`}
        </p>

        {loading ? (
          <div className="modal-card__body modal-card__body--center">
            <Loader2 size={18} className="spin" /> Loading playlists…
          </div>
        ) : (
          <div className="modal-card__body">
            <div className="playlist-pick-list">
              {playlists.length === 0 ? (
                <p className="playlist-pick-empty">No playlists yet — create the first one below.</p>
              ) : (
                playlists.map((playlist) => (
                  <label
                    key={playlist.id}
                    className={`playlist-pick-row ${mode === 'existing' && selectedId === playlist.id ? 'playlist-pick-row--selected' : ''}`}
                  >
                    <input
                      type="radio"
                      name="playlist-target"
                      checked={mode === 'existing' && selectedId === playlist.id}
                      onChange={() => {
                        setMode('existing');
                        setSelectedId(playlist.id);
                      }}
                    />
                    <span className="playlist-pick-row__name">{playlist.name}</span>
                    <span className="playlist-pick-row__count">
                      {playlist.item_count} item{playlist.item_count === 1 ? '' : 's'}
                    </span>
                  </label>
                ))
              )}
            </div>

            <div className="playlist-pick-new">
              <button
                type="button"
                className={`playlist-pick-new__toggle ${mode === 'new' ? 'playlist-pick-new__toggle--active' : ''}`}
                onClick={() => setMode(mode === 'new' ? 'existing' : 'new')}
              >
                <Plus size={14} />
                {mode === 'new' ? 'Pick an existing playlist instead' : 'Create a new playlist…'}
              </button>
              {mode === 'new' ? (
                <input
                  ref={newNameRef}
                  className="input"
                  type="text"
                  value={newName}
                  onChange={(event) => setNewName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') submit();
                  }}
                  placeholder="New playlist name"
                  maxLength={120}
                />
              ) : null}
            </div>

            {error ? <div className="form-error">{error}</div> : null}
          </div>
        )}

        <div className="modal-card__footer">
          <button className="ghost-button" type="button" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button className="primary-button" type="button" onClick={submit} disabled={submitting || loading || filenames.length === 0}>
            {submitting ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
            {submitting
              ? 'Adding…'
              : single
                ? 'Add'
                : `Add ${filenames.length} items`}
          </button>
        </div>
      </div>
    </div>
  );
}
