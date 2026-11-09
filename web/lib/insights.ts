// Pure, client-safe derivations from the published JSON. Every number on the dashboard
// comes from here or straight from the JSON; nothing is typed in by hand.

import type { BarItem } from "@/components/charts/Bar";
import type { Line } from "@/components/charts/MultiLine";
import type { Step } from "@/components/charts/Waterfall";

import { decimals, monthName, num, qty, unitShort } from "./format";
import type { Overview, Series } from "./types";

const NOUN: Record<string, string> = {
  soybeans: "soybean",
  soybean_meal: "soybean meal",
  soybean_oil: "soybean oil",
};

/** "U.S. soybean", "World corn" … */
export function seriesNoun(commodity: string, regionLabel: string, commodityLabel?: string): string {
  const noun = NOUN[commodity] ?? (commodityLabel ?? commodity.replace(/_/g, " ")).toLowerCase();
  return `${regionLabel} ${noun}`;
}

// ---------------------------------------------------------------- stocks-to-use rank (W2)

export type StuView = {
  bars: BarItem[];
  rows: (string | number)[][];
  now: number | null;
  nowMy: string | null;
  estMy: string | null;
  k: number;
  n: number;
  from: string;
  to: string;
};

/** Rank of the current projection among the final values of completed seasons:
 *  k = number of final seasons with a strictly lower stocks-to-use ("tighter"). */
export function stuView(s: Series): StuView {
  const hist = s.stocks_to_use_history.filter((h) => h.stocks_to_use_pct !== null);
  const finals = hist.filter((h) => h.status === "final");
  const currents = hist.filter((h) => h.status === "current");
  const proj = currents[currents.length - 1] ?? null;
  const now = proj?.stocks_to_use_pct ?? null;
  const k = now === null ? 0 : finals.filter((h) => (h.stocks_to_use_pct as number) < now).length;
  const d = decimals(s.unit, proj?.ending_stocks ?? 0);
  return {
    bars: hist.map((h) => ({
      label: h.market_year,
      value: h.stocks_to_use_pct as number,
      kind: h.status === "final" ? "past" : h === proj ? "current" : "est",
    })),
    rows: hist.map((h) => [
      h.market_year,
      `${num(h.stocks_to_use_pct, 1)}%`,
      num(h.ending_stocks, d),
      h.status === "final" ? "final" : (h.flag ?? "current"),
    ]),
    now,
    nowMy: proj?.market_year ?? null,
    estMy: currents.length > 1 ? currents[currents.length - 2].market_year : null,
    k,
    n: finals.length,
    from: hist[0]?.market_year ?? "",
    to: hist[hist.length - 1]?.market_year ?? "",
  };
}

// ---------------------------------------------------------------- revision paths

const CYCLE_SHORT = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"];

export type RevView = {
  lines: Line[];
  xMax: number;
  xTicks: { x: number; label: string }[];
  rows: (string | number)[][];
  head: string[];
  firstMy: string;
  lastMy: string;
  greyFrom: string;
  greyTo: string;
  curMin: number | null;
  curMax: number | null;
  since: string;
  digits: number;
};

/** Current marketing year highlighted, the `previous` before it in grey, by month of the cycle. */
export function revView(s: Series, attr = "ending_stocks", previous = 5, xMax = 17): RevView | null {
  const all = s.revisions[attr] ?? [];
  const sel = all.slice(-(previous + 1));
  if (!sel.length) return null;
  const sample = sel[sel.length - 1].points.at(-1)?.[1] ?? 0;
  const digits = attr === "stocks_to_use_pct" || attr === "yield" ? 1 : decimals(s.unit, sample ?? 0);
  const clean = sel.map((l) => ({
    my: l.market_year,
    pts: l.points
      .filter((p) => p[0] !== null && p[1] !== null && (p[0] as number) <= xMax)
      .map((p) => [p[0] as number, p[1] as number, p[2]] as const),
  }));
  const cur = clean[clean.length - 1];
  const lines: Line[] = clean.map((l, i) => {
    const last = l.pts[l.pts.length - 1];
    const isCur = i === clean.length - 1;
    return {
      id: l.my,
      points: l.pts.map((p) => [p[0], p[1]] as [number, number]),
      highlight: isCur,
      endLabel: isCur && last ? `${l.my}  ${num(last[1], digits)}` : undefined,
    };
  });
  const xTicks = [];
  for (let x = 0; x <= xMax; x += 3) xTicks.push({ x, label: CYCLE_SHORT[x % 12] });
  const months = Array.from({ length: xMax + 1 }, (_, i) => i);
  const rows = months
    .map((mIdx) => [
      `${CYCLE_SHORT[mIdx % 12]}${mIdx >= 12 ? " (yr 2)" : ""}`,
      ...clean.map((l) => {
        const p = l.pts.find((q) => q[0] === mIdx);
        return p ? num(p[1], digits) : "—";
      }),
    ])
    .filter((r) => r.slice(1).some((c) => c !== "—"));
  const curVals = cur.pts.map((p) => p[1]);
  return {
    lines,
    xMax,
    xTicks,
    rows,
    head: ["Month of cycle", ...clean.map((l) => l.my)],
    firstMy: clean[0].my,
    lastMy: cur.my,
    greyFrom: clean[0].my,
    greyTo: clean.length > 1 ? clean[clean.length - 2].my : clean[0].my,
    curMin: curVals.length ? Math.min(...curVals) : null,
    curMax: curVals.length ? Math.max(...curVals) : null,
    since: cur.pts[0] ? monthName(cur.pts[0][2]) : "",
    digits,
  };
}

