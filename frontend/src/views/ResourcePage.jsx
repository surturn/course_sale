import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, kes, localPhone } from '../api';
import Cover from '../components/Cover';
import { useAuth } from '../auth';

export default function ResourcePage() {
  const { id } = useParams();
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [resource, setResource] = useState(null);
  const [owned, setOwned] = useState(false);
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [guest, setGuest] = useState({ full_name: '', email: '' });
  const [accountExists, setAccountExists] = useState(false);

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

  async function payAsGuest(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setAccountExists(false);
    try {
      const order = await api('/orders/guest', { method: 'POST', body: { resource_ids: [Number(id)], phone, ...guest } });
      await refresh();
      navigate(`/orders/${order.id}`);
    } catch (err) {
      setError(err.message);
      setAccountExists(err.status === 409 && /account/i.test(err.message));
      setBusy(false);
    }
  }

  if (!resource) return error ? <p className="error" role="alert">{error}</p> : null;

  return (
    <article className="resource">
      <Link to="/" className="back">All resources</Link>
      <header className="resource-head">
        <Cover title={resource.title} type={resource.type} src={resource.cover_url} className="hero-cover" />
        <div>
          <h1><span className="hl">{resource.title}</span></h1>
          <p className="meta">{resource.page_count ? `${resource.page_count} pages` : resource.type}</p>
        </div>
      </header>
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
          <>
            <div className="nudge">
              <h2>Faster with an account</h2>
              <p className="hint">Your purchases stay in one library, open on any device, and we can help you quickly if something goes wrong.</p>
              <div className="actions">
                <Link className="button" to={`/login?next=/r/${id}`}>Log in</Link>
                <Link className="button secondary" to={`/register?next=/r/${id}`}>Create account</Link>
              </div>
            </div>
            <form onSubmit={payAsGuest}>
              <h2 className="or">Or buy as a guest</h2>
              <label htmlFor="g-name">Full name</label>
              <input id="g-name" autoComplete="name" required minLength={2} value={guest.full_name}
                onChange={(e) => setGuest({ ...guest, full_name: e.target.value })} />
              <label htmlFor="g-email">Email</label>
              <input id="g-email" type="email" autoComplete="email" required value={guest.email}
                onChange={(e) => setGuest({ ...guest, email: e.target.value })} />
              <label htmlFor="phone">M-Pesa number</label>
              <input id="phone" inputMode="tel" autoComplete="tel" placeholder="0712345678" required value={phone}
                onChange={(e) => setPhone(e.target.value)} />
              <button className="button" disabled={busy}>{busy ? 'Sending prompt…' : `Pay ${kes(resource.price)}`}</button>
              <p className="hint">Your name and email appear on the pages you read. You will set a password after paying.</p>
            </form>
            {accountExists && (
              <p className="hint">
                Bought as a guest before? <Link to="/recover">Get your library back</Link>.
              </p>
            )}
          </>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    </article>
  );
}
