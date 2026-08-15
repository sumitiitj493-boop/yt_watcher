import { useEffect, useMemo, useRef, useState } from 'react';
import { Volume2, VolumeX } from 'lucide-react';

// Short, motivating quotes — one is picked per page load (random).
const QUOTES = [
  'Small steps every day lead to big results.',
  'Discipline beats motivation when motivation fades.',
  'Study now, shine later.',
  'Consistency is the quiet superpower.',
  'Every expert was once a beginner.',
  'One video at a time — you are building your future.',
  'Focus on progress, not perfection.',
  'Your future self will thank you for today.',
  'Learn a little, improve a lot.',
  'The best time to start was yesterday. The next best is now.',
];

// Simple, reliable spoken "Welcome" using the browser's built-in speech
// synthesis — no audio files, nothing to download, nothing to break.
let playedThisLoad = false;

function speakWelcome() {
  try {
    if (!('speechSynthesis' in window)) return false;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance('Welcome!');
    utter.lang = 'en-US';
    utter.rate = 0.95;
    // Prefer an English voice if one is available.
    const voices = window.speechSynthesis.getVoices();
    const en = voices.find((v) => String(v.lang || '').toLowerCase().startsWith('en'));
    if (en) utter.voice = en;
    window.speechSynthesis.speak(utter);
    return true;
  } catch {
    return false;
  }
}

export default function WelcomeQuote({ voiceOn = true }) {
  const quote = useMemo(() => QUOTES[Math.floor(Math.random() * QUOTES.length)], []);
  const [needsClick, setNeedsClick] = useState(false);
  const playedRef = useRef(false);

  useEffect(() => {
    if (!voiceOn) return undefined;
    if (playedThisLoad || playedRef.current) return undefined;
    playedThisLoad = true;
    playedRef.current = true;

    const ok = speakWelcome();
    if (ok) return undefined;

    // Blocked by the browser (autoplay rules) — wait for the first click.
    setNeedsClick(true);
    const onFirstInteraction = () => {
      cleanup();
      speakWelcome();
      setNeedsClick(false);
    };
    const cleanup = () => {
      window.removeEventListener('pointerdown', onFirstInteraction);
      window.removeEventListener('keydown', onFirstInteraction);
      window.removeEventListener('click', onFirstInteraction);
      window.removeEventListener('touchstart', onFirstInteraction);
    };
    window.addEventListener('pointerdown', onFirstInteraction);
    window.addEventListener('keydown', onFirstInteraction);
    window.addEventListener('click', onFirstInteraction);
    window.addEventListener('touchstart', onFirstInteraction);
    const hideTimer = window.setTimeout(() => setNeedsClick(false), 8000);
    return () => {
      cleanup();
      window.clearTimeout(hideTimer);
    };
  }, [voiceOn]);

  return (
    <div className="welcome-quote">
      <h1 className="welcome-quote__title">
        Welcome 👋
        <button
          className="welcome-quote__speak"
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            if (voiceOn) speakWelcome();
          }}
          title={voiceOn ? 'Say "Welcome"' : 'Voice is off'}
          aria-label="Speak welcome"
        >
          {voiceOn ? <Volume2 size={16} /> : <VolumeX size={16} />}
        </button>
      </h1>
      <p className="welcome-quote__text">“{quote}”</p>
      {needsClick ? (
        <p className="welcome-quote__hint">🔊 Click anywhere to hear “Welcome”</p>
      ) : null}
    </div>
  );
}
