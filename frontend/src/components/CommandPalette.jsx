import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AudioLines,
  BookOpenText,
  CornerDownLeft,
  Download,
  FileText,
  FolderOpen,
  History,
  Image as ImageIcon,
  LibraryBig,
  Mic2,
  Moon,
  Music2,
  Search,
  SunMedium,
} from 'lucide-react';
import { api } from '../lib/api';

const PAGE_ITEMS = [
  { key: 'page-download', group: 'Pages', label: 'Download', sub: 'Download videos or playlists', icon: Download, path: '/download', keywords: 'video youtube playlist' },
  { key: 'page-transcripts', group: 'Pages', label: 'Transcripts', sub: 'Saved lecture transcripts', icon: BookOpenText, path: '/transcripts', keywords: 'saver transcript' },
  { key: 'page-playlist', group: 'Pages', label: 'Playlist', sub: 'Manage playlists & play continuously', icon: Music2, path: '/playlist', keywords: 'queue' },
  { key: 'page-library', group: 'Pages', label: 'Library', sub: 'All downloaded files', icon: LibraryBig, path: '/library', keywords: 'files media' },
  { key: 'page-history', group: 'Pages', label: 'History', sub: 'Download history & retries', icon: History, path: '/history', keywords: 'jobs' },
  { key: 'page-whisper', group: 'Pages', label: 'Whisper', sub: 'Local AI transcription', icon: Mic2, path: '/whisper', keywords: 'ai transcribe' },
  { key: 'page-audio', group: 'Pages', label: 'Audio Extractor', sub: 'Extract audio from files', icon: AudioLines, path: '/extract-audio', keywords: 'mp3 music' },
  { key: 'page-photos', group: 'Pages', label: 'Photos', sub: 'Saved images', icon: ImageIcon, path: '/photos', keywords: 'instagram images' },
];

function rankMatch(query, text) {
  const q = query.trim().toLowerCase();
  const t = String(text || '').toLowerCase();
  if (!q) return 0;
  if (t.startsWith(q)) return 0;
  if (t.includes(q)) return 1;
  let i = 0;
  for (const ch of t) {
    if (ch === q[i]) i += 1;
    if (i === q.length) return 2;
  }
  return -1;
}

