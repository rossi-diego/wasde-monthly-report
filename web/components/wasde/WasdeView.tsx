"use client";

import Link from "next/link";

import Bar from "@/components/charts/Bar";
import { ChartTable } from "@/components/charts/common";
import { CommodityName, T, useLang, useT } from "@/components/chrome/I18n";
import TopBar, { CommodityPills, type Pill, type ReleaseInfo } from "@/components/chrome/TopBar";
import { InsightCard } from "@/components/home/InsightCards";
import type { Insight, InsightsDoc } from "@/lib/data-contract";
import { monthYear, num } from "@/lib/format";
import { cardView, changeView, type CardView } from "@/lib/insight-text";
import type { Key } from "@/lib/i18n";

function Chapter({ n, id, eyebrow, title, children }: { n: number; id: string; eyebrow: Key; title: Key; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2.5" data-testid={`chapter-${n}`}>
      <div>
        <div className="eyebrow">
          <T k="esr.ch" v={{ n: `0${n}` }} /> · <T k={eyebrow} />
        </div>
        <h2 id={id} className="m-0 mt-0.5 text-[17px] font-bold">
          <T k={title} />
        </h2>
      </div>
      {children}
    </section>
  );
}

const ok = (i: Insight) => i.suppressed_reason === null;

export default function WasdeView({
  insights,
  release,
  pills,
}: {
  insights: InsightsDoc | null;
  release: ReleaseInfo;
  pills: Pill[];
}) {
  const t = useT();
  const { lang } = useLang();
  const all = insights?.insights ?? [];
  const w1 = all.filter((i) => i.rule === "W1" && ok(i)).sort((a, b) => Number(Boolean(b.params.headline)) - Number(Boolean(a.params.headline)));
  const w2 = all.filter((i) => i.rule === "W2" && ok(i));
  const w34 = all.filter((i) => (i.rule === "W3" || i.rule === "W4") && ok(i));
  const views = (xs: Insight[]) => xs.map((i) => ({ i, v: cardView(i, lang) })).filter((x): x is { i: Insight; v: CardView } => x.v !== null);

  return (
    <>
      <TopBar title={t("wasde.title", { month: monthYear(release.reportMonth, lang) })} release={release}>
        <CommodityPills pills={pills} />
      </TopBar>

      {!insights && (
        <p className="m-0 text-muted">
          <T k="wasde.none" />
        </p>
      )}

      {w1.length > 0 && (
        <Chapter n={1} id="h-w-changes" eyebrow="wasde.c1.eb" title="wasde.c1">
          <ol className="card m-0 list-none px-5 py-2" data-testid="w1-list">
            {w1.map((i) => {
              const c = changeView(i, lang);
              const up = (i.params.delta as number) > 0;
              return (
                <li key={c.id} data-insight-id={c.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 border-t border-line py-2.5 first:border-t-0">
                  <span className="font-semibold">
                    {c.what}
                    {c.headline && (
                      <span className="ml-2 rounded-full bg-nav-active px-2 py-[1px] text-[11px] font-semibold">
                        <T k="wasde.w1.headline" />
                      </span>
                    )}
                  </span>
                  <span className={`mono text-right font-semibold ${up ? "text-up" : "text-down"}`}>
                    {c.delta}
                    {c.pct ? ` (${c.pct})` : ""}
                  </span>
                  <span className="text-xs text-muted">{c.value}</span>
                  <span className="text-right text-xs text-muted">{c.score}</span>
                </li>
              );
            })}
          </ol>
        </Chapter>
      )}

      {w2.length > 0 && (
        <Chapter n={2} id="h-w-tight" eyebrow="wasde.c2.eb" title="wasde.c2">
          <div className="grid-fit-240">
            {views(w2).map(({ i, v }) => {
              const hist = (i.params.history as { market_year: string; stocks_to_use_pct: number }[]) ?? [];
              const my = i.params.market_year as string;
              const items = hist.map((h) => ({
                label: h.market_year,
                value: h.stocks_to_use_pct,
                kind: (h.market_year === my ? "current" : "past") as "current" | "past",
              }));
              if (!items.some((x) => x.kind === "current")) items.push({ label: my, value: i.params.stocks_to_use_pct as number, kind: "current" });
              const aria = t("wasde.c2.aria", { what: v.title, first: i.params.first_market_year as string, my, v: v.value });
              return (
                <div key={v.id} className="flex min-w-0 flex-col gap-2">
                  <InsightCard v={v} />
                  <div className="card p-3">
                    <Bar items={items} height={150} ariaLabel={aria} format={(x) => `${num(x, 0)}%`} />
                    <ChartTable caption={aria} head={[t("wasde.h.my"), t("stu.head.stu")]} rows={items.map((x) => [x.label, `${num(x.value, 2)}%`])} />
                  </div>
                </div>
              );
            })}
          </div>
        </Chapter>
      )}

      {w34.length > 0 && (
        <Chapter n={3} id="h-w-rev" eyebrow="wasde.c3.eb" title="wasde.c3">
          <div className="grid-fit-240">
            {views(w34).map(({ v }) => (
              <InsightCard key={v.id} v={v} />
            ))}
          </div>
        </Chapter>
      )}

      <section aria-labelledby="h-w-views" className="card flex flex-col gap-2 p-5">
        <h2 id="h-w-views" className="m-0 text-[17px] font-bold">
          <T k="wasde.views" />
        </h2>
        <p className="m-0 text-[13px] text-muted">
          <T k="wasde.viewsNote" />
        </p>
        <div className="flex flex-wrap gap-x-5">
          {pills.map((p) => (
            <Link key={p.id} href={`/commodity/${p.id}/`} className="inline-flex min-h-11 items-center font-semibold text-link">
              <CommodityName id={p.id} fallback={p.label} /> →
            </Link>
          ))}
          <Link href="/data/#report-wasde" className="inline-flex min-h-11 items-center text-link">
            <T k="reports.data" />
          </Link>
        </div>
      </section>
    </>
  );
}
