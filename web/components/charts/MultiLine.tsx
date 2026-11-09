"use client";

import { niceTicks, useWidth } from "@/components/charts/common";

export type Line = { id: string; points: [number, number][]; highlight: boolean; endLabel?: string };

/** Several paths on a shared x axis; highlighted lines are drawn last, thicker and in colour. */
export default function MultiLine({
  lines,
  xMax,
  xTicks,
  ariaLabel,
  height = 230,
  format = (v) => String(v),
}: {
  lines: Line[];
  xMax: number;
  xTicks: { x: number; label: string }[];
  ariaLabel: string;
  height?: number;
  format?: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const ys = lines.flatMap((l) => l.points.map((p) => p[1]));
  const ticks = niceTicks(Math.min(...ys), Math.max(...ys), 4);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const labelRoom = lines.some((l) => l.endLabel) ? 78 : 10;
  const m = { l: 46, r: labelRoom, t: 14, b: 26 };
  const x = (v: number) => m.l + (v / Math.max(xMax, 1)) * (width - m.l - m.r);
  const y = (v: number) => height - m.b - ((v - lo) / (hi - lo || 1)) * (height - m.b - m.t);
  const shownTicks: typeof xTicks = [];
  for (const t of xTicks) {
    const prev = shownTicks[shownTicks.length - 1];
    if (!prev || x(t.x) - x(prev.x) >= 40) shownTicks.push(t);
  }
  const ordered = [...lines].sort((a, b) => Number(a.highlight) - Number(b.highlight));

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
        {ordered.map((l) => {
          const pts = l.points.filter((p) => p[0] <= xMax);
          if (!pts.length) return null;
          const last = pts[pts.length - 1];
          const stroke = l.highlight ? "var(--wasde)" : "var(--bar-past)";
          return (
            <g key={l.id}>
              <polyline
                points={pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ")}
                fill="none"
                style={{ stroke }}
                strokeWidth={l.highlight ? 3.5 : 1.8}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {l.highlight && <circle cx={x(last[0])} cy={y(last[1])} r={4} style={{ fill: stroke }} />}
              {l.endLabel && (
                <text x={x(last[0]) + 8} y={y(last[1]) + 4} fontSize={11} fontWeight={600} style={{ fill: l.highlight ? "var(--wasde)" : "var(--muted)" }}>
                  {l.endLabel}
                </text>
              )}
            </g>
          );
        })}
        {shownTicks.map((t) => (
          <text key={t.x} x={x(t.x)} y={height - 8} textAnchor="middle" fontSize={11} style={{ fill: "var(--muted)" }}>
            {t.label}
          </text>
        ))}
      </svg>
    </div>
  );
}
