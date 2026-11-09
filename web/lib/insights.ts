// Pure, client-safe derivations from the published JSON. Every number on the dashboard
// comes from here or straight from the JSON; nothing is typed in by hand.
// Every function takes the display language (default EN); the numbers do not depend on it.

import type { BarItem } from "@/components/charts/Bar";
import type { Line } from "@/components/charts/MultiLine";
import type { Step } from "@/components/charts/Waterfall";

import { decimals, monthName, monthOf, monthYear, num, ordinal, qty, unitShort } from "./format";
import { translate, type Key, type Lang, type Vars } from "./i18n";
import { attrName, commodityName, regionName } from "./labels";
import type { Overview, Series } from "./types";

const NOUN: Record<string, string> = {
  soybeans: "soybean",
  soybean_meal: "soybean meal",
  soybean_oil: "soybean oil",
};

/** "U.S. soybean", "World corn" … ("Soja (EUA)", "Milho (Mundo)" in PT, which needs the region id). */
export function seriesNoun(
  commodity: string,
  regionLabel: string,
  commodityLabel?: string,
  lang: Lang = "en",
  regionId?: string,
): string {
  if (lang === "pt") {
    const c = commodityName(commodity, "pt", commodityLabel ?? commodity.replace(/_/g, " "));
    return `${c} (${regionId ? regionName(regionId, "pt", regionLabel) : regionLabel})`;
  }
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
  /** Window of the final seasons the rank is computed over (labelled next to every rank). */
  finalFrom: string;
  finalTo: string;
};

/** Rank of the current projection among the final values of completed seasons:
 *  k = number of final seasons with a strictly lower stocks-to-use ("tighter"). */
export function stuView(s: Series, lang: Lang = "en"): StuView {
  const t = (k: Key) => translate(lang, k);
  const hist = s.stocks_to_use_history.filter((h) => h.stocks_to_use_pct !== null);
  const finals = hist.filter((h) => h.status === "final");
  const currents = hist.filter((h) => h.status === "current");
  const proj = currents[currents.length - 1] ?? null;
  const now = proj?.stocks_to_use_pct ?? null;
  const k = now === null ? 0 : finals.filter((h) => (h.stocks_to_use_pct as number) < now).length;
  const d = decimals(s.unit, proj?.ending_stocks ?? 0);
  const status = (h: (typeof hist)[number]) =>
    h.status === "final"
      ? t("status.final")
      : h.flag === "proj"
        ? t("status.proj")
        : h.flag === "est"
          ? t("status.est")
          : (h.flag ?? t("status.current"));
  return {
    bars: hist.map((h) => ({
      label: h.market_year,
      value: h.stocks_to_use_pct as number,
      kind: h.status === "final" ? "past" : h === proj ? "current" : "est",
    })),
    rows: hist.map((h) => [h.market_year, `${num(h.stocks_to_use_pct, 1)}%`, num(h.ending_stocks, d), status(h)]),
    now,
    nowMy: proj?.market_year ?? null,
    estMy: currents.length > 1 ? currents[currents.length - 2].market_year : null,
    k,
    n: finals.length,
    from: hist[0]?.market_year ?? "",
    to: hist[hist.length - 1]?.market_year ?? "",
    finalFrom: finals[0]?.market_year ?? "",
    finalTo: finals[finals.length - 1]?.market_year ?? "",
  };
}

// ---------------------------------------------------------------- revision paths

