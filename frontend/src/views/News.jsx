import { useEffect, useState } from 'react';
import ChipRow from '../components/ChipRow';
import { DisclaimerNote } from '../components/Disclaimer';
import ListSkeleton from '../components/ListSkeleton';
import StoreCta from '../components/StoreCta';
import { api } from '../api';

const NICHES = [
  ['', 'All'],
  ['hardware', 'Hardware'],
  ['software', 'Software & dev'],
  ['ai', 'AI'],
  ['security', 'Security'],
  ['africa', 'Africa tech'],
];

function ago(iso) {
  const h = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 36e5));
  if (h < 1) return 'just now';
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export default function News() {
  const [niche, setNiche] = useState('');
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setItems(null);
    setError('');
    api(`/news${niche ? `?niche=${niche}` : ''}`)
      .then((r) => live && setItems(r.items))
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [niche, attempt]);

  return (
    <>
      <section className="intro">
        <h1><span className="hl">What's happening in tech.</span></h1>
        <p>Headlines from trusted sites on hardware, software, AI, security and African tech. Updated through the day. Each link opens the original story.</p>
      </section>

      <DisclaimerNote />

      <div className="free-controls">
        <ChipRow label="Filter by topic" value={niche} onChange={setNiche} options={NICHES.map(([value, label]) => ({ value, label }))} />
      </div>

      {error && (
        <div role="alert">
          <p className="error">Couldn't load the headlines. {error}</p>
          <button className="button" onClick={() => setAttempt((n) => n + 1)}>Try again</button>
        </div>
      )}
      {!items && !error && <ListSkeleton rows={6} />}
      {items?.length === 0 && <p className="empty">No headlines right now. Check back in a few minutes.</p>}
      {items?.length > 0 && (
        <ul className="reading-list free-list">
          {items.map((n, i) => (
            <li key={n.link} style={{ '--i': i }}>
              <a href={n.link} target="_blank" rel="noopener noreferrer">
                <span className="title">{n.title}</span>
                <span className="meta">{n.source} · {ago(n.published)}{n.summary ? ` · ${n.summary}` : ''}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <StoreCta />
    </>
  );
}
