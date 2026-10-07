import { useEffect, useState } from 'react';
import { api, kes } from '../api';

const STATE_LABEL = { pending: 'Waiting', processing: 'Prompt sent', confirmed: 'Paid', failed: 'Failed' };

export default function Admin() {
  const [resources, setResources] = useState([]);
  const [sales, setSales] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () =>
    Promise.all([api('/admin/resources'), api('/admin/orders')])
      .then(([r, s]) => { setResources(r); setSales(s); })
      .catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function upload(e) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError('');
    try {
      await api('/admin/resources', { method: 'POST', form: new FormData(form) });
      form.reset();
      await load();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  async function update(id, changes) {
    setError('');
    try {
      await api(`/admin/resources/${id}`, { method: 'PATCH', body: changes });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const paid = sales.filter((s) => s.state === 'confirmed');

  return (
    <>
      <h1><span className="hl">Manage</span></h1>
      {error && <p className="error" role="alert">{error}</p>}

      <section className="panel">
        <h2>Add a resource</h2>
        <form className="upload" onSubmit={upload}>
          <label htmlFor="title">Title</label>
          <input id="title" name="title" required minLength={2} />
          <label htmlFor="description">Description</label>
          <textarea id="description" name="description" rows={3} />
          <div className="row">
            <div>
              <label htmlFor="type">Type</label>
              <select id="type" name="type" defaultValue="pdf">
                <option value="pdf">PDF</option>
                <option value="book">Book</option>
                <option value="course">Course</option>
              </select>
            </div>
            <div>
              <label htmlFor="price">Price (KES)</label>
              <input id="price" name="price" type="number" min="1" max="150000" required />
            </div>
          </div>
          <label htmlFor="file">PDF file</label>
          <input id="file" name="file" type="file" accept="application/pdf" required />
          <button className="button" disabled={busy}>{busy ? 'Uploading…' : 'Upload'}</button>
          <p className="hint">New uploads stay hidden until you publish them.</p>
        </form>
      </section>

      <section className="panel">
        <h2>Resources</h2>
        {resources.length === 0 && <p className="empty">Upload your first PDF above.</p>}
        <table>
          <thead><tr><th>Title</th><th>Pages</th><th>Price (KES)</th><th>Visible</th></tr></thead>
          <tbody>
            {resources.map((r) => (
              <tr key={r.id}>
                <td>{r.title}</td>
                <td>{r.page_count ?? 'Not set'}</td>
                <td>
                  <input aria-label={`Price for ${r.title}`} type="number" min="1" defaultValue={r.price}
                    onBlur={(e) => Number(e.target.value) !== r.price && update(r.id, { price: Number(e.target.value) })} />
                </td>
                <td>
                  <button className="link" onClick={() => update(r.id, { published: !r.published })}>
                    {r.published ? 'Published, hide' : 'Hidden, publish'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>Sales</h2>
        <p>{paid.length} paid orders, {kes(paid.reduce((sum, s) => sum + s.total_amount, 0))} received.</p>
        <table>
          <thead><tr><th>Ref</th><th>Buyer</th><th>Items</th><th>Amount</th><th>Status</th><th>M-Pesa receipt</th></tr></thead>
          <tbody>
            {sales.map((s) => (
              <tr key={s.id}>
                <td>{s.account_reference}</td>
                <td>{s.buyer_email}</td>
                <td>{s.items.map((i) => i.title).join(', ')}</td>
                <td>{kes(s.total_amount)}</td>
                <td>{STATE_LABEL[s.state]}{s.failure_reason ? ` (${s.failure_reason.replace(/_/g, ' ')})` : ''}</td>
                <td>{s.mpesa_receipt ?? 'None yet'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
