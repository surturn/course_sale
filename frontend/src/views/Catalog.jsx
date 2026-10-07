import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ListSkeleton from '../components/ListSkeleton';
import { api, kes } from '../api';

const TYPE_LABEL = { pdf: 'PDF', book: 'Book', course: 'Course' };

export default function Catalog() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/resources').then(setItems).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <section className="intro">
        <h1><span className="hl">Notes, books and interview prep from someone who's been there.</span></h1>
        <p>Pay with M-Pesa and read in your browser. Every copy carries the buyer's name, so please don't share yours.</p>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {!items && !error && <ListSkeleton />}
      {items?.length === 0 && <p className="empty">Nothing's on sale yet. Check back soon.</p>}
      {items?.length > 0 && (
        <ul className="reading-list">
          {items.map((r, i) => (
            <li key={r.id} style={{ '--i': i }}>
              <Link to={`/r/${r.id}`}>
                <span className="title">{r.title}</span>
                <span className="meta">{TYPE_LABEL[r.type]}{r.page_count ? `, ${r.page_count} pages` : ''}</span>
                <span className="price">{kes(r.price)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
