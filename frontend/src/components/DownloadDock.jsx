import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Download, X } from 'lucide-react';

const ACTIVE_STATUSES = new Set(['pending', 'queued', 'starting', 'downloading', 'processing']);

const STATUS_LABEL = {
  pending: 'Queued',
  queued: 'Queued',
  starting: 'Starting',
  downloading: 'Downloading',
  processing: 'Processing',
};

function percentOf(item) {
  if (Number.isFinite(item?.progress)) return Math.min(Math.max(item.progress, 0), 100);
  const parsed = Number.parseFloat(item?.percent || '');
  return Number.isNaN(parsed) ? 0 : Math.min(Math.max(parsed, 0), 100);
}

export default function DownloadDock({ downloads, onCancel }) {
  const [expanded, setExpanded] = useState(false);
  const active = useMemo(
    () => (downloads || []).filter((d) => ACTIVE_STATUSES.has(d.status)),
    [downloads],
  );

  // Collapse the panel automatically when nothing is active anymore.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- collapse when queue empties
    if (active.length === 0) setExpanded(false);
  }, [active.length]);

  if (active.length === 0) return null;

  return (
    <div className={`dock ${expanded ? 'dock--expanded' : ''}`}>
      <button
        className="dock__toggle"
        type="button"
        onClick={() => setExpanded((v) => !v)}
        title={expanded ? 'Collapse downloads' : 'Show active downloads'}
      >
        <span className="dock__toggle-icon"><Download size={16} /></span>
        <span className="dock__toggle-text">
          {active.length} download{active.length === 1 ? '' : 's'} active
        </span>
        <span className="dock__toggle-caret">{expanded ? '▾' : '▴'}</span>
      </button>

      {expanded ? (
        <div className="dock__panel">
          <div className="dock__panel-head">
            <strong>Active downloads</strong>
            <button className="dock__close" type="button" onClick={() => setExpanded(false)} title="Close">
              <X size={15} />
            </button>
          </div>
          <div className="dock__list">
            {active.map((item) => (
              <div className="dock__row" key={item.task_id}>
                <div className="dock__row-title" title={item.title || item.filename || 'Download'}>
                  {item.title || item.filename || 'Download'}
                </div>
                <div className="dock__row-meta">
                  <span>{STATUS_LABEL[item.status] || item.status}</span>
                  <span>{percentOf(item).toFixed(0)}%</span>
                </div>
                <div className="dock__bar">
                  <div className="dock__bar-fill" style={{ width: `${percentOf(item)}%` }} />
                </div>
                <button
                  className="dock__cancel"
                  type="button"
                  title="Cancel"
                  onClick={() => onCancel?.(item.task_id)}
                >
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
          <Link className="dock__history" to="/history" onClick={() => setExpanded(false)}>
            Open History <ArrowRight size={14} />
          </Link>
        </div>
      ) : null}
    </div>
  );
}
