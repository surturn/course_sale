import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Cover from '../components/Cover';
import GuestPrompt from '../components/GuestPrompt';
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
      <GuestPrompt compact />
      {error && <p className="error" role="alert">{error}</p>}
      {!items && !error && <ListSkeleton />}
      {items?.length === 0 && <p className="empty">You haven't bought anything yet. <Link to="/">Browse resources</Link></p>}
      {items?.length > 0 && (
        <ul className="reading-list">
          {items.map(({ resource, purchased_at }, i) => (
            <li key={resource.id} style={{ '--i': i }}>
              <Link to={`/read/${resource.id}`} className="has-cover">
                <Cover title={resource.title} type={resource.type} src={resource.cover_url} className="thumb" />
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
