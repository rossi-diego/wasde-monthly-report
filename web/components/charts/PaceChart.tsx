"use client";

import { niceTicks, useWidth } from "@/components/charts/common";

export type PaceLine = { id: string; points: [number, number | null][]; current: boolean };
export type BandPoint = { x: number; mean: number | null; min: number | null; max: number | null };

/** Runs of consecutive non-null points (a missing as-of target breaks the line, never bridges it). */
function runs(points: [number, number | null][]): [number, number][][] {
  const out: [number, number][][] = [];
  let cur: [number, number][] = [];
  for (const [x, y] of points) {
    if (y === null || y === undefined) {
      if (cur.length) out.push(cur);
      cur = [];
    } else cur.push([x, y]);
  }
  if (cur.length) out.push(cur);
  return out;
}

/** Share of a target by week: prior years thin, a min–max band with its mean, the current year
 *  thick in the report colour, and a 100% reference line. */
export default function PaceChart({
  lines,
  band,
  xMax,
  color,
  ariaLabel,
  targetLabel,
  height = 260,
  format,
}: {
  lines: PaceLine[];
  band: BandPoint[];
  xMax: number;
  color: string;
  ariaLabel: string;
  targetLabel: string;
  height?: number;
  format: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const ys = [
    ...lines.flatMap((l) => l.points.map((p) => p[1]).filter((v): v is number => v !== null)),
    ...band.flatMap((b) => [b.min, b.max].filter((v): v is number => v !== null)),
    1,
  ];
  const ticks = niceTicks(0, Math.max(...ys), 4);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const m = { l: 44, r: 12, t: 12, b: 26 };
  const x = (v: number) => m.l + ((v - 1) / Math.max(xMax - 1, 1)) * (width - m.l - m.r);
  const y = (v: number) => height - m.b - ((v - lo) / (hi - lo || 1)) * (height - m.b - m.t);
  const xTicks = [1, 10, 20, 30, 40, 50].filter((w) => w <= xMax);
  const bandPts = band.filter((b) => b.min !== null && b.max !== null) as { x: number; min: number; max: number; mean: number | null }[];
  const area =
    bandPts.length > 1
      ? [
          ...bandPts.map((b) => `${x(b.x).toFixed(1)},${y(b.max).toFixed(1)}`),
          ...[...bandPts].reverse().map((b) => `${x(b.x).toFixed(1)},${y(b.min).toFixed(1)}`),
        ].join(" ")
      : null;
  const meanRuns = runs(band.map((b) => [b.x, b.mean]));
  const ordered = [...lines].sort((a, b) => Number(a.current) - Number(b.current));
  const poly = (pts: [number, number][]) => pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");

  return (
    <div ref={ref} className="w-full">
      <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} width="100%" height={height} className="block">
        {ticks.map((tk) => (
          <g key={tk}>
            <line x1={m.l} x2={width - m.r} y1={y(tk)} y2={y(tk)} style={{ stroke: "var(--grid)" }} strokeWidth={1} />
            <text x={m.l - 6} y={y(tk) + 4} textAnchor="end" fontSize={11} style={{ fill: "var(--muted)" }}>
              {format(tk)}
            </text>
          </g>
        ))}
        {area && <polygon points={area} style={{ fill: color, opacity: 0.14 }} />}
        <line x1={m.l} x2={width - m.r} y1={y(1)} y2={y(1)} style={{ stroke: "var(--muted)" }} strokeWidth={1} strokeDasharray="2 3" />
        <text x={width - m.r} y={y(1) - 5} textAnchor="end" fontSize={11} style={{ fill: "var(--muted)" }}>
          {targetLabel}
        </text>
        {ordered.map((l) =>
          runs(l.points).map((pts, i) => (
            <polyline
              key={`${l.id}-${i}`}
              points={poly(pts)}
              fill="none"
              style={{ stroke: l.current ? color : "var(--bar-past)" }}
              strokeWidth={l.current ? 3.5 : 1.6}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )),
        )}
        {meanRuns.map((pts, i) => (
          <polyline key={`mean-${i}`} points={poly(pts)} fill="none" style={{ stroke: "var(--muted)" }} strokeWidth={1.6} strokeDasharray="5 4" />
        ))}
        {lines
          .filter((l) => l.current)
          .map((l) => {
            const last = [...l.points].reverse().find((p) => p[1] !== null);
            return last ? <circle key={`${l.id}-dot`} cx={x(last[0])} cy={y(last[1] as number)} r={4.5} style={{ fill: color }} /> : null;
          })}
        {xTicks.map((w) => (
          <text key={w} x={x(w)} y={height - 8} textAnchor="middle" fontSize={11} style={{ fill: "var(--muted)" }}>
            {w}
          </text>
        ))}
      </svg>
    </div>
  );
}
