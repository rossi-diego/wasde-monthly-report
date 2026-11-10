"use client";

import Link from "next/link";

import { T, useT } from "@/components/chrome/I18n";
import { CardNotes, SmallChip } from "@/components/home/InsightCards";
import type { CardView } from "@/lib/insight-text";
import type { TileSlots } from "@/lib/lens";
import { REPORT_TILE } from "@/lib/reports";

/** A solid report tile on the home page: one finding, its n, small-sample chip, position chip and
 *  release date, and a route to the report page. Charts and the Data link stay on the report pages.
 *
 *  Five slots, in this order: eyebrow · title · value · meta (one context line (up to 2 lines), then chip · n ·
 *  small sample · Notes) · footer (release date | Open report). From 560px the tile is a subgrid
 *  of its parent (.report-tiles in globals.css), so the values and footers of a row of tiles share
 *  one line; below 560px it is a compact card (title left, value right). Eyebrow, title and context are
 *  line-clamped; the verdict chip wraps and is never cut, with the full text in `title`. The full source text ("ESR Nov 5, 2026 · WASDE
 *  October 2026") is read out by screen readers next to the release date. */
export default function ReportTile({
  v,
  origin,
  slots,
  spanSm,
  spanMd,
}: {
  v: CardView;
  origin: "home" | "also";
  /** Number, unit and the one context line (lib/lens.ts tileSlots); no context renders nothing. */
  slots: TileSlots;
  /** Column span of 2 (560–767px) and of 6 (768–1279px). */
  spanSm: number;
  spanMd: number;
}) {
  const t = useT();
  const hid = `h-tile-${v.id.replace(/[^a-z0-9]+/gi, "-")}`;
  const source = t("card.source", { s: v.source });
  const { context } = slots;
  return (
    <article
      aria-labelledby={hid}
      data-testid="insight-card"
      data-origin={origin}
      data-insight-id={v.id}
      data-report={v.report}
      className="report-tile"
      style={{ background: REPORT_TILE[v.report] ?? "var(--tile-wasde)", "--span-sm": spanSm, "--span-md": spanMd } as React.CSSProperties}
    >
      <div className="rt-eb" title={v.eyebrow}>
        {v.eyebrow}
      </div>
      <h3 id={hid} title={v.title} className="rt-h3">
        {v.title}
      </h3>
      <div className="rt-val">
        {/* The whole value (number + unit suffix) is the data-param element: exactly formatParam. */}
        <span className="rt-v" data-testid="tile-value" data-param={v.valueParam}>
          <span className="mono">{slots.num}</span>
          {slots.suffix && <span className="rt-u">{slots.suffix}</span>}
        </span>
        {slots.unit && (
          <span className="rt-u" title={slots.unit}>
            {slots.unit}
          </span>
        )}
      </div>
      <div className="rt-meta">
        {context && (
          <p className="rt-ctx" title={context} data-testid="card-context">
            {context}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs">
          {v.chip && (
            <span className="rt-chip inline-block rounded-xl bg-black/20 px-2 py-[1px] font-semibold" title={v.chip} data-testid="card-chip">
              {v.chip}
            </span>
          )}
          <span data-testid="n" className="font-semibold">
            {t("card.n", { n: v.n ?? "—" })}
          </span>
          {v.small && <SmallChip tone="onColor" />}
          <CardNotes caveats={v.caveats} className="text-white open:basis-full" onColor />
        </div>
      </div>
      <div className="rt-ft" data-testid="tile-footer">
        <span className="min-w-0 truncate whitespace-nowrap" title={source}>
          <span aria-hidden="true" data-testid="tile-date">
            {v.sourceDate}
          </span>
          <span className="sr-only" data-testid="card-source">
            {source}
          </span>
        </span>
        <Link
          href={v.href}
          aria-label={t("tile.openAria")}
          className="inline-flex min-h-11 shrink-0 items-center whitespace-nowrap font-semibold text-white focus-visible:outline-white min-[560px]:min-h-9"
        >
          <span className="rt-open-long">
            <T k="card.openReport" />
          </span>
          <span className="rt-open-short">
            <T k="tile.openShort" />
          </span>
        </Link>
      </div>
    </article>
  );
}
