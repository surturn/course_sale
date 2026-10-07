export default function ListSkeleton({ rows = 4 }) {
  return (
    <ul className="reading-list skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i}><span /><span /></li>
      ))}
    </ul>
  );
}