/** Cycle month 0 = May of the marketing-year start. */
const cycleShort = (x: number, lang: Lang) => monthOf(5 + (x % 12), "short", lang);

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
export function revView(s: Series, attr = "ending_stocks", previous = 5, xMax = 17, lang: Lang = "en"): RevView | null {
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
  for (let x = 0; x <= xMax; x += 3) xTicks.push({ x, label: cycleShort(x, lang) });
  const months = Array.from({ length: xMax + 1 }, (_, i) => i);
  const rows = months
    .map((mIdx) => [
      `${cycleShort(mIdx, lang)}${mIdx >= 12 ? ` ${translate(lang, "rev.yr2")}` : ""}`,
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
    head: [translate(lang, "rev.head"), ...clean.map((l) => l.my)],
    firstMy: clean[0].my,
    lastMy: cur.my,
    greyFrom: clean[0].my,
    greyTo: clean.length > 1 ? clean[clean.length - 2].my : clean[0].my,
    curMin: curVals.length ? Math.min(...curVals) : null,
    curMax: curVals.length ? Math.max(...curVals) : null,
    since: cur.pts[0] ? monthName(cur.pts[0][2], "long", lang) : "",
    digits,
  };
}

// ---------------------------------------------------------------- drivers waterfall

/** Two-line axis labels by driver id. */
const DRIVER_LABEL: Record<Lang, Record<string, [string, string?]>> = {
  en: {
    beginning_stocks: ["Beginning", "stocks"],
    production: ["Production"],
    production_area: ["Area"],
    production_yield: ["Yield"],
    imports: ["Imports"],
    domestic_total: ["Domestic", "use"],
    exports: ["Exports"],
    other: ["Other"],
  },
  pt: {
    beginning_stocks: ["Estoques", "iniciais"],
    production: ["Produção"],
    production_area: ["Área"],
    production_yield: ["Produtiv."],
    imports: ["Importações"],
    domestic_total: ["Uso", "doméstico"],
    exports: ["Exportações"],
    other: ["Outros"],
  },
};

/** Full row labels in PT (the JSON carries the EN label). */
const DRIVER_ROW_PT: Record<string, string> = {
  beginning_stocks: "Estoques iniciais",
  production: "Produção",
  production_area: "Produção · área",
  production_yield: "Produção · produtividade",
  imports: "Importações",
  domestic_total: "Uso doméstico",
  exports: "Exportações",
  other: "Outros / arredondamento",
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

export function waterfallView(
  s: Series,
  marketYear: string | undefined,
  prevMonth: string | null,
  lang: Lang = "en",
): WaterfallView | null {
  const drv = marketYear ? s.drivers.find((d) => d.market_year === marketYear) : s.drivers[s.drivers.length - 1];
  if (!drv || drv.from === null || drv.to === null) return null;
  const digits = decimals(s.unit, drv.to);
  const comps = drv.components.filter((c) => c.value !== null && Math.abs(c.value) > 1e-9);
  if (!comps.length && drv.from === drv.to) return null;
  const tr = (k: Key, v?: Vars) => translate(lang, k, v);
  const rowLabel = (c: { id: string; label: string }) => (lang === "pt" ? (DRIVER_ROW_PT[c.id] ?? c.label) : c.label);
  const prevShort = prevMonth ? monthName(prevMonth, "short", lang) : tr("wf.previous");
  const curShort = monthName(s.report_month, "short", lang);
  const steps: Step[] = [
    { label: prevShort, label2: tr("wf.estimate"), value: drv.from, kind: "total" },
    ...comps.map((c) => {
      const [a, b] = DRIVER_LABEL[lang][c.id] ?? [rowLabel(c)];
      return { label: a, label2: b, value: c.value as number, kind: "delta" as const };
    }),
    { label: curShort, label2: tr("wf.estimate"), value: drv.to, kind: "total" },
  ];
  const f = (v: number) => num(v, digits);
  const sgn = (v: number) => `${v >= 0 ? "+" : "−"}${f(Math.abs(v))}`;
  const parts = comps.map((c) => {
    const v = c.value as number;
    const note = (c.id === "domestic_total" || c.id === "exports") && v < 0 ? ` ${tr("wf.moreUse")}` : "";
    return `${rowLabel(c).toLowerCase()} ${sgn(v)}${note}`;
  });
  return {
    steps,
    from: drv.from,
    to: drv.to,
    marketYear: drv.market_year,
    digits,
    aria: tr("wf.aria", {
      my: drv.market_year,
      prev: prevShort,
      from: f(drv.from),
      parts: parts.join("; "),
      cur: curShort,
      to: f(drv.to),
      unit: unitShort(s.unit, lang),
    }),
    rows: [
      [tr("wf.rowEstimate", { m: prevShort }), f(drv.from)],
      ...comps.map((c) => [rowLabel(c), sgn(c.value as number)]),
      [tr("wf.rowEstimate", { m: curShort }), f(drv.to)],
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

export function changeRows(ov: Overview, lang: Lang = "en"): ChangeRow[] {
  const top = Math.max(...ov.highlights.map((h) => h.score), 0) || 1;
  return ov.highlights.map((h) => {
    const d = decimals(h.unit, h.delta);
    const extra: string[] = [];
    if (h.pct_delta !== null) extra.push(`${h.pct_delta > 0 ? "+" : "−"}${num(Math.abs(h.pct_delta * 100), 1)}%`);
    if (h.streak >= 2) {
      extra.push(translate(lang, h.delta > 0 ? "chg.streakUp" : "chg.streakDown", { n: h.streak, nth: ordinal(h.streak) }));
    } else if (h.related[0]) {
      const r = h.related[0];
      const sign = r.delta > 0 ? "+" : "−";
      extra.push(`${attrName(r.attribute, lang, r.label)} ${sign}${num(Math.abs(r.delta), decimals(r.unit, r.delta))} ${unitShort(r.unit, lang)}`.trim());
    }
    return {
      key: `${h.commodity}-${h.region_id}-${h.market_year}-${h.attribute}`,
      commodity: h.commodity,
      what: translate(lang, "chg.what", {
        what: seriesNoun(h.commodity, h.region, h.commodity_label, lang, h.region_id),
        attr: attrName(h.attribute, lang, h.attribute_label),
        my: h.market_year,
      }),
      delta: `${h.delta > 0 ? "+" : h.delta < 0 ? "−" : ""}${num(Math.abs(h.delta), d)} ${unitShort(h.unit, lang)}`.trim(),
      dir: h.delta > 0 ? "up" : h.delta < 0 ? "down" : "flat",
      to: qty(h.value, h.unit, lang),
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
  /** "new": no previous value to compare with (every May, the new marketing year's first projection). */
  dir: "up" | "down" | "flat" | "new";
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
  lang: Lang = "en",
): Kpi | null {
  const col = s.balance_sheet.columns.findIndex((c) => c.market_year === marketYear);
  const row = s.balance_sheet.rows.find((r) => r.id === attr);
  const cell = col >= 0 ? row?.values[col] : undefined;
  if (!row || !cell || cell.value === null) return null;
  const d = decimals(s.unit, cell.value);
  // A missing delta or previous value means a first projection: never report it as "unchanged".
  const isNew = cell.delta === null || cell.delta === undefined || cell.prev === null || cell.prev === undefined;
  const delta = isNew ? 0 : (cell.delta as number);
  const dd = decimals(s.unit, delta); // the change at its published precision (e.g. +0.26 MMT)
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
    unit: unitShort(s.unit, lang),
    dir: isNew ? "new" : delta > 0 ? "up" : delta < 0 ? "down" : "flat",
    deltaAbs: isNew ? "" : num(Math.abs(delta), dd),
    deltaPct:
      !isNew && cell.prev ? `${delta >= 0 ? "+" : "−"}${num(Math.abs((delta / (cell.prev as number)) * 100), 1)}%` : null,
    context,
    contextKind: opts.context === "stu" ? "stu" : "text",
    spark,
    sparkLabel: {
      what: opts.title,
      since: first ? monthYear(first[2], lang) : "",
      from: spark.length ? num(spark[0], d) : "",
      to: spark.length ? num(spark[spark.length - 1], d) : "",
    },
    color: opts.color,
  };
}
