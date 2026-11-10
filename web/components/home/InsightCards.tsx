"use client";

import Link from "next/link";

import RangeBar from "@/components/charts/RangeBar";
import { T, useLang, useT } from "@/components/chrome/I18n";
import ReportTile from "@/components/home/ReportTile";
import type { InsightsDoc } from "@/lib/data-contract";
import { cardView, heroView, rangeText, rangeTick, type CardView } from "@/lib/insight-text";
import { heroEvidence, homeTiles, tileSlots, type TileSlots } from "@/lib/lens";

/** "small sample" chip: shown whenever the insight carries the small_sample caveat (n < 10).
 *  `onColor`: white border and text, for the solid report tiles. */
export function SmallChip({ tone = "default" }: { tone?: "default" | "onColor" | "accent" }) {
  const cls =
    tone === "onColor" ? "border-white text-white" : tone === "accent" ? "border-[var(--r-crush)] text-[var(--r-crush)]" : "border-current text-down";
  return (
    <span data-testid="small-sample" className={`rounded-full border px-2 py-[1px] text-[11px] font-semibold ${cls}`}>
      <T k="tight.small" />
    </span>
  );
}

/** Caveats behind a closed disclosure ("Notes (k)"); nothing when there are none. */
export function CardNotes({ caveats, className = "text-muted", onColor = false }: { caveats: string[]; className?: string; onColor?: boolean }) {
  const t = useT();
  if (!caveats.length) return null;
  return (
    <details className={`text-xs ${className}`} data-testid="card-notes">
      <summary className={`inline-flex min-h-6 items-center font-semibold ${onColor ? "focus-visible:outline-white" : ""}`}>{t("card.notes", { n: caveats.length })}</summary>
      <ul className="m-0 mt-1 list-none p-0">
        {caveats.map((c) => (
          <li key={c}>· {c}</li>
        ))}
      </ul>
    </details>
  );
}

export function InsightCard({
  v,
  dataHref,
  variant = "full",
  origin,
}: {
  v: CardView;
  dataHref?: string;
  /** compact (home hero evidence): first context line, caveats behind "Notes", no Data link. */
  variant?: "full" | "compact";
  origin?: string;
}) {
  const t = useT();
  const compact = variant === "compact";
  const hid = `h-card-${v.id.replace(/[^a-z0-9]+/gi, "-")}`;
  const context = compact ? v.context.slice(0, 1) : v.context;
  return (
    <article
      aria-labelledby={hid}
      data-testid="insight-card"
      data-insight-id={v.id}
      data-origin={origin}
      className="card flex min-w-0 flex-col gap-2 p-[18px]"
      style={{ borderTop: `4px solid ${v.color}` }}
    >
      <div className="text-xs font-bold uppercase tracking-[0.04em]" style={{ color: v.color }}>
        {v.eyebrow}
      </div>
      <h3 id={hid} className="m-0 text-[15px] font-bold">
        {v.title}
      </h3>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="mono text-[28px] font-semibold tracking-[-0.02em]" data-param={v.valueParam}>
          {v.value}
        </span>
        {v.valueNote && <span className="text-[13px] text-muted">{v.valueNote}</span>}
      </div>
      {v.range && (
        <RangeBar
          lo={v.range.lo}
          hi={v.range.hi}
          mean={v.range.mean}
          value={v.range.value}
          color={v.color}
          fromZero={v.rangeUnit === "share" || v.rangeUnit === "pct"}
          format={(x) => rangeTick(v.rangeUnit, x)}
          ariaLabel={t("card.rangeAria", {
            min: rangeText(v.rangeUnit, v.range.lo),
            max: rangeText(v.rangeUnit, v.range.hi),
            v: v.value,
          })}
        />
      )}
      {context.map((c) => (
        <p key={c} className="m-0 text-[13px]" data-testid="card-context">
          {c}
        </p>
      ))}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        {v.chip && (
          <span className="rounded-full bg-nav-active px-2 py-[1px] font-semibold text-ink" data-testid="card-chip">
            {v.chip}
          </span>
        )}
        <span data-testid="n" className="font-semibold text-ink">
          {t("card.n", { n: v.n ?? "—" })}
        </span>
        {v.small && <SmallChip />}
      </div>
      {compact ? (
        <CardNotes caveats={v.caveats} />
      ) : (
        v.caveats.length > 0 && (
          <ul className="m-0 list-none p-0 text-xs text-muted">
            {v.caveats.map((c) => (
              <li key={c}>· {c}</li>
            ))}
          </ul>
        )
      )}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 border-t border-line pt-1 text-xs text-muted">
        <span data-testid="card-source">{t("card.source", { s: v.source })}</span>
        <span className="flex gap-x-3">
          <Link href={v.href} className="inline-flex min-h-11 items-center font-semibold text-link">
            <T k="card.open" />
          </Link>
          {!compact && dataHref && (
            <Link href={dataHref} className="inline-flex min-h-11 items-center text-link">
              <T k="card.data" />
            </Link>
          )}
        </span>
      </div>
    </article>
  );
}

/** Home lead card: the insights.json `hero` sentence as the card's heading (deterministic rules;
 *  neutral fallback), then the evidence of its first clause (lib/lens.ts heroEvidence) as a
 *  two-column block (number | range strip, chips and Notes) and a source | link footer pinned to
 *  the bottom. Without evidence the card is the sentence and its sub line only. */
