// Pure, client-safe text of the Crop Progress and Grain Stocks pages (header numbers, lead and
// chapter sentences), from the report JSON and the typed insights. The pages render these
// strings and the Playwright contract tests compare them with the JSON (also for a frozen
// off-season fixture), so nothing on those pages is typed in by hand.

import type { CropProgressCrop, GrainStocksCommodity, Insight, InsightsDoc } from "./data-contract";
import { ciText, mbu, monthYear, num, ordinalIn, pctInt, points, share, shortDate, signedMbu, signedShare, tonnes, withNumberLang } from "./format";
import { translate, type Key, type Lang } from "./i18n";
import { byId, cropName, cropTitle, noun, stageName } from "./insight-text";
import { commodityName } from "./labels";

const ok = (i: Insight | undefined) => (i && i.suppressed_reason === null ? i : undefined);
const P = <T = number>(i: Insight, k: string) => i.params[k] as T;
const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const pctMean = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${num(v, 1)}%`);

// ------------------------------------------------------------------------- Crop Progress

export type CropProgressText = {
  closed: boolean;
  stage: CropProgressCrop["stages"][number] | null;
  lead: string;
  sub: string;
  stats: { stage: string; stageLabel: string; stageSub: string; ge: string; geSub: string; ci: string; ciSub: string; next: string; nextSub: string };
  geLine: string | null;
  prevLine: string | null;
  ciLine: string | null;
  stageLine: string | null;
  seasonLine: string;
  dist: string | null;
};

/** The stage C2 reports on (NASS's stage in progress), else the newest stage with a value. */
export function currentStage(d: CropProgressCrop, c2?: Insight) {
  const want = (c2?.params.stage as string | undefined) ?? d.stage_pace.stage;
  return d.stages.find((s) => s.stage === want) ?? [...d.stages].reverse().find((s) => s.value_pct !== null) ?? null;
}

function cropProgressTextImpl(d: CropProgressCrop, doc: InsightsDoc | null, lang: Lang, lastScheduled: string | null): CropProgressText {
  const t = (k: Key, v?: Record<string, string | number>) => translate(lang, k, v);
  const crop = d.crop;
  const closed = d.season_state === "closed";
  const c1 = byId(doc, `C1:${crop}`);
  const c2 = byId(doc, `C2:${crop}`);
  const c3 = byId(doc, `C3:${crop}`);
  const c1ok = ok(c1);
  const c2ok = ok(c2);
  const c3ok = ok(c3);
  const stage = currentStage(d, c2);
  const cond = d.condition;
  const date = (iso: string | null | undefined, y = true) => shortDate(iso, y, lang) ?? "—";

  let lead: string;
  if (closed && c1ok) {
    lead = t("cp.lead.closed", {
      v: pctInt(P(c1ok, "ge_pct")),
      mean: pctMean(P(c1ok, "hist_mean")),
      min: pctInt(P(c1ok, "hist_min")),
      max: pctInt(P(c1ok, "hist_max")),
      n: c1ok.n ?? 0,
    });
  } else if (stage && stage.value_pct !== null) {
    lead = t("cp.lead.stage", {
      crop: cropTitle(crop, lang),
      v: pctInt(stage.value_pct),
      stage: stageName(stage.stage, lang),
      date: date(d.week_ending, false),
      d: points(stage.vs_5yr_avg_pp),
      avg: pctInt(stage.nass_5yr_avg_pct),
    });
  } else if (cond && cond.ge_pct !== null) {
    lead = t("cp.lead.ge", { v: pctInt(cond.ge_pct), date: date(cond.week_ending) });
  } else lead = t("cp.lead.none");

  const sub = closed
    ? t("cp.subClosed", { date: date(d.latest.release_key), next: date(d.next_release) })
    : t("cp.sub", { week: date(d.latest.week_ending), date: date(d.latest.release_key), next: date(d.next_release, false) });

  // Chapter 1: C1 (good/excellent) and C3 (condition index).
  let geLine: string | null = null;
  if (cond && cond.ge_pct !== null) {
    geLine =
      c1ok && P<number | null>(c1ok, "hist_min") !== null && !closed
        ? t("cp.c1.sentence", {
            v: pctInt(cond.ge_pct),
            date: date(cond.week_ending),
            mean: pctMean(P(c1ok, "hist_mean")),
            min: pctInt(P(c1ok, "hist_min")),
            max: pctInt(P(c1ok, "hist_max")),
            n: c1ok.n ?? 0,
          })
        : t("cp.c1.plain", { v: pctInt(cond.ge_pct), date: date(cond.week_ending) });
  }
  const prevLine =
    cond && cond.nass_prev_year_ge_pct !== null && cond.ge_pct !== null
      ? t("cp.c1.prev", { v: pctInt(cond.nass_prev_year_ge_pct), d: points(cond.ge_pct - cond.nass_prev_year_ge_pct) })
      : null;
  let ciLine: string | null = null;
  if (cond && cond.ci !== null) {
    ciLine =
      c3ok && P<number | null>(c3ok, "hist_min") !== null
        ? t("cp.c1.ci", {
            v: ciText(cond.ci),
            mean: ciText(P(c3ok, "hist_mean")),
            min: ciText(P(c3ok, "hist_min")),
            max: ciText(P(c3ok, "hist_max")),
            n: c3ok.n ?? 0,
          })
        : t("cp.c1.ciPlain", { v: ciText(cond.ci) });
  }
  const dist =
    cond && cond.ge_pct !== null
      ? t("cp.c1.dist", {
          vp: pctInt(cond.very_poor_pct),
          p: pctInt(cond.poor_pct),
          f: pctInt(cond.fair_pct),
          g: pctInt(cond.good_pct),
          e: pctInt(cond.excellent_pct),
        })
      : null;

  // Chapter 2: C2 (stage pace vs NASS's published 5-yr average).
  const stageLine = c2ok
    ? t("cp.c2.sentence", {
        v: pctInt(P(c2ok, "value_pct")),
        stage: stageName(P<string>(c2ok, "stage"), lang),
        date: date(P<string>(c2ok, "week_ending")),
        d: points(P<number | null>(c2ok, "pace_vs_5yr_pp")),
        avg: pctInt(P<number | null>(c2ok, "nass_5yr_avg_pct")),
        years: P<string | null>(c2ok, "avg_years") ?? "—",
      })
    : null;

  const seasonLine = closed
    ? t("cp.c3.closed", { season: d.season, last: date(lastScheduled) })
    : t("cp.c3.open", { season: d.season, last: date(lastScheduled) });

  return {
    closed,
    stage,
    lead,
    sub,
    stats: {
      stage: pctInt(stage?.value_pct),
      stageLabel: stage ? t("cp.k.stage", { stage: cap(stageName(stage.stage, lang)), date: date(d.week_ending, false) }) : t("cp.h.stage"),
      stageSub: t("cp.k.stageSub", { avg: pctInt(stage?.nass_5yr_avg_pct), prev: pctInt(stage?.nass_prev_year_pct) }),
      ge: pctInt(cond?.ge_pct),
      geSub: t("cp.k.geSub", { date: date(cond?.week_ending, false), prev: pctInt(cond?.nass_prev_year_ge_pct) }),
      ci: ciText(cond?.ci),
      ciSub: t("cp.k.ciSub", { mean: ciText(cond?.ci_5yr_mean) }),
      next: date(d.next_release),
      nextSub: closed ? t("cp.k.nextSubClosed") : t("cp.k.nextSub"),
    },
    geLine,
    prevLine,
    ciLine,
    stageLine,
    seasonLine,
    dist,
  };
}

export const cropProgressText = (d: CropProgressCrop, doc: InsightsDoc | null, lang: Lang, lastScheduled: string | null = null) =>
  withNumberLang(lang, () => cropProgressTextImpl(d, doc, lang, lastScheduled));

/** Final good/excellent ratings (closed season): the 5 prior seasons of C1 plus this one. */
export function finalRatings(c1: Insight | undefined): { season: number; ge: number; current: boolean }[] {
  if (!c1 || c1.suppressed_reason !== null || c1.params.season_state !== "closed") return [];
  const hist = (c1.params.history as { season: number; ge_pct: number }[]) ?? [];
  return [...hist.map((h) => ({ season: h.season, ge: h.ge_pct, current: false })), { season: c1.params.season as number, ge: c1.params.ge_pct as number, current: true }];
}

export { cropName };

// --------------------------------------------------------------------------- Grain Stocks

export type GrainStocksText = {
  /** Lower-case commodity noun for chart labels ("corn" / "milho"). */
  what: string;
  lead: string;
  sub: string;
  stats: { total: string; totalLabel: string; totalSub: string; farm: string; farmSub: string; yoy: string; next: string };
  g1Line: string | null;
  g1Pctl: string | null;
  g2Line: string | null;
  g3Line: string | null;
};

function grainStocksTextImpl(d: GrainStocksCommodity, doc: InsightsDoc | null, lang: Lang): GrainStocksText {
  const t = (k: Key, v?: Record<string, string | number>) => translate(lang, k, v);
  const c = d.commodity_id;
  const what = lang === "pt" ? commodityName(c, "pt", d.label).toLowerCase() : noun(c, "en");
  const whatT = lang === "pt" ? commodityName(c, "pt", d.label) : cap(noun(c, "en"));
  const g1 = ok(byId(doc, `G1:${c}`));
  const g2 = ok(byId(doc, `G2:${c}`));
  const g3 = ok(byId(doc, `G3:${c}`));
  const k = d.kpis;
  const date = (iso: string | null | undefined, y = true) => shortDate(iso, y, lang) ?? "—";

  const g1Vars = g1
    ? {
        date: date(P<string>(g1, "as_of_date")),
        nass: mbu(P(g1, "nass_total_mbu")),
        v: signedMbu(P(g1, "surprise_mbu")),
        dir: t(`dir.${P<string>(g1, "direction")}` as Key),
        pct: signedShare(P(g1, "surprise_pct")),
        nth: ordinalIn(P<number>(g1, "k"), lang),
        n: g1.n ?? 0,
        first: P<string | null>(g1, "first_market_year") ?? "—",
        last: P<string>(g1, "market_year"),
        month: monthYear(P<string | null>(g1, "wasde_release_key"), lang),
        wasde: mbu(P(g1, "wasde_ending_stocks_mbu")),
      }
    : null;

  const lead =
    g1 && g1Vars && P<boolean>(g1, "is_latest_release")
      ? t("gs.lead.g1", { what: whatT, ...g1Vars })
      : t("gs.lead.plain", { what: whatT, date: date(d.latest.as_of_date), total: mbu(k.total_mbu), yoy: signedShare(k.total_yoy_pct) });

  const g1Line = g1Vars ? t("gs.c1.sentence", g1Vars) : null;
  const pctl = g1 ? P<number | null>(g1, "percentile_larger_than") : null;
  const g1Pctl = pctl !== null && pctl !== undefined ? t("gs.c1.pctl", { p: num(pctl, 0) }) : null;

  const g2Line = g2
    ? t("gs.c2.sentence", {
        from: date(P<string | null>(g2, "prev_as_of_date"), false),
        to: date(P<string>(g2, "as_of_date"), false),
        v: mbu(P(g2, "implied_disappearance_mbu")),
        formula: `${mbu(P(g2, "prev_stocks_mbu"))} + ${mbu(P(g2, "production_mbu"))} − ${mbu(P(g2, "stocks_mbu"))}`,
        mean: mbu(P(g2, "hist_mean")),
        min: num(P(g2, "hist_min"), 0),
        max: mbu(P(g2, "hist_max")),
        n: g2.n ?? 0,
      })
    : null;

  const g3Line = g3
    ? t("gs.c3.sentence", {
        v: share(P(g3, "on_farm_share")),
        date: date(P<string>(g3, "as_of_date")),
        mean: share(P(g3, "hist_mean")),
        min: share(P(g3, "hist_min")),
        max: share(P(g3, "hist_max")),
        n: g3.n ?? 0,
        yoy: signedShare(P<number | null>(g3, "total_yoy_pct")),
      })
    : null;

  return {
    lead,
    sub: t("gs.sub", { date: date(d.latest.as_of_date), rel: date(d.latest.release_key), next: date(d.next_release, false) }),
    stats: {
      total: mbu(k.total_mbu),
      totalLabel: t("gs.k.total", { date: date(d.latest.as_of_date, false) }),
      totalSub: t("gs.k.totalSub", { mt: tonnes(k.total_mt, lang) }),
      farm: share(k.on_farm_share),
      farmSub: t("gs.k.farmSub", { on: mbu(k.on_farm_mbu), off: mbu(k.off_farm_mbu) }),
      yoy: signedShare(k.total_yoy_pct),
      next: date(d.next_release),
    },
    g1Line,
    g1Pctl,
    g2Line,
    g3Line,

    what,
  };
}

export const grainStocksText = (d: GrainStocksCommodity, doc: InsightsDoc | null, lang: Lang) =>
  withNumberLang(lang, () => grainStocksTextImpl(d, doc, lang));
