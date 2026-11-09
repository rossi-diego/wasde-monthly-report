import type { Key } from "./i18n";

// The v1 report set (plan §3). WASDE and Export Sales have data (cut A), NASS crush since cut
// B; the others are announced placeholders that never show numbers until their stage ships.
export type ReportDef = {
  id: "wasde" | "export_sales" | "crush" | "crop_progress" | "grain_stocks";
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
  { id: "wasde", name: "report.wasde", cadence: "cadence.monthly", cadenceDetail: "cadence.monthly", color: "var(--r-wasde)", live: true, href: "/reports/wasde/" },
  {
    id: "export_sales",
    name: "report.export_sales",
    cadence: "cadence.weekly",
    cadenceDetail: "cadence.d.weeklyThu",
    color: "var(--r-esr)",
    live: true,
    href: "/reports/export-sales/",
  },
  {
    id: "crush",
    name: "report.crush",
    cadence: "cadence.monthly",
    cadenceDetail: "cadence.d.monthlyCrush",
    color: "var(--r-crush)",
    live: true,
    href: "/reports/oilseed-crush/",
  },
  {
    id: "crop_progress",
    name: "report.crop_progress",
    cadence: "cadence.weekly",
    cadenceDetail: "cadence.d.weeklyMon",
    color: "var(--r-progress)",
    live: false,
    insight: "up.progress",
    arrives: "up.cutCseason",
  },
  {
    id: "grain_stocks",
    name: "report.grain_stocks",
    cadence: "cadence.quarterly",
    cadenceDetail: "cadence.quarterly",
    color: "var(--r-stocks)",
    live: false,
    insight: "up.stocks",
    arrives: "up.cutC",
  },
];

export const UPCOMING = REPORTS.filter((r) => !r.live);
