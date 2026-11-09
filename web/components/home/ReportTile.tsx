"use client";

import Link from "next/link";

import { T, useT } from "@/components/chrome/I18n";
import { CardNotes, SmallChip } from "@/components/home/InsightCards";
import type { CardView } from "@/lib/insight-text";
import { REPORT_TILE } from "@/lib/reports";

/** A solid report tile on the home page: one finding, its n, small-sample chip, position chip and
 *  source release, and a route to the report page. Charts, extra context lines and the Data link
 *  stay on the report pages. Below 560px the header is one row (title left, value right). */
export default function ReportTile({ v, origin }: { v: CardView; origin: "home" | "also" }) {
  const t = useT();
  const hid = `h-tile-${v.id.replace(/[^a-z0-9]+/gi, "-")}`;
  return (
    <article
      aria-labelledby={hid}
      data-testid="insight-card"
      data-origin={origin}
      data-insight-id={v.id}
      data-report={v.report}
      className="box-border flex min-w-0 flex-col gap-2 rounded-2xl p-[18px] text-white min-[560px]:min-h-[180px]"
      style={{ background: REPORT_TILE[v.report] ?? "var(--tile-wasde)" }}
    >
      {/* Below 560px: title left, value right, the value's note underneath; wider: stacked. */}
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-1 min-[560px]:grid-cols-1 min-[560px]:gap-y-2">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.04em]">{v.eyebrow}</div>
          <h3 id={hid} title={v.title} className="m-0 mt-0.5 line-clamp-2 text-[14px] font-bold leading-snug">
            {v.title}
          </h3>
        </div>
        {/* `contents` below 560px puts the value and its note on the parent grid. */}
        <div className="max-[559px]:contents min-[560px]:flex min-[560px]:flex-wrap min-[560px]:items-baseline min-[560px]:gap-x-2">
          <span
            className="mono whitespace-nowrap text-right text-[24px] font-semibold leading-tight tracking-[-0.02em] min-[560px]:whitespace-normal min-[560px]:text-left min-[560px]:text-[28px] min-[1280px]:text-[22px] min-[1440px]:text-[24px]"
            data-param={v.valueParam}
          >
            {v.value}
          </span>
          {v.valueNote && <span className="col-span-2 text-[13px]">{v.valueNote}</span>}
        </div>
      </div>
      {v.context[0] && (
        <p className="m-0 text-xs" data-testid="card-context">
          {v.context[0]}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {v.chip && (
          <span className="rounded-full bg-black/20 px-2 py-[1px] font-semibold" data-testid="card-chip">
            {v.chip}
          </span>
        )}
        <span data-testid="n" className="font-semibold">
          {t("card.n", { n: v.n ?? "—" })}
        </span>
        {v.small && <SmallChip tone="onColor" />}
      </div>
      <CardNotes caveats={v.caveats} className="text-white" onColor />
      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 border-t border-white/25 pt-1 text-xs">
        <span data-testid="card-source">{t("card.source", { s: v.source })}</span>
        <Link href={v.href} className="inline-flex min-h-11 items-center font-semibold text-white focus-visible:outline-white">
          <T k="card.openReport" />
        </Link>
      </div>
    </article>
  );
}
