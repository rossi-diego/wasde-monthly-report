import type { Key } from "./i18n";

// The v1 report set (plan §3): WASDE and Export Sales since cut A, NASS crush since cut B,
// Crop Progress and Grain Stocks since cut C. Every report is live; a build without a report's
// data shows that page's "not in this build yet" state, never invented numbers.
export type ReportDef = {
  id: "wasde" | "export_sales" | "crush" | "crop_progress" | "grain_stocks";
  /** report_id in the published JSON (the crush page is report "oilseed_crush"). */
  reportId: "wasde" | "export_sales" | "oilseed_crush" | "crop_progress" | "grain_stocks";
  name: Key;
  cadence: Key;
  cadenceDetail: Key;
  color: string; // CSS variable
  live: boolean;
  href?: string; // report page (live reports only)
  insight?: Key;
  arrives?: Key;
};

export const REPORTS: ReportDef[] = [
  { id: "wasde", reportId: "wasde", name: "report.wasde", cadence: "cadence.monthly", cadenceDetail: "cadence.monthly", color: "var(--r-wasde)", live: true, href: "/reports/wasde/" },
  {
    id: "export_sales",
    reportId: "export_sales",
    name: "report.export_sales",
    cadence: "cadence.weekly",
    cadenceDetail: "cadence.d.weeklyThu",
    color: "var(--r-esr)",
    live: true,
    href: "/reports/export-sales/",
  },
  {
    id: "crush",
    reportId: "oilseed_crush",
    name: "report.crush",
    cadence: "cadence.monthly",
    cadenceDetail: "cadence.d.monthlyCrush",
    color: "var(--r-crush)",
    live: true,
    href: "/reports/oilseed-crush/",
  },
  {
    id: "crop_progress",
    reportId: "crop_progress",
    name: "report.crop_progress",
    cadence: "cadence.weekly",
    cadenceDetail: "cadence.d.weeklyMonSeason",
    color: "var(--r-progress)",
    live: true,
    href: "/reports/crop-progress/",
  },
  {
    id: "grain_stocks",
    reportId: "grain_stocks",
    name: "report.grain_stocks",
    cadence: "cadence.quarterly",
    cadenceDetail: "cadence.d.quarterlyGs",
    color: "var(--r-stocks)",
    live: true,
    href: "/reports/grain-stocks/",
  },
];

/** Report colour by published report_id ("cross" sits with Export Sales). */
export const REPORT_COLOR: Record<string, string> = {
  wasde: "var(--r-wasde)",
  export_sales: "var(--r-esr)",
  oilseed_crush: "var(--r-crush)",
  crop_progress: "var(--r-progress)",
  grain_stocks: "var(--r-stocks)",
  cross: "var(--r-esr)",
};

/** Report name key by published report_id. */
export const REPORT_NAME: Record<string, Key> = {
  wasde: "report.wasde",
  export_sales: "report.export_sales",
  oilseed_crush: "report.crush",
  crop_progress: "report.crop_progress",
  grain_stocks: "report.grain_stocks",
};

/** Report page by published report_id. */
export const REPORT_HREF: Record<string, string> = {
  wasde: "/reports/wasde/",
  export_sales: "/reports/export-sales/",
  oilseed_crush: "/reports/oilseed-crush/",
  crop_progress: "/reports/crop-progress/",
  grain_stocks: "/reports/grain-stocks/",
};

/** Commodity pages (/commodities/<slug>/): the commodities that at least three reports cover. */
export const LENSES = [
  { id: "soybeans", label: "Soybeans" },
  { id: "corn", label: "Corn" },
] as const;
