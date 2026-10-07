import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, kes, localPhone } from '../api';
import { useAuth } from '../auth';

export default function ResourcePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [resource, setResource] = useState(null);
  const [owned, setOwned] = useState(false);
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api(`/resources/${id}`).then(setResource).catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => {
    if (!user) return;
    setPhone(localPhone(user.phone));
    api('/library').then((items) => setOwned(items.some((i) => i.resource.id === Number(id)))).catch(() => {});
  }, [user, id]);

  async function pay(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const order = await api('/orders', { method: 'POST', body: { resource_ids: [Number(id)], phone } });
      navigate(`/orders/${order.id}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (!resource) return error ? <p className="error" role="alert">{error}</p> : null;

  return (
    <article className="resource">
      <Link to="/" className="back">All resources</Link>
      <h1><span className="hl">{resource.title}</span></h1>
      <p className="meta">{resource.page_count ? `${resource.page_count} pages` : resource.type}</p>
      {resource.description && <p className="description">{resource.description}</p>}

      <div className="buy-box">
        <p className="price">{kes(resource.price)}</p>
        {owned ? (
          <Link className="button" to={`/read/${id}`}>Read now</Link>
        ) : user ? (
          <form onSubmit={pay}>
            <label htmlFor="phone">M-Pesa number</label>
            <input id="phone" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required />
            <button className="button" disabled={busy}>{busy ? 'Sending prompt…' : `Pay ${kes(resource.price)}`}</button>
            <p className="hint">You'll get an M-Pesa prompt on this phone. Enter your PIN to finish.</p>
          </form>
        ) : (
          <Link className="button" to={`/login?next=/r/${id}`}>Log in to buy</Link>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    </article>
  );
}
