import "server-only";

import type { Pill, ReleaseInfo } from "@/components/chrome/TopBar";

import { getIndex, getMeta, getOverview, getSeries } from "./data";
import { monthName, num, shortDate, unitShort } from "./format";
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
import type { Meta, Series } from "./types";

export function releaseInfo(meta: Meta = getMeta()): ReleaseInfo {
  return {
    number: meta.latest.wasde_number,
    released: shortDate(meta.latest.release_date),
    next: shortDate(meta.next_release, false),
    label: meta.latest.label,
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
  what: string; // "U.S. soybean"
  unitLabel: string;
  stu: StuView;
  rev: RevView | null;
};

export type HomeData = {
  month: string; // "October 2026"
  prevMonth: string; // "September"
  kpis: Kpi[];
  panels: CommodityPanel[];
  defaultCommodity: string;
  waterfall: (WaterfallView & { what: string; unit: string; stuNow: string; stuPrev: string; k: number; n: number }) | null;
  changes: ChangeRow[];
  downloads: ReturnType<typeof downloadLinks>;
  history: { first: string; reports: string; rows: string; tag: string | null };
};

export function homeData(): HomeData {
  const meta = getMeta();
  const ov = getOverview();
  const index = getIndex();
  const prevMonth = monthName(meta.previous_report_month);

  const us: Record<string, Series> = {};
  for (const c of index) {
    const s = trySeries(c.id, "united_states");
    if (s) us[c.id] = s;
  }

  const panels: CommodityPanel[] = index
    .filter((c) => us[c.id])
    .map((c) => ({
      id: c.id,
      label: c.label,
      what: seriesNoun(c.id, us[c.id].region_label, c.label),
      unitLabel: us[c.id].unit_label ?? unitShort(us[c.id].unit),
      stu: stuView(us[c.id]),
      rev: revView(us[c.id]),
    }))
    .filter((p) => p.stu.bars.length > 0);

  // KPI tiles: U.S. soybean and corn ending stocks, Brazil soybean production, world soybean stocks.
  const soyNew = ov.cards.find((c) => c.commodity === "soybeans")?.us?.new?.market_year;
  const cornNew = ov.cards.find((c) => c.commodity === "corn")?.us?.new?.market_year;
  const specs: [string, string, string, string | undefined, string, string, "stu" | "previous_seasons"][] = [
    ["us-soy", "soybeans", "united_states", soyNew, "U.S. soybean ending stocks", "var(--tile-1)", "stu"],
    ["us-corn", "corn", "united_states", cornNew, "U.S. corn ending stocks", "var(--tile-2)", "stu"],
    ["br-soy", "soybeans", "brazil", soyNew, "Brazil soybean production", "var(--tile-3)", "previous_seasons"],
    ["world-soy", "soybeans", "world", soyNew, "World soybean ending stocks", "var(--tile-4)", "stu"],
  ];
  const kpis = specs
    .map(([id, com, reg, my, title, color, context]) => {
      const s = reg === "united_states" ? us[com] : trySeries(com, reg);
      if (!s || !my) return null;
      return kpiFromSeries(s, id === "br-soy" ? "production" : "ending_stocks", my, { id, title, color, context });
    })
    .filter((k): k is Kpi => k !== null);

  // Waterfall of the commodity whose U.S. stocks moved most.
  const wfId = pickWaterfallCommodity(ov);
  const wfCard = ov.cards.find((c) => c.commodity === wfId);
  const wfSeries = wfId ? us[wfId] : undefined;
  let waterfall: HomeData["waterfall"] = null;
  if (wfId && wfCard?.us?.new && wfSeries) {
    const v = waterfallView(wfSeries, wfCard.us.new.market_year, meta.previous_report_month);
    const stu = stuView(wfSeries);
    if (v) {
      waterfall = {
        ...v,
        what: seriesNoun(wfId, wfSeries.region_label, wfCard.label),
        unit: unitShort(wfSeries.unit),
        stuNow: `${num(wfCard.us.new.stocks_to_use_pct, 1)}%`,
        stuPrev: `${num(wfCard.us.new.prev_stocks_to_use_pct, 1)}%`,
        k: stu.k,
        n: stu.n,
      };
    }
  }

  return {
    month: meta.latest.label,
    prevMonth,
    kpis,
    panels,
    defaultCommodity: panels.find((p) => p.id === "soybeans")?.id ?? panels[0]?.id ?? "",
    waterfall,
    changes: changeRows(ov),
    downloads: downloadLinks(meta),
    history: {
      first: `${monthName(meta.history.first_report)} ${meta.history.first_report.slice(0, 4)}`,
      reports: num(meta.history.reports),
      rows: num(meta.history.rows),
      tag: meta.data_release_tag,
    },
  };
}

