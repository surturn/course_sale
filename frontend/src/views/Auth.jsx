import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';

function useNext() {
  const [params] = useSearchParams();
  const next = params.get('next');
  return next?.startsWith('/') && !next.startsWith('//') ? next : '/'; // same-site paths only
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      await login(f.get('email'), f.get('password'));
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="auth" onSubmit={submit}>
      <h1><span className="hl">Log in</span></h1>
      <label htmlFor="email">Email</label>
      <input id="email" name="email" type="email" autoComplete="email" required />
      <label htmlFor="password">Password</label>
      <input id="password" name="password" type="password" autoComplete="current-password" required />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
      <p>New here? <Link to={`/register?next=${encodeURIComponent(next)}`}>Create an account</Link></p>
    </form>
  );
}

export function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    try {
      await api('/auth/register', { method: 'POST', body });
      await login(body.email, body.password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="auth" onSubmit={submit}>
      <h1><span className="hl">Create an account</span></h1>
      <label htmlFor="full_name">Full name</label>
      <input id="full_name" name="full_name" autoComplete="name" required minLength={2} />
      <label htmlFor="email">Email</label>
      <input id="email" name="email" type="email" autoComplete="email" required />
      <label htmlFor="phone">M-Pesa number</label>
      <input id="phone" name="phone" inputMode="tel" autoComplete="tel" placeholder="0712345678" required />
      <label htmlFor="password">Password</label>
      <input id="password" name="password" type="password" autoComplete="new-password" required minLength={8} />
      <p className="hint">At least 8 characters. Your name and email appear on every page you buy.</p>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
      <p>Already have one? <Link to={`/login?next=${encodeURIComponent(next)}`}>Log in</Link></p>
    </form>
  );
}
