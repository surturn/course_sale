import { useMemo, useState } from 'react';
import StoreCta from '../components/StoreCta';
import items from '../data/free-resources.json';

const KIND_LABEL = { repo: 'GitHub', site: 'Website', tool: 'Tool', course: 'Course' };
const NICHES = ['All', ...new Set(items.map((i) => i.niche))];

export default function FreeLibrary() {
  const [niche, setNiche] = useState('All');
  const [q, setQ] = useState('');

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase();
    return items.filter(
      (i) =>
        (niche === 'All' || i.niche === niche) &&
        (!term || `${i.title} ${i.desc} ${i.niche}`.toLowerCase().includes(term)),
    );
  }, [niche, q]);

  return (
    <>
      <section className="intro">
        <h1><span className="hl">Free tools and know-how for work, money and everyday life.</span></h1>
        <p>Courses, apps, guides and tools for coding, money, habits and learning, for everyone. You don't need to be technical. Links open on their own sites, and some have paid extras, so check each one.</p>
      </section>

      <div className="free-controls">
        <label className="visually-hidden" htmlFor="free-search">Search free resources</label>
        <input
          id="free-search"
          type="search"
          placeholder="Search, e.g. budget, python, sleep, resume"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="chips" role="group" aria-label="Filter by niche">
          {NICHES.map((n) => (
            <button
              key={n}
              type="button"
              className={n === niche ? 'chip on' : 'chip'}
              aria-pressed={n === niche}
              onClick={() => setNiche(n)}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {shown.length === 0 && <p className="empty">Nothing matches that. Try another word or niche.</p>}
      {shown.length > 0 && (
        <ul className="reading-list free-list">
          {shown.map((r) => (
            <li key={r.url}>
              <a href={r.url} target="_blank" rel="noopener noreferrer">
                <span className="title">{r.title}</span>
                <span className="meta">{r.desc}</span>
                <span className="price">{KIND_LABEL[r.kind]}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <StoreCta />
    </>
  );
}
