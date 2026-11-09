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

/** Share of a target by week (or month): prior years thin, a min–max band with its mean, the
 *  current year thick in the report colour, and a reference line (100% by default).
 *  ``domain="data"`` scales the y axis to the values (e.g. oil yields of 11.4–12 lb/bu, or a
 *  deviation from the 5-yr mean in percentage points). An empty ``targetLabel`` draws the
 *  reference line without an in-plot label (the caller names it in its legend); ``yUnit`` prints
 *  the y unit above the axis. */
export default function PaceChart({
  lines,
  band,
  xMax,
  color,
  ariaLabel,
  targetLabel,
  height = 260,
  format,
  xTicks: xTickLabels,
  reference = 1,
  domain = "zero",
  yUnit,
}: {
  lines: PaceLine[];
  band: BandPoint[];
  xMax: number;
  color: string;
  ariaLabel: string;
  targetLabel: string;
  height?: number;
  format: (v: number) => string;
  /** Custom x labels (default: week numbers 1, 10, 20 …). */
  xTicks?: { x: number; label: string }[];
  /** Horizontal reference value (null: none). */
  reference?: number | null;
  domain?: "zero" | "data";
  yUnit?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const ys = [
    ...lines.flatMap((l) => l.points.map((p) => p[1]).filter((v): v is number => v !== null)),
    ...band.flatMap((b) => [b.min, b.max].filter((v): v is number => v !== null)),
    ...(reference !== null ? [reference] : []),
  ];
  const ticks = domain === "data" ? niceTicks(Math.min(...ys), Math.max(...ys), 4) : niceTicks(0, Math.max(...ys), 4);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const m = { l: 44, r: 12, t: yUnit ? 24 : 12, b: 26 };
  const x = (v: number) => m.l + ((v - 1) / Math.max(xMax - 1, 1)) * (width - m.l - m.r);
  const y = (v: number) => height - m.b - ((v - lo) / (hi - lo || 1)) * (height - m.b - m.t);
  const xTicksAll = xTickLabels ?? [1, 10, 20, 30, 40, 50].filter((w) => w <= xMax).map((w) => ({ x: w, label: String(w) }));
  // The band is drawn per run of weeks that have one: a week without a band (too few
  // comparable seasons) leaves a gap, never a bridge.
  const bandRuns: { x: number; min: number; max: number }[][] = [];
  let curRun: { x: number; min: number; max: number }[] = [];
  for (const b of band) {
    if (b.min === null || b.max === null) {
      if (curRun.length) bandRuns.push(curRun);
      curRun = [];
    } else curRun.push({ x: b.x, min: b.min, max: b.max });
  }
  if (curRun.length) bandRuns.push(curRun);
  const areas = bandRuns
    .filter((r) => r.length > 1)
    .map((r) =>
      [...r.map((b) => `${x(b.x).toFixed(1)},${y(b.max).toFixed(1)}`), ...[...r].reverse().map((b) => `${x(b.x).toFixed(1)},${y(b.min).toFixed(1)}`)].join(" "),
    );
  // Thin the x labels from the right (the newest week always keeps its label) so that two
  // labels never collide on a narrow screen ("Sep 20ct 25" at 360 px).
  const xTicks: { x: number; label: string }[] = [];
  for (const tk of [...xTicksAll].reverse()) {
    const prev = xTicks[0];
    if (!prev || x(prev.x) - x(tk.x) >= (prev.label.length + tk.label.length) * 3.3 + 10) xTicks.unshift(tk);
  }
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
        {yUnit && (
          <text x={4} y={12} fontSize={11} style={{ fill: "var(--muted)" }}>
            {yUnit}
          </text>
        )}
        {areas.map((pts, i) => (
          <polygon key={`band-${i}`} points={pts} style={{ fill: color, opacity: 0.14 }} />
        ))}
        {reference !== null && (
          <>
            <line x1={m.l} x2={width - m.r} y1={y(reference)} y2={y(reference)} style={{ stroke: "var(--muted)" }} strokeWidth={1} strokeDasharray="2 3" />
            {targetLabel && (
              <text x={width - m.r} y={y(reference) - 5} textAnchor="end" fontSize={11} style={{ fill: "var(--muted)" }}>
                {targetLabel}
              </text>
            )}
          </>
        )}
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
          // A label at the right edge is end-anchored so it is never clipped.
          <text key={w.x} x={x(w.x)} y={height - 8} textAnchor={x(w.x) > width - m.r - 24 ? "end" : "middle"} fontSize={11} style={{ fill: "var(--muted)" }}>
            {w.label}
          </text>
        ))}
      </svg>
    </div>
  );
}
