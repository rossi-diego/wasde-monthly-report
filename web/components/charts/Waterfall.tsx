"use client";

import { niceTicks, useWidth } from "@/components/charts/common";

export type Step = { label: string; label2?: string; value: number; kind: "total" | "delta" };

/** Bridge from one total to the next. Totals start at the axis floor (printed on the axis,
 *  which does not start at zero: the change is the story); deltas float on the running level. */
export default function Waterfall({
  steps,
  ariaLabel,
  height = 250,
  format = (v) => String(v),
}: {
  steps: Step[];
  ariaLabel: string;
  height?: number;
  format?: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  // [start, end] of every bar; a total's start is the axis floor, filled in below.
  const spans: [number | null, number][] = [];
  let level = 0;
  for (const s of steps) {
    if (s.kind === "total") {
      level = s.value;
      spans.push([null, level]);
    } else {
      spans.push([level, level + s.value]);
      level += s.value;
    }
  }
  const levels = spans.flatMap(([a, b]) => (a === null ? [b] : [a, b]));
  const lo0 = Math.min(...levels);
  const hi0 = Math.max(...levels);
  const span = Math.max(hi0 - lo0, Math.abs(hi0) * 0.02, 1e-6);
  const ticks = niceTicks(Math.max(0, lo0 - span * 0.6), hi0 + span * 0.12, 4);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const m = { l: 46, r: 8, t: 22, b: 40 };
  const y = (v: number) => height - m.b - ((v - lo) / (hi - lo || 1)) * (height - m.b - m.t);
  const slot = (width - m.l - m.r) / Math.max(steps.length, 1);
  const bw = Math.min(56, slot * 0.56);
  const labelSize = slot < 64 ? 10 : 11; // category labels stay apart on a phone

  const bars = steps.map((s, i) => {
    const a = spans[i][0] ?? lo;
    const b = spans[i][1];
    const top = y(Math.max(a, b));
    const bottom = y(Math.min(a, b));
    const fill = s.kind === "total" ? "var(--wasde)" : s.value >= 0 ? "var(--up)" : "var(--down)";
    const val = s.kind === "total" ? format(s.value) : `${s.value >= 0 ? "+" : "−"}${format(Math.abs(s.value))}`;
    return { s, i, cx: m.l + i * slot + slot / 2, top, h: Math.max(2, bottom - top), fill, val };
  });

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
        {bars.map((b) => (
          <g key={b.i}>
            <rect x={b.cx - bw / 2} y={b.top} width={bw} height={b.h} rx={4} style={{ fill: b.fill }} />
            <text x={b.cx} y={b.top - 6} textAnchor="middle" fontSize={12} fontWeight={600} className="mono" style={{ fill: "var(--text)" }}>
              {b.val}
            </text>
            <text x={b.cx} y={height - 22} textAnchor="middle" fontSize={labelSize} style={{ fill: "var(--muted)" }}>
              {b.s.label}
            </text>
            {b.s.label2 && (
              <text x={b.cx} y={height - 8} textAnchor="middle" fontSize={labelSize} style={{ fill: "var(--muted)" }}>
                {b.s.label2}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
