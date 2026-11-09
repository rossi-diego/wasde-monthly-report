"use client";

import Link from "next/link";

import { useLang, useT } from "@/components/chrome/I18n";
import TopBar, { type ReleaseInfo } from "@/components/chrome/TopBar";
import { InsightCard } from "@/components/home/InsightCards";
import type { CommodityLens, InsightsDoc, TakeFile } from "@/lib/data-contract";
import { bytes } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { cardView } from "@/lib/insight-text";
import { commodityName } from "@/lib/labels";
import { lensBlocks, lensFindings } from "@/lib/lens";
import { LENSES, REPORT_COLOR, REPORT_NAME } from "@/lib/reports";

/** Cross-report datasets sit with the report they compare against (as on /data). */
const groupOf = (f: TakeFile) =>
  f.report_id !== "cross"
    ? f.report_id
    : f.dataset === "crush_pace"
      ? "oilseed_crush"
      : f.dataset.startsWith("stocks_")
        ? "grain_stocks"
        : "export_sales";

const dsLabel = (f: TakeFile): Key => (f.report_id === "crop_progress" && f.dataset === "weekly" ? "ds.crop_progress.weekly" : (`ds.${f.dataset}` as Key));

export default function LensView({
  lens,
  insights,
  files,
  release,
}: {
  lens: CommodityLens;
  insights: InsightsDoc | null;
  files: TakeFile[];
  release: ReleaseInfo;
}) {
  const t = useT();
  const { lang } = useLang();
  const name = commodityName(lens.commodity_id, lang, lens.label);
  const blocks = lensBlocks(lens, lang);
  const cards = lensFindings(lens, insights)
    .map((i) => ({ i, v: cardView(i, lang) }))
    .filter((x) => x.v !== null);
  const pill = (on: boolean) =>
    `flex min-h-11 min-w-11 shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3.5 font-semibold hover:no-underline ${on ? "bg-[var(--pill-active)] text-white" : "text-ink hover:bg-nav-active"}`;

  return (
    <>
      <TopBar title={t("lens.title", { c: name })} release={release} sub={t("lens.sub", { n: lens.n_reports, c: name.toLowerCase() })}>
        <nav aria-label={t("nav.commodities")} className="flex gap-1 rounded-3xl border border-line bg-card p-1">
          {LENSES.map((l) => (
            <Link key={l.id} href={`/commodities/${l.id}/`} aria-current={l.id === lens.commodity_id ? "page" : undefined} className={pill(l.id === lens.commodity_id)}>
              {commodityName(l.id, lang, l.label)}
            </Link>
          ))}
        </nav>
      </TopBar>

      <p className="m-0 max-w-3xl text-[13px] text-muted">{t("lens.note")}</p>

      <div className="grid-fit-380">
        {blocks.map((b) => {
          const color = REPORT_COLOR[b.reportId];
          const fs = files.filter((f) => groupOf(f) === b.reportId);
          return (
            <article
              key={b.reportId}
              id={`lens-${b.reportId}`}
              aria-labelledby={`h-lens-${b.reportId}`}
              className="card flex min-w-0 flex-col gap-2 p-5"
              style={{ borderTop: `4px solid ${color}` }}
              data-testid="lens-block"
              data-report={b.reportId}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id={`h-lens-${b.reportId}`} className="m-0 text-[15px] font-bold" style={{ color }}>
                  {t(REPORT_NAME[b.reportId])}
                </h2>
                <span className="text-xs text-muted" data-testid="lens-released">
                  {t("lens.released", { date: b.released ?? "—" })}
                  {b.next ? ` · ${t("lens.next", { date: b.next })}` : ""}
                </span>
              </div>
              <dl className="m-0 grid">
                {b.rows.map((r) => (
                  <div key={r.metric} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 border-t border-line py-2" data-testid="lens-row" data-metric={r.metric}>
                    <dt className="min-w-0">
                      <Link href={r.href} className="font-semibold text-link">
                        {r.label}
                      </Link>
                      <div className="text-xs text-muted">{r.period}</div>
                    </dt>
                    <dd className="mono m-0 text-right text-[17px] font-semibold" data-testid="lens-value">
                      {r.value}
                    </dd>
                  </div>
                ))}
              </dl>
              {fs.length > 0 && (
                <ul className="m-0 flex list-none flex-wrap gap-x-4 p-0 text-[13px]">
                  {fs
                    .filter((f) => f.format === "parquet")
                    .map((f) => (
                      <li key={f.file}>
                        <a href={f.href} className="inline-flex min-h-11 items-center gap-1 text-link" download={f.href.startsWith("/") ? "" : undefined}>
                          {t(dsLabel(f))} · Parquet <span className="text-muted">({bytes(f.bytes)})</span>
                        </a>
                      </li>
                    ))}
                </ul>
              )}
              <div className="mt-auto flex flex-wrap gap-x-5 text-[13px]">
                <Link href={b.href} className="inline-flex min-h-11 items-center font-semibold text-link">
                  {t("lens.open")}
                </Link>
                <Link href={b.dataHref} className="inline-flex min-h-11 items-center text-link">
                  {t("lens.data")}
                </Link>
              </div>
            </article>
          );
        })}
      </div>

      {cards.length > 0 && (
        <section aria-labelledby="h-lens-findings" className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-baseline gap-2.5">
            <h2 id="h-lens-findings" className="m-0 text-[17px] font-bold">
              {t("lens.findings")}
            </h2>
            <span className="text-xs text-muted">{t("lens.findingsNote", { c: name.toLowerCase() })}</span>
          </div>
          <div className="grid-fit-240">
            {cards.map(({ i, v }) => (
              <InsightCard key={i.id} v={v!} dataHref={`/data/#report-${i.report_id === "cross" ? "export_sales" : i.report_id}`} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
