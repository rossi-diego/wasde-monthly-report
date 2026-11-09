"use client";

import Link from "next/link";

import RangeBar from "@/components/charts/RangeBar";
import { T, useLang, useT } from "@/components/chrome/I18n";
import type { Insight, InsightsDoc } from "@/lib/data-contract";
import { share } from "@/lib/format";
import { cardView, finding, heroView, type CardView } from "@/lib/insight-text";

/** "small sample" chip: shown whenever the insight carries the small_sample caveat (n < 10). */
export function SmallChip() {
  return (
    <span data-testid="small-sample" className="rounded-full border border-current px-2 py-[1px] text-[11px] font-semibold text-down">
      <T k="tight.small" />
    </span>
  );
}

export function InsightCard({ v, dataHref }: { v: CardView; dataHref?: string }) {
  const t = useT();
  const hid = `h-card-${v.id.replace(/[^a-z0-9]+/gi, "-")}`;
  return (
    <article
      aria-labelledby={hid}
      data-testid="insight-card"
      data-insight-id={v.id}
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
          format={(x) => share(x, 0)}
          ariaLabel={t("card.rangeAria", { min: share(v.range.lo), max: share(v.range.hi), v: v.value })}
        />
      )}
      {v.context.map((c) => (
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
      {v.caveats.length > 0 && (
        <ul className="m-0 list-none p-0 text-xs text-muted">
          {v.caveats.map((c) => (
            <li key={c}>· {c}</li>
          ))}
        </ul>
      )}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 border-t border-line pt-1 text-xs text-muted">
        <span data-testid="card-source">{t("card.source", { s: v.source })}</span>
        <span className="flex gap-x-3">
          <Link href={v.href} className="inline-flex min-h-11 items-center font-semibold text-link">
            <T k="card.open" />
          </Link>
          {dataHref && (
            <Link href={dataHref} className="inline-flex min-h-11 items-center text-link">
              <T k="card.data" />
            </Link>
          )}
        </span>
      </div>
    </article>
  );
}

/** Home hero line from insights.json `hero` (deterministic rules; neutral fallback). */
export function HeroLine({ doc }: { doc: InsightsDoc }) {
  const { lang } = useLang();
  const h = heroView(doc.hero, lang);
  return (
    <section aria-labelledby="h-hero" className="flex flex-col gap-1" data-testid="hero" data-kind={h.kind}>
      <div className="eyebrow" style={{ color: "var(--r-esr)" }}>
        <T k="hero.eyebrow" />
      </div>
      <h2 id="h-hero" className="m-0 max-w-[640px] text-[19px] font-semibold leading-snug" data-testid="hero-text">
        {h.text}
      </h2>
      {h.sub && (
        <p className="m-0 text-[13px] text-muted" data-testid="hero-sub">
          {h.sub}
        </p>
      )}
    </section>
  );
}

const dataAnchor = (i: Insight) => `/data/#report-${i.report_id === "cross" ? "export_sales" : i.report_id}`;

/** The home cards (insights.json `home_cards`, in order): one per report plus the cross card. */
export default function InsightCards({ doc }: { doc: InsightsDoc }) {
  const { lang } = useLang();
  const cards = doc.home_cards
    .map((id) => finding(doc, id))
    .filter((i): i is Insight => Boolean(i))
    .map((i) => ({ i, v: cardView(i, lang) }))
    .filter((x): x is { i: Insight; v: CardView } => x.v !== null);
  if (!cards.length) return null;
  return (
    <section aria-labelledby="h-cards" className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline gap-2.5">
        <h2 id="h-cards" className="m-0 text-[17px] font-bold">
          <T k="cards.title" />
        </h2>
        <span className="text-xs text-muted">
          <T k="cards.note" />
        </span>
      </div>
      <div className="grid-fit-240">
        {cards.map(({ i, v }) => (
          <InsightCard key={v.id} v={v} dataHref={dataAnchor(i)} />
        ))}
      </div>
    </section>
  );
}
