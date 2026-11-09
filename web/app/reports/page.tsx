import type { Metadata } from "next";
import Link from "next/link";

import { DateText, MonthYear, T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import { EsrLatestText, FreshnessChip, KeyDates, StaleBanner } from "@/components/Freshness";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getCropProgressIndex, getCrushIndex, getEsrIndex, getGrainStocksIndex, getInsights, getMeta, getReleaseCatalog, getReportsMeta } from "@/lib/data";
import { num } from "@/lib/format";
import type { Key } from "@/lib/i18n";

export const metadata: Metadata = { title: "Reports · USDA Reports Dashboard" };

// Cadence + grace when insights.json (gates.stale_after_days) is not in the build.
const DEFAULT_STALE: Record<string, number> = { wasde: 76, export_sales: 17, oilseed_crush: 76, crop_progress: 17, grain_stocks: 192 };

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 border-t border-line py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="m-0 text-right font-semibold">{children}</dd>
    </div>
  );
}

function LiveChip({ color = "var(--pill-active)" }: { color?: string }) {
  return (
    <span className="rounded-full px-3 py-1 text-xs font-semibold text-white" style={{ background: color }}>
      <T k="reports.live" />
    </span>
  );
}

export default function ReportsPage() {
  const meta = getMeta();
  const reports = getReportsMeta();
  const cp = getCropProgressIndex();
  const cpMeta = reports.crop_progress;
  const cpTs = cpMeta?.release_ts_utc ?? cp?.latest.release_ts_utc ?? null;
  const cpOff = cp?.season?.state === "closed";
  const gs = getGrainStocksIndex();
  const gsMeta = reports.grain_stocks;
  const gsTs = gsMeta?.release_ts_utc ?? gs?.latest.release_ts_utc ?? null;
  const esr = getEsrIndex();
  const stale = { ...DEFAULT_STALE, ...(getInsights()?.gates.stale_after_days ?? {}) };
  const wasdeTs = reports.wasde?.release_ts_utc ?? meta.latest.release_date;
  const esrMeta = reports.export_sales;
  const esrTs = esrMeta?.release_ts_utc ?? esr?.latest.release_ts_utc ?? null;
  const crush = getCrushIndex();
  const crushMeta = reports.oilseed_crush;
  const crushTs = crushMeta?.release_ts_utc ?? crush?.latest.release_ts_utc ?? null;
  // Rows of the published ESR datasets (one entry per dataset; the Parquet file's count).
  const esrDatasetRows = (getReleaseCatalog()?.files ?? []).filter(
    (f) => f.report_id === "export_sales" && f.format === "parquet" && !f.legacy_alias_of,
  );
  return (
    <>
      <TopBar title={<T k="reports.title" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>

      <StaleBanner reportId="wasde" name="report.wasde" cadence="cadence.monthly" releaseTs={wasdeTs} maxDays={stale.wasde} />
      {esr && (
        <StaleBanner reportId="export_sales" name="report.export_sales" cadence="cadence.weekly" releaseTs={esrTs} maxDays={stale.export_sales} />
      )}
      {crush && (
        <StaleBanner reportId="oilseed_crush" name="report.crush" cadence="cadence.monthly" releaseTs={crushTs} maxDays={stale.oilseed_crush} />
      )}
      {cp && (
        <StaleBanner reportId="crop_progress" name="report.crop_progress" cadence="cadence.weekly" releaseTs={cpTs} maxDays={stale.crop_progress} offSeason={cpOff} />
      )}
      {gs && (
        <StaleBanner reportId="grain_stocks" name="report.grain_stocks" cadence="cadence.quarterly" releaseTs={gsTs} maxDays={stale.grain_stocks} />
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
              <LiveChip color="var(--pill-esr)" />
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
                  {esrDatasetRows.length > 0 && (
                    <div className="text-xs font-normal text-muted" data-testid="esr-published-rows">
                      <T k="reports.publishedRows" />{" "}
                      {esrDatasetRows.map((r, i) => (
                        <span key={r.dataset}>
                          {i > 0 ? " · " : ""}
                          <T k={`ds.${r.dataset}` as Key} /> {num(r.rows)}
                        </span>
                      ))}
                    </div>
                  )}
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

        {crush && (
          <article id="oilseed_crush" aria-labelledby="h-crush" className="card flex flex-col gap-3 p-5" style={{ borderColor: "var(--r-crush)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="eyebrow" style={{ color: "var(--r-crush)" }}>
                  <T k="cadence.d.monthlyCrush" />
                </div>
                <h2 id="h-crush" lang="en" className="m-0 text-[17px] font-bold">
                  Fats &amp; Oils: Oilseed Crushings · USDA NASS
                </h2>
              </div>
              <LiveChip color="var(--pill-crush)" />
            </div>
            <dl className="m-0 grid">
              <Row label={<T k="reports.latest" />}>
                <MonthYear m={crush.latest.month.slice(0, 7)} />
                {" · "}
                <DateText iso={crush.latest.release_key} />
              </Row>
              <Row label={<T k="reports.next" />}>
                <DateText iso={crushMeta?.next_release ?? crush.next_release} />
              </Row>
              <Row label={<T k="reports.freshness" />}>
                <FreshnessChip releaseTs={crushTs} maxDays={stale.oilseed_crush} />
              </Row>
              {crushMeta && (
                <Row label={<T k="reports.history" />}>
                  <T k="reports.releasesRows" v={{ releases: num(crushMeta.releases), rows: num(crushMeta.rows) }} />
                  <div className="text-xs font-normal text-muted">
                    <T k="card.window" v={{ from: crush.history_start }} />
                  </div>
                </Row>
              )}
            </dl>
            <div className="mt-auto flex flex-wrap gap-x-5">
              <Link href="/reports/oilseed-crush/" className="inline-flex min-h-11 items-center font-semibold text-link">
                <T k="reports.openCrush" />
              </Link>
              <Link href="/data/#report-oilseed_crush" className="inline-flex min-h-11 items-center text-link">
                <T k="reports.data" />
              </Link>
            </div>
          </article>
        )}

        {cp && (
          <article id="crop_progress" aria-labelledby="h-cp" className="card flex flex-col gap-3 p-5" style={{ borderColor: "var(--r-progress)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="eyebrow" style={{ color: "var(--r-progress)" }}>
                  <T k="cadence.d.weeklyMonSeason" />
                </div>
                <h2 id="h-cp" lang="en" className="m-0 text-[17px] font-bold">
                  Crop Progress · USDA NASS
                </h2>
              </div>
              <LiveChip color="var(--pill-progress)" />
            </div>
            <dl className="m-0 grid">
              <Row label={<T k="reports.latest" />}>
                <KeyDates k="reports.cpLatest" dates={{ week: cp.latest.week_ending, date: cp.latest.release_key }} />
              </Row>
              <Row label={<T k="reports.next" />}>
                <DateText iso={cpMeta?.next_release ?? cp.next_release} />
              </Row>
              {cp.season && (
                <Row label={<T k="reports.season" />}>
                  <span data-testid="cp-season-state" data-state={cp.season.state}>
                    {cpOff ? (
                      <KeyDates k="reports.seasonClosed" dates={{ next: cp.next_release }} vars={{ season: cp.season.season }} />
                    ) : (
                      <KeyDates k="reports.seasonOpen" dates={{ last: cp.season.last_scheduled }} vars={{ season: cp.season.season }} />
                    )}
                  </span>
                </Row>
              )}
              <Row label={<T k="reports.freshness" />}>
                <FreshnessChip releaseTs={cpTs} maxDays={stale.crop_progress} offSeason={cpOff} />
              </Row>
              {cpMeta && (
                <Row label={<T k="reports.history" />}>
                  <T k="reports.releasesRows" v={{ releases: num(cpMeta.releases), rows: num(cpMeta.rows) }} />
                </Row>
              )}
            </dl>
            <div className="mt-auto flex flex-wrap gap-x-5">
              <Link href="/reports/crop-progress/" className="inline-flex min-h-11 items-center font-semibold text-link">
                <T k="reports.openCp" />
              </Link>
              <Link href="/data/#report-crop_progress" className="inline-flex min-h-11 items-center text-link">
                <T k="reports.data" />
              </Link>
            </div>
          </article>
        )}

        {gs && (
          <article id="grain_stocks" aria-labelledby="h-gs" className="card flex flex-col gap-3 p-5" style={{ borderColor: "var(--r-stocks)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="eyebrow" style={{ color: "var(--r-stocks)" }}>
                  <T k="cadence.d.quarterlyGs" />
                </div>
                <h2 id="h-gs" lang="en" className="m-0 text-[17px] font-bold">
                  Grain Stocks · USDA NASS
                </h2>
              </div>
              <LiveChip color="var(--pill-stocks)" />
            </div>
            <dl className="m-0 grid">
              <Row label={<T k="reports.latest" />}>
                <KeyDates k="reports.gsLatest" dates={{ as: gs.latest.as_of_date, date: gs.latest.release_key }} />
              </Row>
              <Row label={<T k="reports.next" />}>
                <DateText iso={gsMeta?.next_release ?? gs.next_release} />
              </Row>
              <Row label={<T k="reports.freshness" />}>
                <FreshnessChip releaseTs={gsTs} maxDays={stale.grain_stocks} />
              </Row>
              {gsMeta && (
                <Row label={<T k="reports.history" />}>
                  <T k="reports.releasesRows" v={{ releases: num(gsMeta.releases), rows: num(gsMeta.rows) }} />
                </Row>
              )}
            </dl>
            <div className="mt-auto flex flex-wrap gap-x-5">
              <Link href="/reports/grain-stocks/" className="inline-flex min-h-11 items-center font-semibold text-link">
                <T k="reports.openGs" />
              </Link>
              <Link href="/data/#report-grain_stocks" className="inline-flex min-h-11 items-center text-link">
                <T k="reports.data" />
              </Link>
            </div>
          </article>
        )}
      </div>
    </>
  );
}
