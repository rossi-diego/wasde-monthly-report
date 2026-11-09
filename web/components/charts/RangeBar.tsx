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
}: {
  lo: number;
  hi: number;
  mean: number | null;
  value: number;
  color: string;
  ariaLabel: string;
  format: (v: number) => string;
  height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(260);
  const min = Math.min(lo, value, 0);
  const max = Math.max(hi, value) * 1.08 || 1;
  const pad = 8;
  const x = (v: number) => pad + ((v - min) / (max - min || 1)) * (width - 2 * pad);
  const mid = 12;
  return (
    <div ref={ref} className="w-full">
      <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} width="100%" height={height} className="block">
        <line x1={pad} x2={width - pad} y1={mid} y2={mid} style={{ stroke: "var(--grid)" }} strokeWidth={6} strokeLinecap="round" />
        <rect x={x(lo)} y={mid - 6} width={Math.max(2, x(hi) - x(lo))} height={12} rx={4} style={{ fill: "var(--bar-past)" }} />
        {mean !== null && <line x1={x(mean)} x2={x(mean)} y1={mid - 8} y2={mid + 8} style={{ stroke: "var(--muted)" }} strokeWidth={2} />}
        <circle cx={x(value)} cy={mid} r={6.5} style={{ fill: color, stroke: "var(--card)" }} strokeWidth={2} />
        <text x={x(lo)} y={height - 2} fontSize={10.5} textAnchor="middle" style={{ fill: "var(--muted)" }}>
          {format(lo)}
        </text>
        <text x={x(hi)} y={height - 2} fontSize={10.5} textAnchor="middle" style={{ fill: "var(--muted)" }}>
          {format(hi)}
        </text>
      </svg>
    </div>
  );
}
