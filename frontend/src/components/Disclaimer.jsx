import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

function DisclaimerText() {
  return (
    <>
      <p>Invonics is an aggregator. We collect links, tools, headlines and learning material from other websites to help you find them. We are not the source of that content.</p>
      <p>We are not bound by, and do not promise that we agree with, verify or keep up to date, any information you find through those links. That includes finance, health, security and other advice. Check the original source and, for money or health decisions, speak to a qualified professional.</p>
      <p>Third-party sites have their own terms, prices and privacy practices. We are not responsible for them or for anything you do after leaving this site.</p>
    </>
  );
}

// Wraps a page of third-party content. The server only sends that content to browsers that
// have accepted, so the children are not rendered, and their data is not requested, until then.
// Acceptance is a long-lived cookie set by the server; if the check fails we stay closed.
export function DisclaimerGate({ children }) {
  const [state, setState] = useState('loading'); // loading | needed | ok | error
  const [ticked, setTicked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const ref = useRef(null);

  function check() {
    setState('loading');
    api('/disclaimer').then((r) => setState(r.accepted ? 'ok' : 'needed')).catch(() => setState('error'));
  }
  useEffect(check, []);
  useEffect(() => {
    if (state === 'needed' && ref.current && !ref.current.open) ref.current.showModal();
  }, [state]);

  async function accept() {
    if (!ticked || busy) return;
    setBusy(true);
    setProblem('');
    try {
      await api('/disclaimer/accept', { method: 'POST', body: { agreed: true } });
      ref.current?.close();
      setState('ok');
    } catch (e) {
      setProblem(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (state === 'ok') return children;
  if (state === 'error') {
    return (
      <p className="empty">
        We couldn't check the disclaimer. <button type="button" className="link" onClick={check}>Try again</button>
      </p>
    );
  }
  if (state === 'loading') return null;
  return (
    <>
      <p className="empty">Please read and accept the disclaimer to continue.</p>
      <dialog ref={ref} className="disclaimer" aria-labelledby="disclaimer-h" onCancel={(e) => e.preventDefault()}>
        <h2 id="disclaimer-h">Before you continue</h2>
        <DisclaimerText />
        <label className="agree">
          <input type="checkbox" checked={ticked} onChange={(e) => setTicked(e.target.checked)} />
          <span>I have read this and understand that Invonics is only an aggregator and is not responsible for the information on linked sites.</span>
        </label>
        {problem && <p className="error" role="alert">{problem}</p>}
        <button type="button" className="button" onClick={accept} disabled={!ticked || busy}>Continue</button>
      </dialog>
    </>
  );
}

// Small line under a page intro that reopens the notice for reading.
export function DisclaimerNote() {
  const ref = useRef(null);
  return (
    <>
      <p className="hint">
        Links and headlines come from other websites.{' '}
        <button type="button" className="link" onClick={() => ref.current?.showModal()}>Read the disclaimer</button>
      </p>
      <dialog ref={ref} className="disclaimer" aria-labelledby="disclaimer-note-h">
        <h2 id="disclaimer-note-h">Disclaimer</h2>
        <DisclaimerText />
        <button type="button" className="button" onClick={() => ref.current?.close()} autoFocus>Close</button>
      </dialog>
    </>
  );
}
