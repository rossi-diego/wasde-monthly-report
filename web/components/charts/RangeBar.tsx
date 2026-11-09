"use client";

import { useWidth } from "@/components/charts/common";

/** A value against a historical min–max band (and its mean): a one-line strip chart. */
export default function RangeBar({
  lo,
  hi,
  mean,
  value,
  color,
  ariaLabel,
  format,
  height = 34,
  fromZero = true,
}: {
  lo: number;
  hi: number;
  mean: number | null;
  value: number;
  color: string;
  ariaLabel: string;
  format: (v: number) => string;
  height?: number;
  /** false: scale to the band (values far from zero, e.g. an oil yield of 11.6–11.9 lb/bu). */
  fromZero?: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(260);
  const span = Math.max(hi, value) - Math.min(lo, value) || Math.abs(value) || 1;
  const min = fromZero ? Math.min(lo, value, 0) : Math.min(lo, value) - span * 0.3;
  const max = fromZero ? Math.max(hi, value) * 1.08 || 1 : Math.max(hi, value) + span * 0.3;
  const pad = 8;
  const x = (v: number) => pad + ((v - min) / (max - min || 1)) * (width - 2 * pad);
  const mid = 12;
  // End labels: one under each end of the band, or a single "lo–hi" label under its middle
  // when the band is too narrow for both (e.g. 7.5–8.0 %, which would print "7%8%").
  const loT = format(lo);
  const hiT = format(hi);
  const textW = (s: string) => s.length * 6.2;
  const clampX = (cx: number, s: string) => Math.min(width - textW(s) / 2, Math.max(textW(s) / 2, cx));
  const labels =
    x(hi) - x(lo) >= (textW(loT) + textW(hiT)) / 2 + 6
      ? [
          { x: clampX(x(lo), loT), text: loT },
          { x: clampX(x(hi), hiT), text: hiT },
        ]
      : [{ x: clampX((x(lo) + x(hi)) / 2, loT === hiT ? loT : `${loT}–${hiT}`), text: loT === hiT ? loT : `${loT}–${hiT}` }];
  return (
    <div ref={ref} className="w-full">
      <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} width="100%" height={height} className="block">
        <line x1={pad} x2={width - pad} y1={mid} y2={mid} style={{ stroke: "var(--grid)" }} strokeWidth={6} strokeLinecap="round" />
        <rect x={x(lo)} y={mid - 6} width={Math.max(2, x(hi) - x(lo))} height={12} rx={4} style={{ fill: "var(--bar-past)" }} />
        {mean !== null && <line x1={x(mean)} x2={x(mean)} y1={mid - 8} y2={mid + 8} style={{ stroke: "var(--muted)" }} strokeWidth={2} />}
        <circle cx={x(value)} cy={mid} r={6.5} style={{ fill: color, stroke: "var(--card)" }} strokeWidth={2} />
        {labels.map((l) => (
          <text key={l.text + l.x} x={l.x} y={height - 2} fontSize={10.5} textAnchor="middle" style={{ fill: "var(--muted)" }}>
            {l.text}
          </text>
        ))}
      </svg>
    </div>
  );
}