export function LeadCard({ doc, className = "" }: { doc: InsightsDoc; className?: string }) {
  const { lang } = useLang();
  const t = useT();
  const h = heroView(doc.hero, lang);
  const ev = heroEvidence(doc);
  const v = ev ? cardView(ev, lang) : null;
  const eid = v ? `h-lead-${v.id.replace(/[^a-z0-9]+/gi, "-")}` : undefined;
  return (
    <article
      aria-labelledby="h-hero"
      data-testid="lead-card"
      className={`card flex min-w-0 flex-col px-4 pt-4 min-[560px]:px-[22px] min-[560px]:pt-5 ${v ? "" : "pb-5"} ${className}`}
      style={{ borderTop: "3px solid var(--r-esr)" }}
    >
      <div data-testid="hero" data-kind={h.kind} className="flex flex-col gap-1">
        <div className="eyebrow" style={{ color: "var(--r-esr)" }} data-testid="lead-eyebrow">
          {h.eyebrow}
        </div>
        <h2 id="h-hero" className="m-0 mt-0.5 text-[20px] font-semibold leading-[1.25] tracking-[-0.01em] min-[560px]:text-[22px]" data-testid="hero-text">
          {h.text}
        </h2>
        <p className="m-0 text-[13px] text-muted" data-testid="hero-sub">
          {h.sub}
        </p>
      </div>
      {v && (
        <section
          aria-labelledby={eid}
          data-testid="insight-card"
          data-insight-id={v.id}
          data-origin="hero"
          className="mt-[18px] flex flex-1 flex-col border-t border-line"
        >
          <div className="grid flex-1 grid-cols-1 items-center gap-3 py-4 min-[560px]:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] min-[560px]:gap-6">
            <div className="min-w-0">
              <h3 id={eid} className="m-0 mb-1.5 text-[14px] font-semibold">
                {v.title}
              </h3>
              <div className="mono text-[34px] font-semibold leading-[1.1] tracking-[-0.02em]" data-param={v.valueParam} data-testid="lead-value">
                {v.value}
              </div>
              {v.valueNote && <p className="m-0 mt-1.5 text-[13px] text-muted">{v.valueNote}</p>}
            </div>
            <div className="flex min-w-0 flex-col gap-2">
              {v.range && (
                <RangeBar
                  lo={v.range.lo}
                  hi={v.range.hi}
                  mean={v.range.mean}
                  value={v.range.value}
                  color={v.color}
                  fromZero={v.rangeUnit === "share" || v.rangeUnit === "pct"}
                  format={(x) => rangeTick(v.rangeUnit, x)}
                  ariaLabel={t("card.rangeAria", {
                    min: rangeText(v.rangeUnit, v.range.lo),
                    max: rangeText(v.rangeUnit, v.range.hi),
                    v: v.value,
                  })}
                />
              )}
              {v.context[0] && (
                <p className="m-0 text-[13px] text-muted" data-testid="card-context">
                  {v.context[0]}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                {v.chip && (
                  <span className="rounded-full bg-nav-active px-2 py-[1px] font-semibold text-ink" data-testid="card-chip">
                    {v.chip}
                  </span>
                )}
                <span data-testid="n" className="font-semibold text-ink">
                  {t("card.n", { n: v.n ?? "—" })}
                </span>
                {v.small && <SmallChip tone="accent" />}
                <CardNotes caveats={v.caveats} className="text-muted open:basis-full" />
              </div>
            </div>
          </div>
          <div className="mt-auto flex min-h-12 flex-wrap items-center justify-between gap-x-3 border-t border-line text-xs text-muted" data-testid="card-footer">
            <span data-testid="card-source">{t("card.source", { s: v.source })}</span>
            <Link href={v.href} className="inline-flex min-h-11 items-center font-semibold text-link">
              <T k="card.open" />
            </Link>
          </div>
        </section>
      )}
    </article>
  );
}

/** "Latest from each report": one solid tile per report, in report order (lib/lens.ts homeTiles). */
export default function ReportTiles({ doc }: { doc: InsightsDoc }) {
  const { lang } = useLang();
  const tiles = homeTiles(doc)
    .map((x) => {
      const v = cardView(x.insight, lang);
      return { origin: x.origin, v, slots: v ? tileSlots(doc, x.insight, v, lang) : null };
    })
    .filter((x): x is { origin: "home" | "also"; v: CardView; slots: TileSlots } => x.v !== null && x.slots !== null);
  if (!tiles.length) return null;
  const l = tileLayout(tiles.length);
  return (
    <section aria-labelledby="h-cards" className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
        <h2 id="h-cards" className="m-0 text-[16px] font-bold min-[560px]:text-[17px]">
          <T k="cards.title" />
        </h2>
        <span className="text-xs text-muted">
          <T k="cards.note" />
        </span>
      </div>
      <div
        className="report-tiles"
        style={{ "--tiles": tiles.length, "--rows-sm": l.rowsSm, "--rows-md": l.rowsMd } as React.CSSProperties}
        data-testid="report-tiles"
      >
        {tiles.map(({ origin, v, slots }, k) => (
          <ReportTile key={v.id} v={v} origin={origin} slots={slots} spanSm={l.sm[k]} spanMd={l.md[k]} />
        ))}
      </div>
    </section>
  );
}

/** Column spans of n tiles below 1280px, without an orphan cell:
 *  - of 6 columns (768–1279px): rows of 3 (span 2), then a row of 2 (span 3); four tiles are 2 + 2;
 *  - of 2 columns (560–767px): pairs, with the first tile full width when n is odd. */
export function tileLayout(n: number): { md: number[]; sm: number[]; rowsMd: number; rowsSm: number } {
  const rows: number[] = n === 4 ? [2, 2] : [];
  if (n !== 4) for (let left = n; left > 0; left -= 3) rows.push(Math.min(3, left));
  const md = rows.flatMap((k) => Array<number>(k).fill(6 / k));
  const sm = Array.from({ length: n }, (_, k) => (n % 2 === 1 && k === 0 ? 2 : 1));
  return { md, sm, rowsMd: rows.length, rowsSm: Math.ceil(n / 2) };
}
