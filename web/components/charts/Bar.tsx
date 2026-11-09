"use client";

import { niceTicks, useWidth } from "@/components/charts/common";

export type BarItem = { label: string; value: number; kind: "past" | "est" | "current" };

const FILL: Record<BarItem["kind"], string> = {
  past: "var(--bar-past)",
  est: "var(--bar-est)",
  current: "var(--wasde)",
};

/** Vertical bars from zero; the highlighted bar is the current projection. */
export default function Bar({
  items,
  ariaLabel,
  height = 230,
  format = (v) => String(v),
}: {
  items: BarItem[];
  ariaLabel: string;
  height?: number;
  format?: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const m = { l: 40, r: 8, t: 12, b: 26 };
  const max = Math.max(0, ...items.map((i) => i.value));
  const ticks = niceTicks(0, max || 1, 4);
  const top = ticks[ticks.length - 1];
  const x0 = m.l;
  const x1 = width - m.r;
  const y0 = height - m.b;
  const y = (v: number) => y0 - (v / top) * (y0 - m.t);
  const slot = (x1 - x0) / Math.max(items.length, 1);
  const bw = Math.max(2, slot * 0.68);

  // X labels at least ~52px apart, always ending on the last bar.
  const every = Math.max(1, Math.ceil(52 / slot));
  const shown = new Set<number>();
  for (let i = items.length - 1; i >= 0; i -= every) shown.add(i);

  return (
    <div ref={ref} className="w-full">
      <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} width="100%" height={height} className="block">
        {ticks.map((tk) => (
          <g key={tk}>
            <line x1={x0} x2={x1} y1={y(tk)} y2={y(tk)} style={{ stroke: "var(--grid)" }} strokeWidth={1} />
            <text x={x0 - 6} y={y(tk) + 4} textAnchor="end" fontSize={11} style={{ fill: "var(--muted)" }}>
              {format(tk)}
            </text>
          </g>
        ))}
        {items.map((it, i) => {
          const h = Math.max(0, y0 - y(it.value));
          const x = x0 + i * slot + (slot - bw) / 2;
          return (
            <rect key={it.label} x={x} y={y0 - h} width={bw} height={h} rx={Math.min(3, bw / 3)} style={{ fill: FILL[it.kind] }}>
              <title>{`${it.label}: ${format(it.value)}`}</title>
            </rect>
          );
        })}
        {items.map((it, i) =>
          shown.has(i) ? (
            <text key={it.label} x={x0 + i * slot + slot / 2} y={height - 8} textAnchor="middle" fontSize={11} style={{ fill: "var(--muted)" }}>
              {it.label.length === 7 ? it.label.slice(2) : it.label}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}
