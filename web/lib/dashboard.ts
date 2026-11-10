import "server-only";

import type { Pill, ReleaseInfo } from "@/components/chrome/TopBar";

import { getIndex, getMeta, getOverview, getReportsMeta } from "./data";
import { monthName, monthYear, num, withNumberLang } from "./format";
import { LANGS, type Lang } from "./i18n";
import { changeRows, type ChangeRow } from "./insights";
import type { Meta } from "./types";

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

export type HomeData = {
  month: string; // "October 2026" / "outubro de 2026"
  prevMonth: string; // "September" / "setembro"
  changes: ChangeRow[];
  downloads: ReturnType<typeof downloadLinks>;
  history: {
    first: string;
    reports: string;
    rows: string;
    tag: string | null;
    esrReleases: string | null;
    crushReleases: string | null;
    cpReleases: string | null;
    gsReleases: string | null;
  };
};

/** Every derived string of the home page, in one language. The home is a front door: the
 *  WASDE charts (stocks-to-use, revision paths, waterfall) live on the commodity pages. */
export function homeData(lang: Lang = "en"): HomeData {
  const meta = getMeta();
  const ov = getOverview();
  const reportsMeta = getReportsMeta();
  const esrReleases = reportsMeta.export_sales?.releases ?? null;
  const cpReleases = reportsMeta.crop_progress?.releases ?? null;
  const gsReleases = reportsMeta.grain_stocks?.releases ?? null;
  const crushReleases = reportsMeta.oilseed_crush?.releases ?? null;
  return {
    month: monthYear(meta.latest.report_month, lang),
    prevMonth: monthName(meta.previous_report_month, "long", lang),
    changes: changeRows(ov, lang),
    downloads: downloadLinks(meta),
    history: {
      first: monthYear(meta.history.first_report, lang),
      reports: num(meta.history.reports),
      rows: num(meta.history.rows),
      tag: meta.data_release_tag,
      esrReleases: esrReleases ? num(esrReleases) : null,
      crushReleases: crushReleases ? num(crushReleases) : null,
      cpReleases: cpReleases ? num(cpReleases) : null,
      gsReleases: gsReleases ? num(gsReleases) : null,
    },
  };
}

/** The "Biggest revisions" list of overview.json highlights (shown in full on /reports/wasde/). */
export type RevisionsData = { prevMonth: string; changes: ChangeRow[]; excel: string | null };

export const revisionsAll = (): Record<Lang, RevisionsData> =>
  Object.fromEntries(
    LANGS.map((l) => [
      l,
      withNumberLang(l, () => {
        const meta = getMeta();
        return { prevMonth: monthName(meta.previous_report_month, "long", l), changes: changeRows(getOverview(), l), excel: downloadLinks(meta).excel };
      }),
    ]),
  ) as Record<Lang, RevisionsData>;

/** The home page in every language, so the language toggle never mixes languages. */
export const homeDataAll = (): Record<Lang, HomeData> =>
  Object.fromEntries(LANGS.map((l) => [l, withNumberLang(l, () => homeData(l))])) as Record<Lang, HomeData>;
