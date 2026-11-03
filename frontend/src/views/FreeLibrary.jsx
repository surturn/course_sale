import { useEffect, useMemo, useState } from 'react';
import { DisclaimerNote } from '../components/Disclaimer';
import ListSkeleton from '../components/ListSkeleton';
import StoreCta from '../components/StoreCta';
import { api } from '../api';

const KIND_LABEL = { repo: 'GitHub', site: 'Website', tool: 'Tool', course: 'Course' };

function Row({ r, i }) {
  return (
    <li style={{ '--i': i }}>
      <a href={r.url} target="_blank" rel="noopener noreferrer">
        <span className="title">{r.title}<svg className="ext" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4" /></svg><span className="visually-hidden"> (opens in a new tab)</span></span>
        <span className="meta">{r.desc}</span>
        <span className="badge">{KIND_LABEL[r.kind]}</span>
      </a>
    </li>
  );
}

export default function FreeLibrary() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [niche, setNiche] = useState('All');
  const [q, setQ] = useState('');

  useEffect(() => {
    api('/free-resources').then(setItems).catch((e) => setError(e.message));
  }, []);

  const niches = useMemo(() => {
    const counts = new Map();
    (items ?? []).forEach((i) => counts.set(i.niche, (counts.get(i.niche) ?? 0) + 1));
    return counts;
  }, [items]);

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (items ?? []).filter(
      (i) => (niche === 'All' || i.niche === niche) && (!term || `${i.title} ${i.desc} ${i.niche}`.toLowerCase().includes(term)),
    );
  }, [items, niche, q]);

  // With no filter or search, show one headed section per niche so people can scan by topic.
  const grouped = niche === 'All' && !q.trim();
  const sections = grouped ? [...niches.keys()].map((n) => [n, shown.filter((i) => i.niche === n)]) : [[null, shown]];

  return (
    <>
      <section className="intro">
        <h1><span className="hl">Free tools and learning for everyone.</span></h1>
        <p>Courses, apps, guides and tools for coding, money, habits and learning, for everyone. You don't need to be technical. Links open on their own sites, and some have paid extras, so check each one.</p>
      </section>
      <DisclaimerNote />

      <div className="free-controls">
        <label className="visually-hidden" htmlFor="free-search">Search free resources</label>
        <input id="free-search" type="search" placeholder="Search, e.g. budget, python, sleep, resume" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="chips" role="group" aria-label="Filter by topic">
          {['All', ...niches.keys()].map((n) => (
            <button key={n} type="button" className={n === niche ? 'chip on' : 'chip'} aria-pressed={n === niche} onClick={() => setNiche(n)}>
              {n}{n !== 'All' && <span className="count"> {niches.get(n)}</span>}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {!items && !error && <ListSkeleton rows={6} />}
      {items && shown.length === 0 && <p className="empty">Nothing matches that. Try another word or topic.</p>}
      {sections.map(([name, rows]) =>
        rows.length === 0 ? null : (
          <section key={name ?? 'results'} className="free-section">
            {name && <h2 className="section-head">{name} <span className="count">{rows.length}</span></h2>}
            <ul className="reading-list free-list">
              {rows.map((r, i) => <Row key={r.url} r={r} i={i} />)}
            </ul>
          </section>
        ),
      )}
      <StoreCta />
    </>
  );
}