// ---------------------------------------------------------------- drivers waterfall

const DRIVER_LABEL: Record<string, [string, string?]> = {
  beginning_stocks: ["Beginning", "stocks"],
  production: ["Production"],
  production_area: ["Area"],
  production_yield: ["Yield"],
  imports: ["Imports"],
  domestic_total: ["Domestic", "use"],
  exports: ["Exports"],
  other: ["Other"],
};

export type WaterfallView = {
  steps: Step[];
  from: number;
  to: number;
  marketYear: string;
  digits: number;
  aria: string;
  rows: (string | number)[][];
};

export function waterfallView(s: Series, marketYear: string | undefined, prevMonth: string | null): WaterfallView | null {
  const drv = marketYear ? s.drivers.find((d) => d.market_year === marketYear) : s.drivers[s.drivers.length - 1];
  if (!drv || drv.from === null || drv.to === null) return null;
  const digits = decimals(s.unit, drv.to);
  const comps = drv.components.filter((c) => c.value !== null && Math.abs(c.value) > 1e-9);
  if (!comps.length && drv.from === drv.to) return null;
  const prevShort = prevMonth ? monthName(prevMonth, "short") : "Previous";
  const curShort = monthName(s.report_month, "short");
  const steps: Step[] = [
    { label: prevShort, label2: "estimate", value: drv.from, kind: "total" },
    ...comps.map((c) => {
      const [a, b] = DRIVER_LABEL[c.id] ?? [c.label];
      return { label: a, label2: b, value: c.value as number, kind: "delta" as const };
    }),
    { label: curShort, label2: "estimate", value: drv.to, kind: "total" },
  ];
  const f = (v: number) => num(v, digits);
  const sgn = (v: number) => `${v >= 0 ? "+" : "−"}${f(Math.abs(v))}`;
  const parts = comps.map((c) => {
    const v = c.value as number;
    const note = (c.id === "domestic_total" || c.id === "exports") && v < 0 ? " (more use, fewer stocks)" : "";
    return `${c.label.toLowerCase()} ${sgn(v)}${note}`;
  });
  return {
    steps,
    from: drv.from,
    to: drv.to,
    marketYear: drv.market_year,
    digits,
    aria: `Waterfall of ${drv.market_year} ending stocks: ${prevShort} estimate ${f(drv.from)}; ${parts.join("; ")}; ${curShort} estimate ${f(drv.to)} ${unitShort(s.unit)}.`,
    rows: [
      [`${prevShort} estimate`, f(drv.from)],
      ...comps.map((c) => [c.label, sgn(c.value as number)]),
      [`${curShort} estimate`, f(drv.to)],
    ],
  };
}

/** The focus commodity whose U.S. new-crop ending stocks moved most, relative to last month
 *  (|Δ| ÷ previous value, so bushels, pounds and short tons compare fairly). */
export function pickWaterfallCommodity(ov: Overview): string | null {
  let best: { id: string; score: number } | null = null;
  for (const c of ov.cards) {
    const b = c.us?.new;
    if (!b || b.delta === null || !b.prev_ending_stocks) continue;
    const score = Math.abs(b.delta) / Math.abs(b.prev_ending_stocks);
    if (!best || score > best.score) best = { id: c.commodity, score };
  }
  return best?.id ?? null;
}

// ---------------------------------------------------------------- biggest revisions

