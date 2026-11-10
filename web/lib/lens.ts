// Pure, client-safe view of lens/<commodity>.json (one commodity, every report) and the home
// picks for reports that have no card in insights.json `home_cards`. Every number is the
// JSON's; the Playwright contract test calls these same functions.

import type { CommodityLens, Insight, InsightsDoc, LensMetric } from "./data-contract";
import { bushels, ciText, mbu, monthYear, pctInt, share, shortDate, signedMbu, tonnes, withNumberLang } from "./format";
import { translate, type Key, type Lang } from "./i18n";
import { cardView, finding, stageName } from "./insight-text";

export type LensRow = {
  metric: string;
  label: string;
  value: string;
  period: string;
  href: string;
};

export type LensBlock = {
  reportId: CommodityLens["reports"][number]["report_id"];
  released: string | null;
  next: string | null;
  href: string;
  dataHref: string;
  rows: LensRow[];
};

const NAMED = new Set([
  "production",
  "exports",
  "ending_stocks",
  "crush",
  "total_commitment",
  "pct_of_usda_target",
  "month_crushed",
  "good_excellent_pct",
  "condition_index",
  "total_stocks",
  "on_farm_share",
  "ending_stocks_vs_usda",
]);

/** Metric label: "Ending stocks", "Share harvested" … */
export function metricLabel(m: string, lang: Lang): string {
  if (NAMED.has(m)) return translate(lang, `lens.m.${m}` as Key);
  if (m.endsWith("_pct")) {
    const s = translate(lang, "lens.m.stage", { stage: stageName(m.slice(0, -4), lang) });
    return s[0].toUpperCase() + s.slice(1);
  }
  return m.replace(/_/g, " ");
}

/** The metric's value in USDA's own unit. */
export function metricValue(m: LensMetric, lang: Lang): string {
  const v = m.value;
  if (m.metric === "ending_stocks_vs_usda") return signedMbu(v);
  switch (m.unit_id) {
    case "m_bu":
      return mbu(v);
    case "k_bu":
      return v === null ? "—" : mbu(v / 1000, Math.abs(v) < 1e6 ? 1 : 0);
    case "mt":
      return tonnes(v, lang);
    case "bu":
      return bushels(v, lang);
    case "pct":
      return pctInt(v);
    case "share":
      return share(v);
    case "index_1_5":
      return ciText(v);
    default:
      return v === null ? "—" : String(v);
  }
}

function period(reportId: string, m: LensMetric, lang: Lang): string {
  if (reportId === "wasde") return translate(lang, "lens.p.my", { my: m.period ?? "—" });
  if (reportId === "oilseed_crush") return translate(lang, "lens.p.month", { month: monthYear((m.period_date ?? m.period ?? "").slice(0, 7), lang) });
  if (reportId === "grain_stocks")
    return translate(lang, "lens.p.stock", { date: shortDate(m.period_date ?? m.period, true, lang) ?? "—", my: m.market_year ?? "—" });
  return translate(lang, "lens.p.week", { date: shortDate(m.period_date ?? m.period, true, lang) ?? "—" });
}

/** The report chapter a metric comes from. */
export function metricHref(reportId: string, metric: string, commodity: string): string {
  switch (reportId) {
    case "wasde":
      return `/commodity/${commodity}/`;
    case "export_sales":
      return `/reports/export-sales/?c=${commodity}`;
    case "oilseed_crush":
      return "/reports/oilseed-crush/";
    case "crop_progress":
      return `/reports/crop-progress/?c=${commodity}#ch-${metric === "good_excellent_pct" || metric === "condition_index" ? 1 : 2}`;
    case "grain_stocks":
      return `/reports/grain-stocks/?c=${commodity}${metric === "ending_stocks_vs_usda" ? "#ch-1" : metric === "on_farm_share" ? "#ch-3" : ""}`;
    default:
      return "/reports/";
  }
}

