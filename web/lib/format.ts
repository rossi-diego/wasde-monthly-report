const SHORT: Record<string, string> = {
  mmt: "MMT",
  m_bales: "mil. bales",
  m_bu: "mil. bu",
  m_acres: "mil. acres",
  bu_per_acre: "bu/acre",
  lb_per_acre: "lb/acre",
  usd_per_bu: "$/bu",
  usd_per_cwt: "$/cwt",
  usd_per_short_ton: "$/short ton",
  cents_per_lb: "¢/lb",
  m_lbs: "mil. lbs",
  k_short_tons: "thou. short tons",
  pct: "%",
};

export const unitShort = (u?: string | null) => (u ? SHORT[u] ?? u : "");

export function decimals(unit?: string | null, v = 0): number {
  if (unit === "mmt" || unit === "m_bales") return Math.abs(v) < 10 ? 2 : 1;
  if (unit === "bu_per_acre" || unit === "m_acres") return 1;
  if (unit === "usd_per_bu" || unit === "usd_per_cwt" || unit === "cents_per_lb") return 2;
  return 0;
}

export function num(v: number | null | undefined, d = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function qty(v: number | null | undefined, unit?: string | null): string {
  if (v === null || v === undefined) return "—";
  return `${num(v, decimals(unit, v))} ${unitShort(unit)}`.trim();
}

export function signed(v: number | null | undefined, d = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v === 0) return "unch.";
  const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  return `${v > 0 ? "+" : "−"}${s}`;
}

export function pct(v: number | null | undefined, d = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(d)}%`;
}

export function monthLabel(m: string, style: "long" | "short" = "long"): string {
  const [y, mo] = m.split("-").map(Number);
  return new Date(Date.UTC(y, mo - 1, 1)).toLocaleDateString("en-US", {
    month: style,
    year: "numeric",
    timeZone: "UTC",
  });
}

export function bytes(n: number): string {
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** "proj" -> "Proj.", "est" -> "Est." */
export const flagLabel = (f?: string | null) => (f ? `${f[0].toUpperCase()}${f.slice(1)}.` : "");

export const CYCLE_LABEL = (m: number) => {
  // cycle month 0 = May of the marketing-year start
  const names = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"];
  return `${names[((m % 12) + 12) % 12]}${m >= 12 ? ` +${Math.floor(m / 12)}y` : ""}`;
};
