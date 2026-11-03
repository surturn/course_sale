import { useEffect, useRef, useState } from 'react';

const KEY = 'aggregator-disclaimer-v1';

function seen() {
  try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
}

// Visitors must tick the box before they can use /free and /news. Esc cannot dismiss it
// until then. Acceptance is remembered in this browser; the "Read the disclaimer" link
// reopens it as a plain notice afterwards.
export default function Disclaimer() {
  const ref = useRef(null);
  const [accepted, setAccepted] = useState(seen);
  const [ticked, setTicked] = useState(false);

  useEffect(() => {
    if (!accepted) ref.current?.showModal();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function confirm() {
    if (!accepted && !ticked) return;
    try { localStorage.setItem(KEY, '1'); } catch { /* private mode: it will show again, that is fine */ }
    setAccepted(true);
    ref.current?.close();
  }

  return (
    <>
      <p className="hint">
        Links and headlines come from other websites.{' '}
        <button type="button" className="link" onClick={() => ref.current?.showModal()}>
          Read the disclaimer
        </button>
      </p>
      <dialog
        ref={ref}
        className="disclaimer"
        aria-labelledby="disclaimer-h"
        onCancel={(e) => { if (!accepted) e.preventDefault(); }}
      >
        <h2 id="disclaimer-h">Before you continue</h2>
        <p>Invonics is an aggregator. We collect links, tools, headlines and learning material from other websites to help you find them. We are not the source of that content.</p>
        <p>We are not bound by, and do not promise that we agree with, verify or keep up to date, any information you find through those links. That includes finance, health, security and other advice. Check the original source and, for money or health decisions, speak to a qualified professional.</p>
        <p>Third-party sites have their own terms, prices and privacy practices. We are not responsible for them or for anything you do after leaving this site.</p>
        {!accepted && (
          <label className="agree">
            <input type="checkbox" checked={ticked} onChange={(e) => setTicked(e.target.checked)} />
            <span>I have read this and understand that Invonics is only an aggregator and is not responsible for the information on linked sites.</span>
          </label>
        )}
        <button type="button" className="button" onClick={confirm} disabled={!accepted && !ticked}>
          {accepted ? 'Close' : 'Continue'}
        </button>
      </dialog>
    </>
  );
}
