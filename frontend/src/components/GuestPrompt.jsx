import { useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';

// Shown to a guest buyer: their purchases live on a passwordless account until they set a password.
export default function GuestPrompt({ compact = false }) {
  const { user, refresh } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (!user?.is_guest) return null;

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/auth/set-password', { method: 'POST', body: { password } });
      await refresh();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="nudge" onSubmit={save}>
      <h2>Keep your library</h2>
      <p className="hint">
        {compact ? 'You are signed in as a guest. ' : ''}
        Set a password to open your purchases on any device and get help faster. Without one, you can get back in
        later with the M-Pesa code from your payment SMS.
      </p>
      <label htmlFor="guest-password">New password</label>
      <input id="guest-password" type="password" autoComplete="new-password" minLength={8} required
        value={password} onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button" disabled={busy}>{busy ? 'Saving…' : 'Save password'}</button>
    </form>
  );
}
