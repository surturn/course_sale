import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, kes } from '../api';

const FAILURE_COPY = {
  user_cancelled: 'The M-Pesa prompt was cancelled.',
  insufficient_funds: "There wasn't enough in the M-Pesa account.",
  timeout: 'The M-Pesa prompt expired before a PIN was entered.',
  wrong_pin: 'The M-Pesa PIN was wrong.',
  amount_mismatch: "The amount paid didn't match the order. Contact support with your M-Pesa message.",
  stk_push_error: "We couldn't reach M-Pesa.",
};
const POLL_MS = 3000;
const GIVE_UP_MS = 3 * 60 * 1000;

export default function OrderStatus() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    let timer;
    const started = Date.now();
    async function poll() {
      try {
        const o = await api(`/orders/${id}`);
        setOrder(o);
        if (o.state === 'confirmed' || o.state === 'failed') return;
      } catch (e) {
        setError(e.message);
      }
      if (Date.now() - started > GIVE_UP_MS) return setGaveUp(true);
      timer = setTimeout(poll, POLL_MS);
    }
    poll();
    return () => clearTimeout(timer);
  }, [id]);

  if (!order) return error ? <p className="error" role="alert">{error}</p> : null;
  const first = order.items[0];

  return (
    <section className="order" aria-live="polite">
      {order.state === 'confirmed' && (
        <>
          <h1><span className="hl">Payment received</span></h1>
          <p>{kes(order.total_amount)} paid for {order.items.map((i) => i.title).join(', ')}.</p>
          <Link className="button" to={`/read/${first.resource_id}`}>Start reading</Link>
        </>
      )}
      {order.state === 'failed' && (
        <>
          <h1><span className="hl">Payment didn't go through</span></h1>
          <p>
            {FAILURE_COPY[order.failure_reason] ?? 'M-Pesa declined the payment.'}
            {order.failure_reason !== 'amount_mismatch' && " You haven't been charged."}
          </p>
          <Link className="button" to={`/r/${first.resource_id}`}>Try again</Link>
        </>
      )}
      {(order.state === 'pending' || order.state === 'processing') && (
        <>
          <h1><span className="hl">Check your phone</span></h1>
          <p>Enter your M-Pesa PIN to pay {kes(order.total_amount)}. This page updates by itself.</p>
          <div className="waiting" aria-hidden="true" />
          {gaveUp && (
            <p className="hint">
              Still waiting on M-Pesa. If you've paid, your purchase will appear in <Link to="/library">your library</Link> shortly.
              Reference {order.account_reference}.
            </p>
          )}
        </>
      )}
    </section>
  );
}
