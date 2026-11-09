// Renders the typed insights of insights.json (structured params, no prose) as words, in EN
// or PT. Client-safe and pure: the Playwright contract test imports these same functions and
// checks that the page shows exactly what the JSON says. Rules (docs/DATA_CONTRACT.md):
// suppressed insights are never findings; n is always shown; "percentile" only from the
// JSON (never computed here); 5-yr windows are labelled small sample.

import type { Caveat, Hero, HeroClause, Insight, InsightsDoc, SuppressedReason } from "./data-contract";
import { bushels, decimals, lbPerBu, monthOf, monthYear, num, ordinalIn, share, shortDate, signed, signedQty, tonnes, unitShort } from "./format";
import { translate, type Key, type Lang } from "./i18n";
import { attrName, commodityName, commodityNounPt, regionName } from "./labels";

const NOUN_EN: Record<string, string> = {
  soybeans: "soybean",
  soybean_meal: "soybean meal",
  soybean_oil: "soybean oil",
};

/** Lower-case commodity noun: "soybean" / "soja". */
export function noun(id: string | null | undefined, lang: Lang): string {
  if (!id) return "";
  if (lang === "pt") return commodityNounPt(id) ?? id.replace(/_/g, " ");
  return NOUN_EN[id] ?? id.replace(/_/g, " ");
}

/** "+282" / "−5" with the unit's precision (the unit is printed next to it). */
const signedNum = (v: number, unit: string) => (v === 0 ? "0" : signed(v, decimals(unit, v)));

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export const byId = (doc: InsightsDoc | null, id: string): Insight | undefined => doc?.insights.find((i) => i.id === id);

/** Passing (not suppressed) insight, or undefined. */
export function finding(doc: InsightsDoc | null, id: string): Insight | undefined {
  const i = byId(doc, id);
  return i && i.suppressed_reason === null ? i : undefined;
}

export const isSmall = (i: Insight) => i.caveats.includes("small_sample");

export const caveatText = (c: Caveat, lang: Lang) => translate(lang, `caveat.${c}` as Key);
export const suppressedText = (r: SuppressedReason, lang: Lang) => translate(lang, `supp.${r}` as Key);

/** "ESR Nov 5, 2026 · WASDE October 2026" from an insight's inputs. */
export function sourceText(i: Insight, lang: Lang): string {
  return i.inputs
    .map((r) =>
      r.report_id === "wasde"
        ? translate(lang, "card.src.wasde", { month: monthYear(r.release_key, lang) })
        : translate(lang, r.report_id === "oilseed_crush" ? "card.src.oilseed_crush" : "card.src.export_sales", {
            date: shortDate(r.release_key, true, lang) ?? r.release_key,
          }),
    )
    .join(" · ");
}

// ------------------------------------------------------------------------------- hero

export function heroClauseText(c: HeroClause, lang: Lang): string {
  const what = noun(c.commodity_id, lang);
  return translate(lang, `hero.${c.direction}` as Key, { c: what });
}

export type HeroView = { kind: Hero["kind"]; text: string; clauses: string[]; sub: string | null };

export function heroView(h: Hero, lang: Lang): HeroView {
  const since = shortDate(h.since, true, lang) ?? "—";
  if (h.kind === "fallback" || h.clauses.length === 0) {
    return { kind: "fallback", text: translate(lang, h.n_reports === 1 ? "hero.fallback1" : "hero.fallback", { n: h.n_reports, date: since }), clauses: [], sub: null };
  }
  const clauses = h.clauses.map((c) => heroClauseText(c, lang));
  const joined =
    clauses.length === 1
      ? clauses[0]
      : `${clauses.slice(0, -1).join(", ")}${translate(lang, "hero.and")}${clauses[clauses.length - 1]}`;
  return {
    kind: "story",
    text: translate(lang, "hero.story", { clauses: joined }),
    clauses,
    sub: translate(lang, "hero.sub", { n: h.n_reports, date: since }),
  };
}

// ------------------------------------------------------------------------------- cards

