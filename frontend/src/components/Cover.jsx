// Generated cover art: crisp geometry in the brand's navy and yellow, one distinct cover per title.
// The same title always gets the same cover. Decorative, so hidden from assistive tech.
const INK = '#1d2b4f';
const MARK = '#ffe14d';
const MIST = '#c9d3ea';
const PAPER = '#f6f7f9';

// Ground and two shape colours by resource type, so PDFs, books and courses read apart at a glance.
const PALETTE = {
  pdf: { ground: INK, a: MARK, b: MIST },
  book: { ground: MARK, a: INK, b: PAPER },
  course: { ground: '#e6ebf6', a: INK, b: MARK },
};

function hash(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

export default function Cover({ title = '', type = 'pdf', className = '' }) {
  const base = PALETTE[type] ?? PALETTE.pdf;
  const h = hash(`${type}:${title}`);
  const swap = (h >>> 22) & 1; // swap the two shape colours
  const { ground } = base;
  const a = swap ? base.b : base.a;
  const b = swap ? base.a : base.b;
  const flipX = (h >>> 24) & 1;
  const flipY = (h >>> 25) & 1;
  const pick = (shift, min, max) => min + ((h >>> shift) % (max - min + 1));
  let art;
  switch (h % 4) {
    case 0: { // a rising sun over bands
      const r = pick(3, 26, 38), cx = pick(7, 40, 80), cy = pick(11, 52, 70);
      art = (<>
        <circle cx={cx} cy={cy} r={r} fill={a} />
        <rect x="0" y="100" width="120" height="14" fill={b} />
        <rect x="0" y="122" width="120" height="8" fill={a} />
        <rect x="0" y="138" width="120" height="22" fill={b} />
      </>);
      break;
    }
    case 1: { // pages: stacked bars that shorten, one accent block
      const w1 = pick(3, 70, 96), w2 = pick(7, 48, 70), w3 = pick(11, 26, 48);
      art = (<>
        <rect x="16" y="26" width={w1} height="12" rx="6" fill={a} />
        <rect x="16" y="46" width={w2} height="12" rx="6" fill={b} />
        <rect x="16" y="66" width={w3} height="12" rx="6" fill={a} />
        <rect x="16" y={pick(15, 100, 114)} width="40" height="40" fill={b} />
        <rect x="64" y={pick(19, 110, 122)} width="40" height="30" fill={a} />
      </>);
      break;
    }
    case 2: { // quadrants with quarter circles
      const k = pick(3, 0, 1), rr = pick(5, 22, 30);
      art = (<>
        <path d="M60 0H0V60A60 60 0 0 0 60 0Z" fill={a} transform={k ? 'translate(0 20)' : ''} />
        <rect x="60" y="20" width="60" height="60" fill={b} />
        <rect x="0" y="80" width="60" height="60" fill={b} transform={k ? '' : 'translate(0 20)'} />
        <circle cx={pick(9, 84, 94)} cy={pick(13, 106, 114)} r={rr} fill={a} />
      </>);
      break;
    }
    default: { // a diagonal split with a circle on the seam
      const cut = pick(3, 70, 100);
      art = (<>
        <polygon points={`0,${cut} 120,${cut - 50} 120,160 0,160`} fill={b} />
        <polygon points={`0,${cut + 26} 120,${cut - 24} 120,160 0,160`} fill={a} />
        <circle cx={pick(7, 34, 86)} cy={pick(11, 36, 54)} r="20" fill={a} />
      </>);
    }
  }
  return (
    <svg className={`cover ${className}`} viewBox="0 0 120 160" aria-hidden="true" focusable="false">
      <rect width="120" height="160" fill={ground} />
      <g transform={`translate(${flipX ? 120 : 0} ${flipY ? 160 : 0}) scale(${flipX ? -1 : 1} ${flipY ? -1 : 1})`}>{art}</g>
    </svg>
  );
}