export type ChangeRow = {
  key: string;
  commodity: string;
  what: string;
  delta: string;
  dir: "up" | "down" | "flat";
  to: string;
  extra: string[];
  frac: number;
};

export function changeRows(ov: Overview): ChangeRow[] {
  const top = Math.max(...ov.highlights.map((h) => h.score), 0) || 1;
  return ov.highlights.map((h) => {
    const d = decimals(h.unit, h.delta);
    const extra: string[] = [];
    if (h.pct_delta !== null) extra.push(`${h.pct_delta > 0 ? "+" : "−"}${num(Math.abs(h.pct_delta * 100), 1)}%`);
    if (h.streak >= 2) extra.push(`${h.streak}${["st", "nd", "rd"][h.streak - 1] ?? "th"} consecutive ${h.delta > 0 ? "raise" : "cut"}`);
    else if (h.related[0]) {
      const r = h.related[0];
      extra.push(`${r.label.toLowerCase()} ${r.delta > 0 ? "+" : "−"}${num(Math.abs(r.delta), decimals(r.unit, r.delta))} ${unitShort(r.unit)}`.trim());
    }
    return {
      key: `${h.commodity}-${h.region_id}-${h.market_year}-${h.attribute}`,
      commodity: h.commodity,
      what: `${seriesNoun(h.commodity, h.region, h.commodity_label)} ${h.attribute_label.toLowerCase()}, ${h.market_year}`,
      delta: `${h.delta > 0 ? "+" : h.delta < 0 ? "−" : ""}${num(Math.abs(h.delta), d)} ${unitShort(h.unit)}`.trim(),
      dir: h.delta > 0 ? "up" : h.delta < 0 ? "down" : "flat",
      to: qty(h.value, h.unit),
      extra,
      frac: Math.max(0.04, h.score / top),
    };
  });
}

// ---------------------------------------------------------------- KPI tiles

export type Kpi = {
  id: string;
  title: string;
  tag: string;
  value: string;
  unit: string;
  dir: "up" | "down" | "flat";
  deltaAbs: string;
  deltaPct: string | null;
  context: string;
  contextKind: "stu" | "text";
  spark: number[];
  sparkLabel: { what: string; since: string; from: string; to: string };
  color: string;
};

/** A tile from one balance-sheet line of one series, for the given marketing year. */
export function kpiFromSeries(
  s: Series,
  attr: string,
  marketYear: string,
  opts: { id: string; title: string; color: string; context: "stu" | "previous_seasons" },
): Kpi | null {
  const col = s.balance_sheet.columns.findIndex((c) => c.market_year === marketYear);
  const row = s.balance_sheet.rows.find((r) => r.id === attr);
  const cell = col >= 0 ? row?.values[col] : undefined;
  if (!row || !cell || cell.value === null) return null;
  const d = decimals(s.unit, cell.value);
  const delta = cell.delta ?? 0;
  let context = "";
  if (opts.context === "stu") {
    const su = s.balance_sheet.rows.find((r) => r.id === "stocks_to_use_pct")?.values[col]?.value;
    context = su === null || su === undefined ? "" : `${num(su, 1)}%`;
  } else {
    context = s.balance_sheet.columns
      .slice(0, col)
      .map((c, i) => `${c.market_year}: ${num(row.values[i]?.value, decimals(s.unit, row.values[i]?.value ?? 0))}`)
      .join(" · ");
  }
  const path = (s.revisions[attr] ?? []).find((l) => l.market_year === marketYear)?.points ?? [];
  const spark = path.filter((p) => p[1] !== null).map((p) => p[1] as number);
  const first = path.find((p) => p[1] !== null);
  return {
    id: opts.id,
    title: opts.title,
    tag: marketYear,
    value: num(cell.value, d),
    unit: unitShort(s.unit),
    dir: delta > 0 ? "up" : delta < 0 ? "down" : "flat",
    deltaAbs: num(Math.abs(delta), d),
    deltaPct: cell.prev ? `${delta >= 0 ? "+" : "−"}${num(Math.abs((delta / cell.prev) * 100), 1)}%` : null,
    context,
    contextKind: opts.context === "stu" ? "stu" : "text",
    spark,
    sparkLabel: {
      what: opts.title,
      since: first ? `${monthName(first[2])} ${first[2].slice(0, 4)}` : "",
      from: spark.length ? num(spark[0], d) : "",
      to: spark.length ? num(spark[spark.length - 1], d) : "",
    },
    color: opts.color,
  };
}