export type CardView = {
  id: string;
  report: Insight["report_id"];
  color: string; // CSS variable of the report colour
  eyebrow: string;
  title: string;
  /** The headline number and which param it renders (checked by the contract test). */
  value: string;
  valueParam: string;
  valueNote: string | null;
  context: string[];
  chip: string | null;
  range: { lo: number; hi: number; mean: number | null; value: number } | null;
  /** How the range strip labels its ends: shares (0.38 → 38%) or pounds per bushel. */
  rangeUnit: "share" | "lb_per_bu";
  n: number | null;
  small: boolean;
  caveats: string[];
  source: string;
  href: string;
};

const COLOR = { wasde: "var(--r-wasde)", export_sales: "var(--r-esr)", oilseed_crush: "var(--r-crush)", cross: "var(--r-esr)" } as const;

/** "Crush (NASS) · September 2026": the data month of a crush insight. */
function crushEyebrow(i: Insight, lang: Lang) {
  return translate(lang, "card.eb.crush", { month: monthYear(p<string>(i, "month").slice(0, 7), lang) });
}

/** Range text of a 5-yr window of oil yields (lb/bu). */
function yieldRangeVars(i: Insight) {
  return { mean: lbPerBu(p(i, "hist_mean")), min: lbPerBu(p(i, "hist_min")), max: lbPerBu(p(i, "hist_max")) };
}

const p = <T = number>(i: Insight, k: string) => i.params[k] as T;

function esrWeekEyebrow(i: Insight, lang: Lang) {
  return translate(lang, "card.eb.export_sales", { date: shortDate(p<string>(i, "week_ending"), true, lang) ?? "" });
}

/** Range text "51.6% (range 37.5–57.9%)" of a 5-yr window. */
function rangeVars(i: Insight) {
  return { mean: share(p(i, "hist_mean")), min: share(p(i, "hist_min")), max: share(p(i, "hist_max")) };
}

