import type { Metadata } from "next";
import Link from "next/link";

import { DateText, MonthYear, T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import { EsrLatestText, FreshnessChip, StaleBanner } from "@/components/Freshness";
import Upcoming from "@/components/home/Upcoming";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getEsrIndex, getInsights, getMeta, getMetaReports } from "@/lib/data";
import { num } from "@/lib/format";

export const metadata: Metadata = { title: "Reports · USDA Reports Dashboard" };

// Cadence + grace when insights.json (gates.stale_after_days) is not in the build.
const DEFAULT_STALE: Record<string, number> = { wasde: 76, export_sales: 17 };

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 border-t border-line py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="m-0 text-right font-semibold">{children}</dd>
    </div>
  );
}

function LiveChip() {
  return (
    <span className="rounded-full px-3 py-1 text-xs font-semibold text-white" style={{ background: "var(--pill-active)" }}>
      <T k="reports.live" />
    </span>
  );
}

export default function ReportsPage() {
  const meta = getMeta();
  const reports = getMetaReports();
  const esr = getEsrIndex();
  const stale = { ...DEFAULT_STALE, ...(getInsights()?.gates.stale_after_days ?? {}) };
  const wasdeTs = reports.wasde?.release_ts_utc ?? meta.latest.release_date;
  const esrMeta = reports.export_sales;
  const esrTs = esrMeta?.release_ts_utc ?? esr?.latest.release_ts_utc ?? null;
  return (
    <>
      <TopBar title={<T k="reports.title" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>

      <StaleBanner reportId="wasde" name="report.wasde" cadence="cadence.monthly" releaseTs={wasdeTs} maxDays={stale.wasde} />
      {esr && (
        <StaleBanner reportId="export_sales" name="report.export_sales" cadence="cadence.weekly" releaseTs={esrTs} maxDays={stale.export_sales} />
      )}

      <div className="grid-fit-380">
        <article id="wasde" aria-labelledby="h-wasde" className="card flex flex-col gap-3 p-5" style={{ borderColor: "var(--r-wasde)" }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="eyebrow">
                <T k="cadence.monthly" />
              </div>
              {/* The report's official (English) name. */}
              <h2 id="h-wasde" lang="en" className="m-0 text-[17px] font-bold">
                World Agricultural Supply and Demand Estimates (WASDE)
              </h2>
            </div>
            <LiveChip />
          </div>
          <dl className="m-0 grid">
            <Row label={<T k="reports.latest" />}>
              <MonthYear m={meta.latest.report_month} />
              {meta.latest.wasde_number !== null ? ` · #${meta.latest.wasde_number}` : ""}
              {meta.latest.release_date ? (
                <>
                  {" · "}
                  <DateText iso={meta.latest.release_date} />
                </>
              ) : null}
            </Row>
            <Row label={<T k="reports.next" />}>
              <DateText iso={meta.next_release} />
            </Row>
            <Row label={<T k="reports.freshness" />}>
              <FreshnessChip releaseTs={wasdeTs} maxDays={stale.wasde} />
            </Row>
            <Row label={<T k="reports.history" />}>
              <T
                k="reports.historyRow"
                v={{ reports: num(meta.history.reports), rows: num(meta.history.rows) }}
                months={{ first: meta.history.first_report }}
              />
            </Row>
          </dl>
          <div className="mt-auto flex flex-wrap gap-x-5">
            <Link href="/reports/wasde/" className="inline-flex min-h-11 items-center font-semibold text-link">
              <T k="reports.openWasde" />
            </Link>
            <Link href="/" className="inline-flex min-h-11 items-center text-link">
              <T k="reports.open" />
            </Link>
            <Link href="/data/#report-wasde" className="inline-flex min-h-11 items-center text-link">
              <T k="reports.data" />
            </Link>
          </div>
        </article>

        {esr && (
          <article id="export_sales" aria-labelledby="h-esr" className="card flex flex-col gap-3 p-5" style={{ borderColor: "var(--r-esr)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="eyebrow" style={{ color: "var(--r-esr)" }}>
                  <T k="cadence.d.weeklyThu" />
                </div>
                <h2 id="h-esr" lang="en" className="m-0 text-[17px] font-bold">
                  U.S. Export Sales (ESR) · USDA FAS
                </h2>
              </div>
              <LiveChip />
            </div>
            <dl className="m-0 grid">
              <Row label={<T k="reports.latest" />}>
                <EsrLatestText week={esr.latest.week_ending} release={esr.latest.release_key} />
              </Row>
              <Row label={<T k="reports.next" />}>
                <DateText iso={esrMeta?.next_release ?? esr.next_release} />
              </Row>
              <Row label={<T k="reports.freshness" />}>
                <FreshnessChip releaseTs={esrTs} maxDays={stale.export_sales} />
              </Row>
              {esrMeta && (
                <Row label={<T k="reports.history" />}>
                  <T k="reports.releasesRows" v={{ releases: num(esrMeta.releases), rows: num(esrMeta.rows) }} />
                </Row>
              )}
            </dl>
            <div className="mt-auto flex flex-wrap gap-x-5">
              <Link href="/reports/export-sales/" className="inline-flex min-h-11 items-center font-semibold text-link">
                <T k="reports.openEsr" />
              </Link>
              <Link href="/data/#report-export_sales" className="inline-flex min-h-11 items-center text-link">
                <T k="reports.data" />
              </Link>
            </div>
          </article>
        )}
      </div>

      <Upcoming />
    </>
  );
}
