// Protected reader. Honest posture: blocking right-click, save and print only deters casual
// copying; screenshots and photos can't be stopped in a browser. The real protection is the
// server-side watermark: every page carries the buyer's name/email and a hidden fingerprint.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';
import { deviceId } from '../device';

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();

export default function Reader() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [width, setWidth] = useState(800);
  const frame = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch(`/api/v1/resources/${id}/file`, {
        credentials: 'same-origin',
        headers: { 'X-Device-Id': await deviceId() },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Couldn't open this resource (${res.status}).`);
      }
      const bytes = new Uint8Array(await res.arrayBuffer());
      if (!cancelled) setData(bytes);
    })().catch((e) => !cancelled && setError(e.message === 'Failed to fetch' ? "Can't reach the server. Check your connection." : e.message));
    return () => { cancelled = true; };
  }, [id]);

  // Size pages to the reading column.
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.min(entry.contentRect.width, 900)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [data]);

  // Deterrents: no save/print/copy shortcuts, page turns on arrow keys.
  useEffect(() => {
    function onKey(e) {
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && ['s', 'p', 'c', 'a'].includes(k)) e.preventDefault();
      if (k === 'arrowright') setPage((p) => Math.min(p + 1, pages || p));
      if (k === 'arrowleft') setPage((p) => Math.max(p - 1, 1));
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pages]);

  const file = useMemo(() => (data ? { data: data.slice() } : null), [data]);

  if (error) {
    return (
      <section className="reader-message">
        <p className="error" role="alert">{error}</p>
        <Link to="/library">Back to my library</Link>
      </section>
    );
  }

  return (
    <section className="reader" ref={frame} onContextMenu={(e) => e.preventDefault()} onDragStart={(e) => e.preventDefault()}>
      {!file && <p className="hint">Preparing your copy… the first open takes a few seconds.</p>}
      {file && (
        <Document file={file} onLoadSuccess={({ numPages }) => setPages(numPages)} loading={<p className="hint">Loading…</p>}
          error={<p className="error">This file couldn't be displayed.</p>}>
          <Page pageNumber={page} width={width} renderTextLayer={false} renderAnnotationLayer={false} />
        </Document>
      )}
      {pages > 0 && (
        <nav className="pager" aria-label="Pages">
          <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1}>Previous</button>
          <span>Page {page} of {pages}</span>
          <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages}>Next</button>
        </nav>
      )}
    </section>
  );
}
