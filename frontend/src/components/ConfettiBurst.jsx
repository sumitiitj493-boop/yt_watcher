import { useEffect, useRef, useState } from 'react';

const COLORS = ['#8b5cf6', '#22d3ee', '#34d399', '#f472b6', '#fbbf24', '#6366f1'];

/**
 * A small celebratory confetti burst, fired whenever `burstId` changes.
 * Renders particles that fly up/out from the bottom of the screen and fade.
 */
export default function ConfettiBurst({ burstId = 0 }) {
  const [particles, setParticles] = useState([]);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!burstId) return undefined;
    const pieces = Array.from({ length: 26 }, (_, i) => {
      const angle = Math.PI * (0.12 + 0.76 * (i / 25)) + (Math.random() - 0.5) * 0.2;
      const distance = 120 + Math.random() * 320;
      const dx = Math.cos(angle) * distance;
      const dy = -(Math.sin(angle) * distance) - 60;
      return {
        id: `${burstId}-${i}-${Math.random().toString(36).slice(2)}`,
        left: 18 + Math.random() * 64, // near the dock (bottom-right area)
        dx,
        dy,
        rot: (Math.random() - 0.5) * 900,
        dur: 0.9 + Math.random() * 0.6,
        color: COLORS[i % COLORS.length],
      };
    });
    setParticles(pieces);
    timerRef.current = window.setTimeout(() => setParticles([]), 1800);
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [burstId]);

  if (!particles.length) return null;

  return (
    <div className="confetti-burst" aria-hidden="true">
      {particles.map((p) => (
        <span
          key={p.id}
          className="confetti-piece"
          style={{
            left: `${p.left}%`,
            background: p.color,
            '--dx': `${p.dx}px`,
            '--dy': `${p.dy}px`,
            '--rot': `${p.rot}deg`,
            '--dur': `${p.dur}s`,
          }}
        />
      ))}
    </div>
  );
}
