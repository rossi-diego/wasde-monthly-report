"use client";

import Link from "next/link";

import RangeBar from "@/components/charts/RangeBar";
import { T, useLang, useT } from "@/components/chrome/I18n";
import ReportTile from "@/components/home/ReportTile";
import type { InsightsDoc } from "@/lib/data-contract";
import { cardView, heroView, rangeText, rangeTick, type CardView } from "@/lib/insight-text";
import { heroEvidence, homeTiles } from "@/lib/lens";

/** "small sample" chip: shown whenever the insight carries the small_sample caveat (n < 10).
 *  `onColor`: white border and text, for the solid report tiles. */
export function SmallChip({ tone = "default" }: { tone?: "default" | "onColor" }) {
  const cls = tone === "onColor" ? "border-white text-white" : "border-current text-down";
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

/** Home hero band: the insights.json `hero` sentence (deterministic rules; neutral fallback)
 *  and, beside it, the evidence card of its first clause (lib/lens.ts heroEvidence). */
export function HeroBand({ doc }: { doc: InsightsDoc }) {
  const { lang } = useLang();
  const h = heroView(doc.hero, lang);
  const ev = heroEvidence(doc);
  const v = ev ? cardView(ev, lang) : null;
  return (
    <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-12 lg:gap-6">
      <section
        aria-labelledby="h-hero"
        className={`flex flex-col gap-1.5 ${v ? "lg:col-span-7" : "lg:col-span-12"} lg:pt-2`}
        data-testid="hero"
        data-kind={h.kind}
      >
        <div className="eyebrow" style={{ color: "var(--r-esr)" }}>
          <T k="hero.eyebrow" />
        </div>
        <h2 id="h-hero" className="m-0 max-w-[640px] text-[20px] font-semibold leading-[1.3] sm:text-[22px]" data-testid="hero-text">
          {h.text}
        </h2>
        {h.sub && (
          <p className="m-0 text-[13px] text-muted" data-testid="hero-sub">
            {h.sub}
          </p>
        )}
      </section>
      {v && (
        <div className="min-w-0 lg:col-span-5">
          <InsightCard v={v} variant="compact" origin="hero" />
        </div>
      )}
    </div>
  );
}

/** "Latest from each report": one solid tile per report, in report order (lib/lens.ts homeTiles). */
export default function ReportTiles({ doc }: { doc: InsightsDoc }) {
  const { lang } = useLang();
  const tiles = homeTiles(doc)
    .map((x) => ({ origin: x.origin, v: cardView(x.insight, lang) }))
    .filter((x): x is { origin: "home" | "also"; v: CardView } => x.v !== null);
  if (!tiles.length) return null;
  return (
    <section aria-labelledby="h-cards" className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
        <h2 id="h-cards" className="m-0 text-[17px] font-bold">
          <T k="cards.title" />
        </h2>
        <span className="text-xs text-muted">
          <T k="cards.note" />
        </span>
      </div>
      <div
        className="grid grid-cols-1 gap-4 min-[560px]:grid-cols-2 min-[560px]:[&>*:last-child:nth-child(odd)]:col-span-2 min-[1280px]:grid-cols-[repeat(var(--tiles),minmax(0,1fr))] min-[1280px]:[&>*:last-child:nth-child(odd)]:col-span-1"
        style={{ "--tiles": Math.min(tiles.length, 5) } as React.CSSProperties}
        data-testid="report-tiles"
      >
        {tiles.map(({ origin, v }) => (
          <ReportTile key={v.id} v={v} origin={origin} />
        ))}
      </div>
    </section>
  );
}
