import { useCallback, useEffect, useRef, useState } from 'react';

const reduce = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// One horizontally scrollable row of filter chips. Touch: swipe. Mouse: arrow buttons.
// The selected chip is scrolled into view, so a pick never hides behind the edge.
export default function ChipRow({ label, options, value, onChange }) {
  const scroller = useRef(null);
  const [edge, setEdge] = useState({ start: true, end: true });

  const measure = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    setEdge({ start: el.scrollLeft <= 1, end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 1 });
  }, []);

  useEffect(() => {
    measure();
    const el = scroller.current;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [measure, options.length]);

  function nudge(dir) {
    const el = scroller.current;
    el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: reduce() ? 'auto' : 'smooth' });
  }

  return (
    <div className="chip-row">
      <button type="button" className="chip-nav" aria-label="Scroll topics left" onClick={() => nudge(-1)} disabled={edge.start} tabIndex={-1}>
        <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M7.5 2.5L4 6l3.5 3.5" /></svg>
      </button>
      <div className="chips" role="group" aria-label={label} ref={scroller} onScroll={measure}>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            className={o.value === value ? 'chip on' : 'chip'}
            aria-pressed={o.value === value}
            onClick={(e) => {
              onChange(o.value);
              e.currentTarget.scrollIntoView({ inline: 'center', block: 'nearest', behavior: reduce() ? 'auto' : 'smooth' });
            }}
          >
            {o.label}{o.count != null && <span className="count"> {o.count}</span>}
          </button>
        ))}
      </div>
      <button type="button" className="chip-nav" aria-label="Scroll topics right" onClick={() => nudge(1)} disabled={edge.end} tabIndex={-1}>
        <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4.5 2.5L8 6l-3.5 3.5" /></svg>
      </button>
    </div>
  );
}
