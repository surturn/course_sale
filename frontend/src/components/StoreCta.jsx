import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, kes } from '../api';

// Shown under the free pages: the paid catalog, so free visitors can see what else is here.
export default function StoreCta() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    api('/resources').then((r) => setItems(r.slice(0, 3))).catch(() => {});
  }, []);

  return (
    <section className="store-cta" aria-labelledby="store-cta-h">
      <h2 id="store-cta-h"><span className="hl">Want the full notes and interview prep?</span></h2>
      <p>The free links get you started. The paid notes, books and interview PDFs are written to save you the digging. Pay with M-Pesa and read in your browser.</p>
      {items.length > 0 && (
        <ul className="reading-list">
          {items.map((r) => (
            <li key={r.id}>
              <Link to={`/r/${r.id}`}>
                <span className="title">{r.title}</span>
                <span className="meta">{r.page_count ? `${r.page_count} pages` : 'Read online'}</span>
                <span className="price">{kes(r.price)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link to="/" className="button">Browse all resources</Link>
    </section>
  );
}
