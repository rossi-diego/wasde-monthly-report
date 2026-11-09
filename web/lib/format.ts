import type { Lang } from "./i18n";

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

// PT abbreviations ("mil." would read as "thousand" in Portuguese).
const SHORT_PT: Record<string, string> = {
  m_bales: "mi fardos",
  m_bu: "mi bu",
  m_acres: "mi acres",
  usd_per_short_ton: "$/t curta",
  m_lbs: "mi lb",
  k_short_tons: "mil t curtas",
};

export const unitShort = (u?: string | null, lang: Lang = "en") =>
  u ? ((lang === "pt" ? SHORT_PT[u] : undefined) ?? SHORT[u] ?? u) : "";

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

export function qty(v: number | null | undefined, unit?: string | null, lang: Lang = "en"): string {
  if (v === null || v === undefined) return "—";
  return `${num(v, decimals(unit, v))} ${unitShort(unit, lang)}`.trim();
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

// Month names come from fixed tables (not Intl) so the server and every browser print the same text.
const MONTHS: Record<Lang, { long: string[]; short: string[] }> = {
  en: {
    long: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    short: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  },
  pt: {
    long: ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
    short: ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
  },
};

/** Month number 1-12 -> "September" / "setembro" (or the short form). */
export function monthOf(mo: number, style: "long" | "short" = "long", lang: Lang = "en"): string {
  return MONTHS[lang][style][(((mo - 1) % 12) + 12) % 12] ?? "";
}

/** "2026-10-09T00:00:00" -> "Oct 9, 2026" / "9 out 2026" (no time-zone drift: the date part only). */
export function shortDate(iso: string | null | undefined, withYear = true, lang: Lang = "en"): string | null {
  if (!iso) return null;
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return null;
  const mon = monthOf(m, "short", lang);
  if (lang === "pt") return withYear ? `${d} ${mon} ${y}` : `${d} ${mon}`;
  return withYear ? `${mon} ${d}, ${y}` : `${mon} ${d}`;
}

/** "2026-09" -> "September" / "setembro" (or "Sep" / "set" with style "short"). */
export function monthName(m: string | null | undefined, style: "long" | "short" = "long", lang: Lang = "en"): string {
  if (!m) return "";
  return monthOf(Number(m.split("-")[1]), style, lang);
}

/** "2026-10" -> "October 2026" / "outubro de 2026". */
export function monthYear(m: string | null | undefined, lang: Lang = "en"): string {
  if (!m) return "";
  const y = m.slice(0, 4);
  return lang === "pt" ? `${monthName(m, "long", "pt")} de ${y}` : `${monthName(m, "long", "en")} ${y}`;
}

export function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${s}`;
}

/** "9th" / "9º" */
export const ordinalIn = (n: number, lang: Lang = "en") => (lang === "pt" ? `${n}º` : ordinal(n));

/** A share (0.6554) as a percentage: "65.5%". */
export function share(v: number | null | undefined, d = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(d)}%`;
}

/** Metric tonnes, scaled with at least 3 significant digits: "30.23 MMT", "361 thou. t",
 *  "15.2 thou. t", "1,523 t" (whole tonnes below 10,000, so values match USDA's tables).
 *  PT: "30.23 mi t", "361 mil t". */
export function tonnes(mt: number | null | undefined, lang: Lang = "en"): string {
  if (mt === null || mt === undefined || Number.isNaN(mt)) return "—";
  const a = Math.abs(mt);
  if (a >= 1e6) return `${num(mt / 1e6, 2)} ${lang === "pt" ? "mi t" : "MMT"}`;
  if (a >= 1e5) return `${num(mt / 1e3, 0)} ${lang === "pt" ? "mil t" : "thou. t"}`;
  if (a >= 1e4) return `${num(mt / 1e3, 1)} ${lang === "pt" ? "mil t" : "thou. t"}`;
  return `${num(mt, 0)} t`;
}

/** Axis tick for tonnes, in the same units as {@link tonnes}: "1.5 MMT", "250 thou. t", "0". */
export function tonnesAxis(mt: number, lang: Lang = "en"): string {
  const a = Math.abs(mt);
  if (a === 0) return "0";
  if (a >= 1e6) return `${num(mt / 1e6, a >= 1e7 || Number.isInteger(mt / 1e6) ? 0 : 1)} ${lang === "pt" ? "mi t" : "MMT"}`;
  if (a >= 1e3) return `${num(mt / 1e3, Number.isInteger(mt / 1e3) ? 0 : 1)} ${lang === "pt" ? "mil t" : "thou. t"}`;
  return `${num(mt, 0)} t`;
}

/** Signed native-unit change: "+282", "−5". */
export function signedQty(v: number | null | undefined, unit?: string | null, lang: Lang = "en"): string {
  if (v === null || v === undefined) return "—";
  return `${signed(v, decimals(unit, v))} ${unitShort(unit, lang)}`.trim();
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