const REPORT_ORDER = ["wasde", "export_sales", "oilseed_crush", "crop_progress", "grain_stocks"];
const METRIC_ORDER = [
  "ending_stocks",
  "production",
  "exports",
  "crush",
  "pct_of_usda_target",
  "total_commitment",
  "month_crushed",
  "good_excellent_pct",
  "condition_index",
  "total_stocks",
  "ending_stocks_vs_usda",
  "on_farm_share",
];
const rank = (m: string) => {
  const i = METRIC_ORDER.indexOf(m);
  return i === -1 ? METRIC_ORDER.indexOf("good_excellent_pct") + 0.5 : i; // stages sit before the rating
};

function lensBlocksImpl(lens: CommodityLens, lang: Lang): LensBlock[] {
  return [...lens.reports]
    .sort((a, b) => REPORT_ORDER.indexOf(a.report_id) - REPORT_ORDER.indexOf(b.report_id))
    .map((r) => ({
      reportId: r.report_id,
      released: shortDate(r.report_id === "wasde" ? r.release_ts_utc : r.release_key, true, lang),
      next: shortDate(r.next_release, true, lang),
      href: metricHref(r.report_id, "", lens.commodity_id).split("#")[0],
      dataHref: `/data/#report-${r.report_id}`,
      rows: [...r.metrics]
        .sort((a, b) => rank(a.metric) - rank(b.metric))
        .map((m) => ({
          metric: m.metric,
          label: metricLabel(m.metric, lang),
          value: metricValue(m, lang),
          period: period(r.report_id, m, lang),
          href: metricHref(r.report_id, m.metric, lens.commodity_id),
        })),
    }));
}

export const lensBlocks = (lens: CommodityLens, lang: Lang): LensBlock[] => withNumberLang(lang, () => lensBlocksImpl(lens, lang));

/** The headline metric of each report for the home teaser (one per report, in report order). */
const HEADLINE: Record<string, string[]> = {
  wasde: ["ending_stocks"],
  export_sales: ["pct_of_usda_target", "total_commitment"],
  oilseed_crush: ["pct_of_usda_target", "month_crushed"],
  crop_progress: ["good_excellent_pct", "harvested_pct", "condition_index"],
  grain_stocks: ["total_stocks", "on_farm_share"],
};

export function lensHeadlines(lens: CommodityLens, lang: Lang): (LensRow & { reportId: string })[] {
  return lensBlocks(lens, lang).flatMap((b) => {
    const pick = (HEADLINE[b.reportId] ?? []).map((m) => b.rows.find((r) => r.metric === m)).find(Boolean) ?? b.rows[0];
    return pick ? [{ ...pick, reportId: b.reportId }] : [];
  });
}

/** One passing insight per report among the lens's insight ids (first in the lens's order). */
export function lensFindings(lens: CommodityLens, doc: InsightsDoc | null): Insight[] {
  const seen = new Set<string>();
  const out: Insight[] = [];
  for (const id of lens.insight_ids) {
    const i = finding(doc, id);
    if (!i || seen.has(i.report_id)) continue;
    seen.add(i.report_id);
    out.push(i);
  }
  return out;
}

// ----------------------------------------------------------------- home: "also released"

const passing = (doc: InsightsDoc, rule: string) => doc.insights.filter((i) => i.rule === rule && i.suppressed_reason === null);
const num0 = (v: unknown) => (typeof v === "number" ? v : 0);

/** Headline insight of Crop Progress / Grain Stocks for the home page when `home_cards` holds
 *  none of that report (the row is capped at 5). Crop Progress follows the season gate of
 *  insights.json (`seasons.crop_progress.shown_on_home`: hidden December–March). */
