import "server-only";

import type { Pill, ReleaseInfo } from "@/components/chrome/TopBar";

import { getIndex, getMeta, getMetaReports, getOverview, getSeries } from "./data";
import { monthName, monthYear, num, unitShort } from "./format";
import { LANGS, translate, type Key, type Lang } from "./i18n";
import {
  changeRows,
  kpiFromSeries,
  pickWaterfallCommodity,
  revView,
  seriesNoun,
  stuView,
  waterfallView,
  type ChangeRow,
  type Kpi,
  type RevView,
  type StuView,
  type WaterfallView,
} from "./insights";
import { commodityName } from "./labels";
import type { Meta, Series } from "./types";

/** Raw dates; the top bar formats them in the reader's language. */
export function releaseInfo(meta: Meta = getMeta()): ReleaseInfo {
  return {
    number: meta.latest.wasde_number,
    releaseDate: meta.latest.release_date,
    nextRelease: meta.next_release,
    reportMonth: meta.latest.report_month,
  };
}

export const commodityPills = (): Pill[] => getIndex().map((c) => ({ id: c.id, label: c.label }));

function trySeries(commodity: string, region: string): Series | null {
  try {
    return getSeries(commodity, region);
  } catch {
    return null; // a missing file drops the tile/chart instead of breaking the build
  }
}

/** Download links by format, looked up by extension (no hard-coded file names). */
export function downloadLinks(meta: Meta = getMeta()) {
  const find = (re: RegExp) => meta.downloads.find((d) => re.test(d.file));
  const href = (d?: Meta["downloads"][number]) => (d ? `/data/${d.url}` : null);
  return {
    excel: href(find(/_latest\.xlsx$/) ?? find(/\.xlsx$/)),
    csv: href(find(/\.csv(\.gz)?$/)),
    parquet: href(find(/\.parquet$/)),
  };
}

export type CommodityPanel = {
  id: string;
  label: string;
  what: string; // "U.S. soybean" / "Soja (EUA)"
  unitLabel: string;
  stu: StuView;
  rev: RevView | null;
};

export type HomeData = {
  month: string; // "October 2026" / "outubro de 2026"
  prevMonth: string; // "September" / "setembro"
  kpis: Kpi[];
  panels: CommodityPanel[];
  defaultCommodity: string;
  waterfall: (WaterfallView & { what: string; unit: string; stuNow: string; stuPrev: string; k: number; n: number }) | null;
  changes: ChangeRow[];
  downloads: ReturnType<typeof downloadLinks>;
  history: {
    first: string;
    reports: string;
    rows: string;
    tag: string | null;
    esrReleases: string | null;
    crushReleases: string | null;
  };
};

/** Every derived string of the home page, in one language. */
export function homeData(lang: Lang = "en"): HomeData {
  const meta = getMeta();
  const ov = getOverview();
  const index = getIndex();
  const prevMonth = monthName(meta.previous_report_month, "long", lang);

  const us: Record<string, Series> = {};
  for (const c of index) {
    const s = trySeries(c.id, "united_states");
    if (s) us[c.id] = s;
  }

  const panels: CommodityPanel[] = index
    .filter((c) => us[c.id])
    .map((c) => ({
      id: c.id,
      label: commodityName(c.id, lang, c.label),
      what: seriesNoun(c.id, us[c.id].region_label, c.label, lang, "united_states"),
      // PT: the short unit (the JSON's long unit label is English).
      unitLabel: lang === "en" ? (us[c.id].unit_label ?? unitShort(us[c.id].unit, lang)) : unitShort(us[c.id].unit, lang),
      stu: stuView(us[c.id], lang),
      rev: revView(us[c.id], "ending_stocks", 5, 17, lang),
    }))
    .filter((p) => p.stu.bars.length > 0);

  // KPI tiles: U.S. soybean and corn ending stocks, Brazil soybean production, world soybean stocks.
  const soyNew = ov.cards.find((c) => c.commodity === "soybeans")?.us?.new?.market_year;
  const cornNew = ov.cards.find((c) => c.commodity === "corn")?.us?.new?.market_year;
  const specs: [
    "us-soy" | "us-corn" | "br-soy" | "world-soy",
    string,
    string,
    string | undefined,
    string,
    "stu" | "previous_seasons",
  ][] = [
    ["us-soy", "soybeans", "united_states", soyNew, "var(--tile-1)", "stu"],
    ["us-corn", "corn", "united_states", cornNew, "var(--tile-2)", "stu"],
    ["br-soy", "soybeans", "brazil", soyNew, "var(--tile-3)", "previous_seasons"],
    ["world-soy", "soybeans", "world", soyNew, "var(--tile-4)", "stu"],
  ];
  const kpis = specs
    .map(([id, com, reg, my, color, context]) => {
      const s = reg === "united_states" ? us[com] : trySeries(com, reg);
      if (!s || !my) return null;
      const title = translate(lang, `kpi.t.${id}` as Key);
      return kpiFromSeries(s, id === "br-soy" ? "production" : "ending_stocks", my, { id, title, color, context }, lang);
    })
    .filter((k): k is Kpi => k !== null);

  // Waterfall of the commodity whose U.S. stocks moved most.
  const wfId = pickWaterfallCommodity(ov);
  const wfCard = ov.cards.find((c) => c.commodity === wfId);
  const wfSeries = wfId ? us[wfId] : undefined;
  let waterfall: HomeData["waterfall"] = null;
  if (wfId && wfCard?.us?.new && wfSeries) {
    const v = waterfallView(wfSeries, wfCard.us.new.market_year, meta.previous_report_month, lang);
    const stu = stuView(wfSeries, lang);
    if (v) {
      waterfall = {
        ...v,
        what: seriesNoun(wfId, wfSeries.region_label, wfCard.label, lang, "united_states"),
        unit: unitShort(wfSeries.unit, lang),
        stuNow: `${num(wfCard.us.new.stocks_to_use_pct, 1)}%`,
        stuPrev: `${num(wfCard.us.new.prev_stocks_to_use_pct, 1)}%`,
        k: stu.k,
        n: stu.n,
      };
    }
  }

  const esrReleases = getMetaReports().export_sales?.releases ?? null;
  const crushReleases = getMetaReports().oilseed_crush?.releases ?? null;
  return {
    month: monthYear(meta.latest.report_month, lang),
    prevMonth,
    kpis,
    panels,
    defaultCommodity: panels.find((p) => p.id === "soybeans")?.id ?? panels[0]?.id ?? "",
    waterfall,
    changes: changeRows(ov, lang),
    downloads: downloadLinks(meta),
    history: {
      first: monthYear(meta.history.first_report, lang),
      reports: num(meta.history.reports),
      rows: num(meta.history.rows),
      tag: meta.data_release_tag,
      esrReleases: esrReleases ? num(esrReleases) : null,
      crushReleases: crushReleases ? num(crushReleases) : null,
    },
  };
}

/** The home page in every language, so the language toggle never mixes languages. */
export const homeDataAll = (): Record<Lang, HomeData> =>
  Object.fromEntries(LANGS.map((l) => [l, homeData(l)])) as Record<Lang, HomeData>;