export function cardView(i: Insight, lang: Lang): CardView | null {
  const c = i.commodity_id ?? "";
  const us = (lang === "pt" ? `${commodityName(c, "pt", c)} (EUA)` : `U.S. ${noun(c, "en")}`) as string;
  const release = i.inputs.find((r) => r.report_id === "wasde")?.release_key ?? "";
  const base = {
    id: i.id,
    report: i.report_id,
    color: COLOR[i.report_id],
    n: i.n,
    small: isSmall(i),
    caveats: i.caveats.filter((x) => x !== "small_sample").map((x) => caveatText(x, lang)),
    source: sourceText(i, lang),
    valueNote: null as string | null,
    chip: null as string | null,
    range: null as CardView["range"],
    rangeUnit: "share" as CardView["rangeUnit"],
  };
  const wasdeEyebrow = translate(lang, "card.eb.wasde", { month: monthYear(release, lang) });
  switch (i.rule) {
    case "W2": {
      const ctx = [
        translate(lang, "card.w2.rank", {
          nth: ordinalIn(p(i, "k"), lang),
          n: i.n ?? 0,
          first: p<string>(i, "first_market_year"),
          last: p<string>(i, "market_year"),
        }),
      ];
      const pct = p<number | null>(i, "percentile_tighter_than");
      if (pct !== null && pct !== undefined) ctx.push(translate(lang, "card.w2.pctl", { p: num(pct, 0) }));
      return {
        ...base,
        eyebrow: wasdeEyebrow,
        title: translate(lang, "card.w2.title", { what: us, my: p<string>(i, "market_year") }),
        value: `${num(p(i, "stocks_to_use_pct"), 1)}%`,
        valueParam: "stocks_to_use_pct",
        context: ctx,
        chip: translate(lang, `tercile.${p<string>(i, "tercile")}` as Key),
        href: `/commodity/${c}/`,
      };
    }
    case "W3": {
      const month = monthOf(((p<number>(i, "cycle_month") + 4) % 12) + 1, "long", lang);
      return {
        ...base,
        eyebrow: wasdeEyebrow,
        title: translate(lang, "card.w3.title", { what: us, month, my: p<string>(i, "market_year") }),
        value: signedNum(p(i, "delta"), p<string>(i, "unit_id")),
        valueParam: "delta",
        valueNote: unitShort(p<string>(i, "unit_id"), lang),
        context: [translate(lang, "card.w3.rank", { nth: ordinalIn(p(i, "k"), lang), n: i.n ?? 0 })],
        href: `/commodity/${c}/`,
      };
    }
    case "W4": {
      const countries = (p<string[]>(i, "countries") ?? []).map((x) => regionName(x, lang, x.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase())));
      return {
        ...base,
        eyebrow: wasdeEyebrow,
        title: translate(lang, "wasde.w4.title", { my: p<string>(i, "market_year") }),
        value: share(p(i, "share")),
        valueParam: "share",
        valueNote: translate(lang, "wasde.w4.of", { countries: countries.join(", ") }),
        context: [translate(lang, "wasde.w4.rank", { nth: ordinalIn(p(i, "k"), lang), n: i.n ?? 0 })],
        href: "/commodity/soybeans/",
      };
    }
    case "E1": {
      if (p(i, "pct") === null) return null;
      const lo = p<number>(i, "hist_min");
      const hi = p<number>(i, "hist_max");
      return {
        ...base,
        eyebrow: translate(lang, "card.eb.cross"),
        title: translate(lang, "card.e1.title", { what: us }),
        value: share(p(i, "pct")),
        valueParam: "pct",
        valueNote: translate(lang, "card.e1.of", {
          my: p<string>(i, "market_year"),
          month: monthYear(p<string>(i, "wasde_release_key"), lang),
        }),
        context: [translate(lang, "card.e1.range", { w: p(i, "week_of_my"), ...rangeVars(i) })],
        chip: p<string | null>(i, "position") ? translate(lang, `pos.${p<string>(i, "position")}` as Key) : null,
        range: lo !== null && hi !== null ? { lo, hi, mean: p(i, "hist_mean"), value: p(i, "pct") } : null,
        href: `/reports/export-sales/?c=${c}`,
      };
    }
    case "E2": {
      const wk = translate(lang, "unit.perWeek");
      return {
        ...base,
        eyebrow: esrWeekEyebrow(i, lang),
        title: translate(lang, "card.e2.title", { what: us }),
        value: `${tonnes(p(i, "required_weekly_mt"), lang)}${wk}`,
        valueParam: "required_weekly_mt",
        context: [
          translate(lang, "card.e2.avg", {
            avg: `${tonnes(p(i, "net_sales_4wk_avg_mt"), lang)}${wk}`,
            weeks: p(i, "weeks_remaining"),
          }),
        ],
        href: `/reports/export-sales/?c=${c}`,
      };
    }
    case "E3": {
      const lo = p<number | null>(i, "hist_min");
      const hi = p<number | null>(i, "hist_max");
      return {
        ...base,
        eyebrow: esrWeekEyebrow(i, lang),
        title: translate(lang, "card.e3.title", { what: noun(c, lang) }),
        value: share(p(i, "china_share")),
        valueParam: "china_share",
        valueNote: translate(lang, "card.e3.unknown", { u: share(p(i, "unknown_share")) }),
        context: lo !== null && hi !== null ? [translate(lang, "card.e3.range", { ...rangeVars(i) })] : [],
        chip: p<string | null>(i, "position") ? translate(lang, `pos.${p<string>(i, "position")}` as Key) : null,
        range: lo !== null && hi !== null ? { lo, hi, mean: p(i, "hist_mean"), value: p(i, "china_share") } : null,
        href: `/reports/export-sales/?c=${c}`,
      };
    }
    case "F1": {
      if (p(i, "pct") === null) return null;
      const lo = p<number | null>(i, "hist_min");
      const hi = p<number | null>(i, "hist_max");
      const month = monthOf(Number(p<string>(i, "month").slice(5, 7)), "long", lang);
      return {
        ...base,
        eyebrow: crushEyebrow(i, lang),
        title: translate(lang, "card.f1.title", { what: us, my: p<string>(i, "market_year") }),
        value: share(p(i, "pct")),
        valueParam: "pct",
        valueNote: translate(lang, "card.f1.of", {
          my: p<string>(i, "market_year"),
          month: monthYear(p<string>(i, "wasde_release_key"), lang),
        }),
        context:
          lo !== null && hi !== null
            ? [translate(lang, "card.f1.range", { month, ...rangeVars(i) })]
            : [],
        chip: p<string | null>(i, "position") ? translate(lang, `pos.${p<string>(i, "position")}` as Key) : null,
        range: lo !== null && hi !== null ? { lo, hi, mean: p(i, "hist_mean"), value: p(i, "pct") } : null,
        href: "/reports/oilseed-crush/",
      };
    }
    case "F2": {
      const mo = translate(lang, "unit.perMonth");
      return {
        ...base,
        eyebrow: crushEyebrow(i, lang),
        title: translate(lang, "card.f2.title", { what: us }),
        value: `${bushels(p(i, "required_monthly_bu"), lang)}${mo}`,
        valueParam: "required_monthly_bu",
        context: [
          translate(lang, "card.f2.last", {
            avg: `${bushels(p(i, "last_my_remaining_mean_bu"), lang)}${mo}`,
            months: p(i, "months_remaining"),
          }),
        ],
        href: "/reports/oilseed-crush/",
      };
    }
    case "F3": {
      const lo = p<number | null>(i, "hist_min");
      const hi = p<number | null>(i, "hist_max");
      const month = monthOf(Number(p<string>(i, "month").slice(5, 7)), "long", lang);
      const implied = p<number | null>(i, "wasde_implied_yield_lb_bu");
      const ctx = lo !== null && hi !== null ? [translate(lang, "card.f3.range", { month, ...yieldRangeVars(i) })] : [];
      if (implied !== null && implied !== undefined) {
        ctx.push(translate(lang, "card.f3.wasde", { v: lbPerBu(implied), month: monthYear(p<string>(i, "wasde_oil_release_key"), lang) }));
      }
      return {
        ...base,
        eyebrow: crushEyebrow(i, lang),
        title: translate(lang, "card.f3.title", { month: monthYear(p<string>(i, "month").slice(0, 7), lang) }),
        value: lbPerBu(p(i, "oil_yield_lb_bu")),
        valueParam: "oil_yield_lb_bu",
        valueNote: translate(lang, "card.f3.note"),
        context: ctx,
        chip: p<string | null>(i, "position") ? translate(lang, `pos.${p<string>(i, "position")}` as Key) : null,
        range: lo !== null && hi !== null ? { lo, hi, mean: p(i, "hist_mean"), value: p(i, "oil_yield_lb_bu") } : null,
        rangeUnit: "lb_per_bu",
        href: "/reports/oilseed-crush/",
      };
    }
    default:
      return null;
  }
}