export function alsoReleased(doc: InsightsDoc): Insight[] {
  const onHome = new Set(doc.home_cards.map((id) => doc.insights.find((i) => i.id === id)?.report_id));
  const out: Insight[] = [];
  const cpShown = doc.seasons?.crop_progress?.shown_on_home ?? true;
  if (!onHome.has("crop_progress") && cpShown) {
    const closed = doc.seasons?.crop_progress?.state === "closed";
    const c2 = passing(doc, "C2").sort((a, b) => Math.abs(num0(b.params.pace_vs_5yr_pp)) - Math.abs(num0(a.params.pace_vs_5yr_pp)));
    const pick = closed ? passing(doc, "C1")[0] : (c2[0] ?? passing(doc, "C1")[0] ?? passing(doc, "C3")[0]);
    if (pick) out.push(pick);
  }
  if (!onHome.has("grain_stocks")) {
    // The finding about the newest release: G1 only when that release is an ending-stocks date.
    const latest = (rule: string) => passing(doc, rule).filter((i) => i.params.is_latest_release);
    const g1 = latest("G1").sort((a, b) => num0(a.params.k) - num0(b.params.k));
    const pick = g1[0] ?? latest("G2")[0] ?? latest("G3")[0];
    if (pick) out.push(pick);
  }
  return out;
}

// ------------------------------------------------------------------ home: front door

/** The hero's evidence card: the insight behind the hero's first clause, else the cross card
 *  of `home_cards`, else none. Only passing insights that render as a card. */
export function heroEvidence(doc: InsightsDoc | null): Insight | null {
  if (!doc) return null;
  const renders = (i: Insight | undefined): i is Insight => Boolean(i) && cardView(i!, "en") !== null;
  const first = finding(doc, doc.hero?.clauses?.[0]?.insight_ids?.[0] ?? "");
  if (renders(first)) return first;
  const cross = doc.home_cards.map((id) => finding(doc, id)).find((i) => i?.report_id === "cross");
  return renders(cross) ? cross : null;
}

export type HomeTile = { insight: Insight; origin: "home" | "also" };

/** One tile per report on the home page, in report order: `home_cards` minus the hero evidence
 *  and the cross card, then the "also released" picks; the first finding of a report wins. */
export function homeTiles(doc: InsightsDoc | null): HomeTile[] {
  if (!doc) return [];
  const evidence = heroEvidence(doc);
  const candidates: HomeTile[] = [
    ...doc.home_cards
      .map((id) => finding(doc, id))
      .filter((i): i is Insight => Boolean(i) && i!.id !== evidence?.id && i!.report_id !== "cross")
      .map((insight) => ({ insight, origin: "home" as const })),
    ...alsoReleased(doc).map((insight) => ({ insight, origin: "also" as const })),
  ];
  const seen = new Set<string>();
  const out: HomeTile[] = [];
  for (const t of candidates) {
    if (seen.has(t.insight.report_id) || cardView(t.insight, "en") === null) continue;
    seen.add(t.insight.report_id);
    out.push(t);
  }
  return out.sort((a, b) => REPORT_ORDER.indexOf(a.insight.report_id) - REPORT_ORDER.indexOf(b.insight.report_id));
}

/** The overview.json change key ("corn-united_states-2026/27-ending_stocks", as ChangeRow.key) that
 *  a WASDE revision finding (W1/W3 on a U.S. table) already shows, so the home "What changed in
 *  WASDE" list can skip that row instead of printing the same number twice. Null otherwise. */
export function changeKeyOf(i: Insight | null | undefined): string | null {
  if (!i || i.report_id !== "wasde" || (i.rule !== "W1" && i.rule !== "W3")) return null;
  const { table_id: table, attribute_id: attr, market_year: my } = i.params;
  if (typeof table !== "string" || !table.startsWith("us_") || typeof attr !== "string" || typeof my !== "string") return null;
  return `${i.commodity_id}-united_states-${my}-${attr}`;
}

/** The home tiles' and hero evidence's change keys (see changeKeyOf). */
export function shownChangeKeys(doc: InsightsDoc | null): Set<string> {
  if (!doc) return new Set();
  const keys = [heroEvidence(doc), ...homeTiles(doc).map((x) => x.insight)].map(changeKeyOf);
  return new Set(keys.filter((k): k is string => k !== null));
}
