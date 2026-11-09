/** Tiny trend line for KPI tiles (white on the tile colour). Fixed size, so no measuring needed. */
export default function Sparkline({ values, ariaLabel }: { values: number[]; ariaLabel: string }) {
  if (values.length < 2) return null;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pts = values.map((v, i) => [2 + (i * 92) / (values.length - 1), 29 - ((v - lo) / (hi - lo || 1)) * 26]);
  const last = pts[pts.length - 1];
  return (
    <svg role="img" aria-label={ariaLabel} width="96" height="32" viewBox="0 0 96 32" className="shrink-0">
      <polyline
        points={pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")}
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={last[0]} cy={last[1]} r="3" fill="#FFFFFF" />
    </svg>
  );
}
