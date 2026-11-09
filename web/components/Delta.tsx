import { signed } from "@/lib/format";

/** Signed change with an arrow; direction carried by glyph + sign, color only reinforces. */
export default function Delta({
  value,
  digits = 0,
  suffix = "",
  className = "",
}: {
  value: number | null | undefined;
  digits?: number;
  suffix?: string;
  className?: string;
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className={`text-muted ${className}`}>—</span>;
  }
  if (Math.abs(value) < 0.5 * 10 ** -digits) value = 0; // "−0.0" is not a move
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "";
  return (
    <span className={`tabular whitespace-nowrap ${tone} ${className}`}>
      {arrow && (
        <span aria-hidden className="mr-0.5 text-[0.7em]">
          {arrow}
        </span>
      )}
      {signed(value, digits)}
      {value !== 0 && suffix}
    </span>
  );
}
