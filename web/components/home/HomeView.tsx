"use client";

import Link from "next/link";
import { useState } from "react";

import Bar from "@/components/charts/Bar";
import { ChartTable } from "@/components/charts/common";
import MultiLine from "@/components/charts/MultiLine";
import Sparkline from "@/components/charts/Sparkline";
import Waterfall from "@/components/charts/Waterfall";
import { T, useT } from "@/components/chrome/I18n";
import TopBar, { CommodityPills, type ReleaseInfo } from "@/components/chrome/TopBar";
import DataStrip from "@/components/home/DataStrip";
import Upcoming from "@/components/home/Upcoming";
import type { CommodityPanel, HomeData } from "@/lib/dashboard";
import { num } from "@/lib/format";

function CardHead({ eyebrow, title, id, right }: { eyebrow: React.ReactNode; title: React.ReactNode; id: string; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0 flex-[1_1_220px]">
        <div className="eyebrow">{eyebrow}</div>
        <h2 id={id} className="m-0 mt-0.5 text-[17px] font-bold">
          {title}
        </h2>
      </div>
      {right}
    </div>
  );
}

function Swatch({ color }: { color: string }) {
  return <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: color }} />;
}

function TightOrLoose({ p }: { p: CommodityPanel }) {
  const t = useT();
  const s = p.stu;
  const rank = s.now !== null && s.n >= 5 ? t("tight.rank", { k: s.k, n: s.n }) : null;
  const aria = `${p.what} stocks-to-use by marketing year, ${s.from} to ${s.to}; ${s.nowMy} projection ${num(s.now, 1)}%${rank ? `; ${rank}` : ""}.`;
  return (
    <article aria-labelledby="h-tight" className="card flex min-w-0 flex-col gap-2 p-5">
      <CardHead
        id="h-tight"
        eyebrow={<T k="tight.eyebrow" />}
        title={<T k="tight.title" v={{ what: p.what, from: s.from, to: s.to }} />}
        right={
          <div className="text-right">
            <div className="mono text-xl font-semibold">{num(s.now, 1)}%</div>
            {rank && (
              <div className="text-xs text-muted" data-testid="stu-rank">
                {rank}
              </div>
            )}
          </div>
        }
      />
      <Bar items={s.bars} ariaLabel={aria} format={(v) => `${num(v, 0)}%`} />
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <Swatch color="var(--bar-past)" />
          <T k="tight.legendPast" />
        </span>
        {s.estMy && (
          <span className="flex items-center gap-1.5">
            <Swatch color="var(--bar-est)" />
            <T k="tight.legendEst" v={{ my: s.estMy }} />
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <Swatch color="var(--wasde)" />
          <T k="tight.legendProj" v={{ my: s.nowMy ?? "" }} />
        </span>
        <span>
          <T k="tight.n" v={{ n: s.n }} />
          {s.n < 10 && (
            <>
              {" · "}
              <T k="tight.small" />
            </>
          )}
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ChartTable caption={aria} head={["Marketing year", "Stocks-to-use", "Ending stocks", "Status"]} rows={s.rows} />
        <Link href={`/commodity/${p.id}/`} className="inline-flex min-h-11 items-center text-[13px] font-semibold text-link">
          <T k="tight.open" v={{ label: p.label }} />
        </Link>
      </div>
    </article>
  );
}

function RevisionPath({ p }: { p: CommodityPanel }) {
  const r = p.rev;
  if (!r) return null;
  const aria = `Revision paths of ${p.what} ending stocks for ${r.firstMy} to ${r.lastMy}. The ${r.lastMy} estimate has moved between ${num(r.curMin, r.digits)} and ${num(r.curMax, r.digits)} ${p.unitLabel.toLowerCase()} since ${r.since}.`;
  return (
    <article aria-labelledby="h-rev" className="card flex min-w-0 flex-col gap-2 p-5">
      <CardHead id="h-rev" eyebrow={<T k="rev.eyebrow" />} title={<T k="rev.title" v={{ what: p.what }} />} />
      <MultiLine lines={r.lines} xMax={r.xMax} xTicks={r.xTicks} ariaLabel={aria} format={(v) => num(v, 0)} />
      <div className="text-xs text-muted">
        <T k="rev.note" v={{ unit: p.unitLabel, from: r.greyFrom, to: r.greyTo }} />
      </div>
      <ChartTable caption={aria} head={r.head} rows={r.rows} />
    </article>
  );
}

export default function HomeView({ data, release, pills }: { data: HomeData; release: ReleaseInfo; pills: { id: string; label: string }[] }) {
  const t = useT();
  const [sel, setSel] = useState(data.defaultCommodity);
  const panel = data.panels.find((p) => p.id === sel) ?? data.panels[0];
  const wf = data.waterfall;
  const panelPills = pills.filter((p) => data.panels.some((x) => x.id === p.id));

  return (
    <>
      <TopBar title={<T k="home.title" v={{ month: data.month }} />} release={release}>
        <CommodityPills pills={panelPills} active={panel?.id} onPick={setSel} />
      </TopBar>

      <section aria-label={t("home.kpis")} className="grid-fit-220">
        {data.kpis.map((k) => (
          <article
            key={k.id}
            data-testid="kpi"
            className="box-border flex min-h-[150px] flex-col gap-1.5 rounded-2xl p-[18px] text-white"
            style={{ background: k.color }}
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="m-0 text-[13px] font-semibold">{k.title}</h2>
              <span className="rounded-[10px] bg-black/20 px-2 py-[3px] text-[11px] font-semibold">{k.tag}</span>
            </div>
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="mono text-[30px] font-semibold tracking-[-0.02em]">{k.value}</span>
              <span className="text-[13px]">{k.unit}</span>
            </div>
            <div className="text-[13px] font-semibold">
              {k.dir === "flat"
                ? t("kpi.unch", { month: data.prevMonth })
                : t(k.dir === "up" ? "kpi.up" : "kpi.down", { v: k.deltaAbs, month: data.prevMonth })}
              {k.dir !== "flat" && k.deltaPct ? ` (${k.deltaPct})` : ""}
            </div>
            <div className="mt-auto flex items-end justify-between gap-2">
              <span className="text-xs">{k.contextKind === "stu" ? t("kpi.stu", { v: k.context }) : k.context}</span>
              <Sparkline values={k.spark} ariaLabel={t("kpi.spark", k.sparkLabel)} />
            </div>
          </article>
        ))}
      </section>

      {panel && (
        <div className="grid-fit-380">
          <TightOrLoose p={panel} />
          <RevisionPath p={panel} />
        </div>
      )}

      <div className="grid-fit-380">
        {wf && (
          <article aria-labelledby="h-wf" className="card flex min-w-0 flex-col gap-2 p-5">
            <CardHead
              id="h-wf"
              eyebrow={<T k="wf.eyebrow" />}
              title={`${wf.what} ${wf.marketYear} ending stocks: ${num(wf.from, wf.digits)} → ${num(wf.to, wf.digits)} ${wf.unit}`}
            />
            <Waterfall steps={wf.steps} ariaLabel={wf.aria} format={(v) => num(v, wf.digits)} />
            <div className="text-xs text-muted">
              <T k="wf.note" v={{ now: wf.stuNow, prev: wf.stuPrev, month: data.prevMonth, k: wf.k, n: wf.n }} />
            </div>
            <ChartTable caption={wf.aria} head={["Step", `Effect on ending stocks (${wf.unit})`]} rows={wf.rows} />
          </article>
        )}

        <article aria-labelledby="h-chg" className="card flex min-w-0 flex-col gap-2.5 p-5">
          <CardHead
            id="h-chg"
            eyebrow={<T k="chg.eyebrow" />}
            title={<T k="chg.title" v={{ month: data.prevMonth }} />}
            right={
              data.downloads.excel ? (
                <a href={data.downloads.excel} download className="inline-flex min-h-11 items-center text-[13px] font-semibold text-link">
                  <T k="chg.all" />
                </a>
              ) : undefined
            }
          />
          <ol className="m-0 list-none p-0">
            {data.changes.map((c) => (
              <li
                key={c.key}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-line py-2.5"
              >
                <Link href={`/commodity/${c.commodity}/`} className="font-semibold">
                  {c.what}
                </Link>
                <div className={`mono text-right font-semibold ${c.dir === "up" ? "text-up" : c.dir === "down" ? "text-down" : "text-muted"}`}>
                  {c.delta}
                </div>
                <div className="text-xs text-muted">
                  {c.dir === "up" ? "Raised" : c.dir === "down" ? "Cut" : "Unchanged"} to {c.to}
                  {c.extra.map((e) => ` · ${e}`).join("")}
                </div>
                <div aria-hidden="true" className="h-1.5 w-[120px] overflow-hidden rounded-[3px] bg-grid">
                  <div
                    className="h-1.5 rounded-[3px]"
                    style={{ width: `${Math.round(c.frac * 120)}px`, background: c.dir === "down" ? "var(--down)" : "var(--up)" }}
                  />
                </div>
              </li>
            ))}
          </ol>
          <p className="m-0 text-xs text-muted">
            <T k="chg.bar" />
          </p>
        </article>
      </div>

      <Upcoming />

      <DataStrip links={data.downloads} history={data.history} />
    </>
  );
}
