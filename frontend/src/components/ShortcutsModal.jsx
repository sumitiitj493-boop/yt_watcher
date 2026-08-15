import { useEffect } from 'react';
import { Keyboard, X } from 'lucide-react';

const SHORTCUTS = [
  { keys: ['Ctrl', 'K'], label: 'Open command palette' },
  { keys: ['?'], label: 'Show this shortcuts help' },
  { keys: ['D'], label: 'Go to Download' },
  { keys: ['T'], label: 'Go to Transcripts' },
  { keys: ['P'], label: 'Go to Playlist' },
  { keys: ['L'], label: 'Go to Library' },
  { keys: ['H'], label: 'Go to History' },
  { keys: ['W'], label: 'Go to Whisper' },
  { keys: ['A'], label: 'Go to Audio Extractor' },
  { keys: ['Esc'], label: 'Close popups / overlays' },
];

export default function ShortcutsModal({ open, onClose }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="shortcuts-backdrop" onMouseDown={onClose}>
      <div className="shortcuts-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="shortcuts-modal__head">
          <span className="shortcuts-modal__icon"><Keyboard size={18} /></span>
          <h2 className="panel__title panel__title--tight">Keyboard shortcuts</h2>
          <button className="shortcuts-modal__close" type="button" onClick={onClose} title="Close">
            <X size={16} />
          </button>
        </div>
        <div className="shortcuts-modal__list">
          {SHORTCUTS.map((shortcut) => (
            <div className="shortcuts-modal__row" key={shortcut.label}>
              <span className="shortcuts-modal__keys">
                {shortcut.keys.map((key) => (
                  <kbd key={key}>{key}</kbd>
                ))}
              </span>
              <span className="shortcuts-modal__label">{shortcut.label}</span>
            </div>
          ))}
        </div>
        <p className="shortcuts-modal__note">Shortcuts work anywhere except while typing in a text field.</p>
      </div>
    </div>
  );
}
