import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ListSkeleton from '../components/ListSkeleton';
import { api } from '../api';

export default function Library() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/library').then(setItems).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <h1><span className="hl">My library</span></h1>
      {error && <p className="error" role="alert">{error}</p>}
      {!items && !error && <ListSkeleton />}
      {items?.length === 0 && <p className="empty">You haven't bought anything yet. <Link to="/">Browse resources</Link></p>}
      {items?.length > 0 && (
        <ul className="reading-list">
          {items.map(({ resource, purchased_at }, i) => (
            <li key={resource.id} style={{ '--i': i }}>
              <Link to={`/read/${resource.id}`}>
                <span className="title">{resource.title}</span>
                <span className="meta">Bought {new Date(purchased_at).toLocaleDateString('en-KE')}</span>
                <span className="price">Read</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
