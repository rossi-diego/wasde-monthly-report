"use client";

import Link from "next/link";

import { T, useT } from "@/components/chrome/I18n";
import { CardNotes, SmallChip } from "@/components/home/InsightCards";
import type { CardView } from "@/lib/insight-text";
import { REPORT_TILE } from "@/lib/reports";

/** A solid report tile on the home page: one finding, its n, small-sample chip, position chip and
 *  release date, and a route to the report page. Charts, extra context lines and the Data link stay
 *  on the report pages. Dense by design (about 200px tall in the 5-across row at 1280px+):
 *  - header: title left and value right below 560px (the value drops under the title when it does
 *    not fit); stacked from 560px;
 *  - the first context line only between 480px and 1279px, where a tile has the width for it;
 *  - one meta row: chip · n · small sample · Notes, then the release date and "Open report".
 *    The full source text ("ESR Nov 5, 2026 · WASDE October 2026") is the date's title and is
 *    read out by screen readers. */
export default function ReportTile({ v, origin }: { v: CardView; origin: "home" | "also" }) {
  const t = useT();
  const hid = `h-tile-${v.id.replace(/[^a-z0-9]+/gi, "-")}`;
  const source = t("card.source", { s: v.source });
  return (
    <article
      aria-labelledby={hid}
      data-testid="insight-card"
      data-origin={origin}
      data-insight-id={v.id}
      data-report={v.report}
      className="box-border flex min-w-0 flex-col gap-1.5 rounded-2xl p-[14px] text-white min-[560px]:gap-2 min-[560px]:p-4 min-[1280px]:gap-1 min-[1280px]:p-[14px]"
      style={{ background: REPORT_TILE[v.report] ?? "var(--tile-wasde)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 min-[560px]:flex-col min-[560px]:flex-nowrap min-[560px]:justify-start">
        <div className="min-w-0 flex-[1_1_160px] min-[560px]:flex-none min-[560px]:self-stretch">
          <div className="line-clamp-2 text-xs font-semibold uppercase tracking-[0.04em]" title={v.eyebrow}>
            {v.eyebrow}
          </div>
          <h3 id={hid} title={v.title} className="m-0 mt-0.5 line-clamp-2 text-[14px] font-bold leading-snug">
            {v.title}
          </h3>
        </div>
        <div className="ml-auto flex min-w-0 max-w-full flex-col items-end text-right min-[560px]:ml-0 min-[560px]:flex-row min-[560px]:flex-wrap min-[560px]:items-baseline min-[560px]:gap-x-2 min-[560px]:text-left">
          <span
            className="mono whitespace-nowrap text-[22px] font-semibold leading-tight tracking-[-0.02em] min-[560px]:text-[26px] min-[1280px]:text-[22px] min-[1440px]:text-[24px]"
            data-param={v.valueParam}
          >
            {v.value}
          </span>
          {v.valueNote && (
            <span className="line-clamp-1 text-[12px] min-[560px]:text-[13px]" title={v.valueNote}>
              {v.valueNote}
            </span>
          )}
        </div>
      </div>
      {v.context[0] && (
        <p className="m-0 line-clamp-2 text-xs max-[479px]:hidden min-[1280px]:hidden" data-testid="card-context">
          {v.context[0]}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        {v.chip && (
          <span className="rounded-full bg-black/20 px-2 py-[1px] font-semibold" data-testid="card-chip">
            {v.chip}
          </span>
        )}
        <span data-testid="n" className="font-semibold">
          {t("card.n", { n: v.n ?? "—" })}
        </span>
        {v.small && <SmallChip tone="onColor" />}
        <CardNotes caveats={v.caveats} className="text-white open:basis-full" onColor />
      </div>
      <div className="mt-auto flex items-center justify-between gap-x-3 border-t border-white/25 pt-0.5 text-xs min-[1280px]:pt-0">
        <span className="min-w-0 truncate" title={source}>
          <span aria-hidden="true">{v.sourceDate}</span>
          <span className="sr-only" data-testid="card-source">
            {source}
          </span>
        </span>
        <Link
          href={v.href}
          className="inline-flex min-h-11 shrink-0 items-center font-semibold text-white focus-visible:outline-white min-[1280px]:min-h-7"
        >
          <T k="card.openReport" />
        </Link>
      </div>
    </article>
  );
}