/** The formatted text of one param, as the cards print it (for the contract test). */
export function formatParam(i: Insight, param: string, lang: Lang = "en"): string {
  const v = i.params[param] as number;
  if (param === "stocks_to_use_pct") return `${num(v, 1)}%`;
  if (param === "delta") return signedNum(v, i.params.unit_id as string);
  if (param.endsWith("_mt")) return `${tonnes(v, lang)}${translate(lang, "unit.perWeek")}`;
  if (param === "required_monthly_bu") return `${bushels(v, lang)}${translate(lang, "unit.perMonth")}`;
  if (param === "oil_yield_lb_bu") return lbPerBu(v);
  return share(v);
}

// --------------------------------------------------------------------------- W1 rows

export type ChangeView = { id: string; what: string; value: string; delta: string; pct: string; score: string; headline: boolean };

export function changeView(i: Insight, lang: Lang): ChangeView {
  const c = i.commodity_id ?? "";
  const us = lang === "pt" ? `${commodityName(c, "pt", c)} (EUA)` : `U.S. ${noun(c, "en")}`;
  const aid = p<string>(i, "attribute_id");
  const attr = attrName(aid, lang, aid.replace(/_/g, " "));
  const unit = p<string>(i, "unit_id");
  return {
    id: i.id,
    what: translate(lang, "wasde.w1.what", { what: us, attr, my: p<string>(i, "market_year") }),
    value: `${num(p(i, "value"), 0)} ${unitShort(unit, lang)}`,
    delta: signedQty(p(i, "delta"), unit, lang),
    pct: p<number | null>(i, "pct_delta") === null ? "" : `${p<number>(i, "pct_delta") >= 0 ? "+" : "−"}${share(Math.abs(p(i, "pct_delta")))}`,
    score: translate(lang, "wasde.w1.score", {
      x: num(p(i, "seasonal_score"), 1),
      med: num(p(i, "median_abs_delta"), 0),
      n: i.n ?? 0,
    }),
    headline: Boolean(i.params.headline),
  };
}

export { cap };
