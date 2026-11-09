"use client";

import { niceTicks, useWidth } from "@/components/charts/common";

/** Signed weekly bars (net sales can be negative) with an optional horizontal reference line. */
export default function WeeklyBars({
  items,
  reference,
  referenceLabel,
  color,
  ariaLabel,
  format,
  height = 180,
}: {
  items: { label: string; value: number | null }[];
  reference?: number | null;
  referenceLabel?: string;
  color: string;
  ariaLabel: string;
  format: (v: number) => string;
  height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const vals = items.map((i) => i.value ?? 0);
  const ticks = niceTicks(Math.min(0, ...vals), Math.max(0, reference ?? 0, ...vals), 4);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const m = { l: 52, r: 8, t: 14, b: 24 };
  const y = (v: number) => height - m.b - ((v - lo) / (hi - lo || 1)) * (height - m.b - m.t);
  const slot = (width - m.l - m.r) / Math.max(items.length, 1);
  const bw = Math.max(2, Math.min(28, slot * 0.68));
  const every = Math.max(1, Math.ceil(36 / slot));
  return (
    <div ref={ref} className="w-full">
      <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} width="100%" height={height} className="block">
        {ticks.map((tk) => (
          <g key={tk}>
            <line x1={m.l} x2={width - m.r} y1={y(tk)} y2={y(tk)} style={{ stroke: tk === 0 ? "var(--muted)" : "var(--grid)" }} strokeWidth={1} />
            <text x={m.l - 6} y={y(tk) + 4} textAnchor="end" fontSize={11} style={{ fill: "var(--muted)" }}>
              {format(tk)}
            </text>
          </g>
        ))}
        {items.map((it, i) => {
          if (it.value === null) return null;
          const x = m.l + i * slot + (slot - bw) / 2;
          const top = y(Math.max(it.value, 0));
          const h = Math.abs(y(it.value) - y(0));
          return (
            <rect key={it.label} x={x} y={top} width={bw} height={Math.max(h, 1)} rx={Math.min(3, bw / 3)} style={{ fill: it.value < 0 ? "var(--down)" : color }}>
              <title>{`${it.label}: ${format(it.value)}`}</title>
            </rect>
          );
        })}
        {reference !== null && reference !== undefined && (
          <g>
            <line x1={m.l} x2={width - m.r} y1={y(reference)} y2={y(reference)} style={{ stroke: "var(--text)" }} strokeWidth={1.5} strokeDasharray="5 4" />
            {referenceLabel && (
              <text x={m.l + 4} y={y(reference) - 5} textAnchor="start" fontSize={11} fontWeight={600} paintOrder="stroke" strokeWidth={4} style={{ fill: "var(--text)", stroke: "var(--card)" }}>
                {referenceLabel}
              </text>
            )}
          </g>
        )}
        {items.map((it, i) =>
          i % every === 0 || i === items.length - 1 ? (
            <text key={`l-${it.label}`} x={m.l + i * slot + slot / 2} y={height - 7} textAnchor="middle" fontSize={11} style={{ fill: "var(--muted)" }}>
              {it.label}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}