export default function CommandPalette({ open, onClose, navigate, downloads, theme, onToggleTheme }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const [transcripts, setTranscripts] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset on open is intended
    setQuery('');
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset on open is intended
    setSelected(0);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset on open is intended
    setTranscripts([]);
    window.setTimeout(() => inputRef.current?.focus(), 30);
    api
      .get('/transcript-saver')
      .then((res) => {
        const list = Array.isArray(res.data?.transcripts) ? res.data.transcripts : [];
        setTranscripts(list.slice(0, 8));
      })
      .catch(() => setTranscripts([]));
  }, [open]);

  const items = useMemo(() => {
    const out = [];

    for (const page of PAGE_ITEMS) {
      const text = `${page.label} ${page.sub} ${page.keywords}`;
      const rank = rankMatch(query, text);
      if (rank >= 0) {
        out.push({
          ...page,
          rank,
          run: () => {
            onClose();
            navigate(page.path);
          },
        });
      }
    }

    const actionItems = [
      {
        key: 'action-theme', group: 'Actions', label: theme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode',
        sub: 'Toggle appearance', icon: theme === 'dark' ? SunMedium : Moon,
        rank: rankMatch(query, 'theme dark light appearance'), run: () => { onClose(); onToggleTheme(); },
      },
      {
        key: 'action-folder', group: 'Actions', label: 'Open downloads folder', sub: 'Reveal in file explorer',
        icon: FolderOpen, rank: rankMatch(query, 'open downloads folder explore disk'),
        run: () => { api.post('/open-downloads-folder').catch(() => {}); onClose(); },
      },
      {
        key: 'action-download', group: 'Actions', label: 'Start a new download', sub: 'Go to Download page',
        icon: Download, rank: rankMatch(query, 'start new download url link'),
        run: () => { onClose(); navigate('/download'); },
      },
    ];
    for (const item of actionItems) {
      if (item.rank >= 0) out.push(item);
    }

    const recentDownloads = (downloads || [])
      .slice()
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0))
      .slice(0, 6);
    for (const d of recentDownloads) {
      const label = d.title || 'Download';
      const rank = rankMatch(query, `${label} ${d.filename || ''} ${d.url || ''} download`);
      if (rank >= 0) {
        out.push({
          key: `dl-${d.task_id}`, group: 'Recent downloads', label, sub: `${d.status || ''} · ${d.format || ''}`,
          icon: Download, rank, run: () => { onClose(); navigate('/history'); },
        });
      }
    }

    for (const t of transcripts) {
      const rank = rankMatch(query, `${t.title || ''} transcript ${t.folder || ''}`);
      if (rank >= 0) {
        out.push({
          key: `tr-${t.id}`, group: 'Transcripts', label: t.title || 'Transcript', sub: `${t.folder || 'General'} · ${t.line_count || 0} lines`,
          icon: FileText, rank, run: () => { onClose(); navigate(t.folder ? `/transcripts?folder=${encodeURIComponent(t.folder)}` : '/transcripts'); },
        });
      }
    }

    out.sort((a, b) => {
      if (a.rank !== b.rank) return a.rank - b.rank;
      const ga = PAGE_ITEMS.some((p) => p.key === a.key) ? 0 : 1;
      const gb = PAGE_ITEMS.some((p) => p.key === b.key) ? 0 : 1;
      return ga - gb;
    });
    return out;
  }, [query, downloads, transcripts, theme, onToggleTheme, onClose, navigate]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset selection when results change
    setSelected(0);
  }, [query, items.length]);

  if (!open) return null;

  const runSelected = () => {
    const item = items[selected];
    if (item) item.run();
  };

  const groups = [];
  const seen = new Set();
  for (const item of items) {
    if (!seen.has(item.group)) {
      seen.add(item.group);
      groups.push({ name: item.group, items: [] });
    }
    groups[groups.length - 1].items.push(item);
  }

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelected((s) => Math.min(s + 1, items.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      runSelected();
    }
  };

  return (
    <div className="cmd-palette-backdrop" onMouseDown={onClose}>
      <div className="cmd-palette" onMouseDown={(e) => e.stopPropagation()}>
        <div className="cmd-palette__search">
          <Search size={18} className="cmd-palette__search-icon" />
          <input
            ref={inputRef}
            className="cmd-palette__input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search pages, actions, downloads, transcripts…  (Esc to close)"
            spellCheck="false"
            autoComplete="off"
          />
          <span className="cmd-palette__kbd"><kbd>Esc</kbd></span>
        </div>

        <div className="cmd-palette__results">
          {items.length === 0 ? (
            <div className="cmd-palette__empty">No matches for “{query}”</div>
          ) : (
            groups.map((group) => (
              <div className="cmd-palette__group" key={group.name}>
                <div className="cmd-palette__group-label">{group.name}</div>
                {group.items.map((item) => {
                  const flatIndex = items.indexOf(item);
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className={`cmd-palette__item ${flatIndex === selected ? 'cmd-palette__item--active' : ''}`}
                      onMouseEnter={() => setSelected(flatIndex)}
                      onClick={item.run}
                    >
                      <span className="cmd-palette__item-icon"><Icon size={17} /></span>
                      <span className="cmd-palette__item-text">
                        <span className="cmd-palette__item-label">{item.label}</span>
                        {item.sub ? <span className="cmd-palette__item-sub">{item.sub}</span> : null}
                      </span>
                      {flatIndex === selected ? <CornerDownLeft size={14} className="cmd-palette__enter" /> : null}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
