import { useEffect, useRef, useState } from 'react';

const KEY = 'aggregator-disclaimer-v1';

function seen() {
  try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
}

// Shown once per browser on the pages that list third-party links and headlines.
// A small "Disclaimer" button under the page intro reopens it.
export default function Disclaimer() {
  const ref = useRef(null);
  const [opened, setOpened] = useState(false);

  useEffect(() => {
    if (!seen()) ref.current?.showModal();
  }, []);

  function close() {
    try { localStorage.setItem(KEY, '1'); } catch { /* private mode: it will show again, that is fine */ }
    ref.current?.close();
  }

  return (
    <>
      <p className="hint">
        Links and headlines come from other websites.{' '}
        <button type="button" className="link" onClick={() => { setOpened(true); ref.current?.showModal(); }}>
          Read the disclaimer
        </button>
      </p>
      <dialog ref={ref} className="disclaimer" aria-labelledby="disclaimer-h" onCancel={close} onClose={() => setOpened(false)}>
        <h2 id="disclaimer-h">Before you click</h2>
        <p>Invonics is an aggregator. We collect links, tools, headlines and learning material from other websites to help you find them. We are not the source of that content.</p>
        <p>We are not bound by, and do not promise that we agree with, verify or keep up to date, any information you find through those links. That includes finance, health, security and other advice. Check the original source and, for money or health decisions, speak to a qualified professional.</p>
        <p>Third-party sites have their own terms, prices and privacy practices. We are not responsible for them or for anything you do after leaving this site.</p>
        <button type="button" className="button" onClick={close} autoFocus>{opened ? 'Close' : 'Got it, continue'}</button>
      </dialog>
    </>
  );
}
