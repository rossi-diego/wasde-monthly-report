"use client";

import { useRef, useState } from "react";

import BalanceSheet from "@/components/BalanceSheet";
import Bar from "@/components/charts/Bar";
import { ChartTable } from "@/components/charts/common";
import MultiLine from "@/components/charts/MultiLine";
import Waterfall from "@/components/charts/Waterfall";
import { T, useT } from "@/components/chrome/I18n";
import TopBar, { CommodityPills, type Pill, type ReleaseInfo } from "@/components/chrome/TopBar";
import Delta from "@/components/Delta";
import Explore from "@/components/Explore";
import { decimals, flagLabel, monthLabel, num, unitShort } from "@/lib/format";
import { revView, seriesNoun, stuView, waterfallView } from "@/lib/insights";
import type { CommodityIndex, Series } from "@/lib/types";

type Entry = CommodityIndex[number];

const ATTR_LABEL: Record<string, string> = {
  ending_stocks: "Ending stocks",
  production: "Production",
  stocks_to_use_pct: "Stocks-to-use %",
  exports: "Exports",
  domestic_total: "Domestic use",
  yield: "Yield",
};

function Tabs<V extends string>({ label, items, value, onChange }: { label: string; items: { id: V; label: string }[]; value: V; onChange: (v: V) => void }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1">
      {items.map((it) => (
        <button
          key={it.id}
          type="button"
          aria-pressed={it.id === value}
          onClick={() => onChange(it.id)}
          className={`min-h-11 cursor-pointer rounded-full px-3 text-xs font-semibold ${
            it.id === value ? "bg-[var(--pill-active)] text-white" : "border border-line text-ink hover:bg-nav-active"
          }`}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

function Stat({ title, value, children }: { title: React.ReactNode; value: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="card p-4">
      <p className="m-0 text-[13px] text-muted">{title}</p>
      <p className="mono m-0 mt-1 text-[28px] font-semibold">{value}</p>
      <p className="m-0 text-[13px]">{children}</p>
    </div>
  );
}

export default function CommodityView({
  entry,
  initial,
  release,
  pills,
}: {
  entry: Entry;
  initial: Series;
  release: ReleaseInfo;
  pills: Pill[];
}) {
  const t = useT();
  const [region, setRegion] = useState("united_states");
  const [series, setSeries] = useState<Series>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attr, setAttr] = useState("ending_stocks");
  const [drvMy, setDrvMy] = useState<string | null>(null);
  const latestRequest = useRef(0);

  const selectRegion = (next: string) => {
    setRegion(next);
    if (next === series.region) return;
    const id = ++latestRequest.current; // ignore responses that arrive out of order
    setLoading(true);
    setError(null);
    fetch(`/data/commodities/${entry.id}/${next}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Series>;
      })
      .then((s) => {
        if (id !== latestRequest.current) return;
        setSeries(s);
        setDrvMy(null);
      })
      .catch((e: Error) => id === latestRequest.current && setError(`Could not load ${next}: ${e.message}`))
      .finally(() => id === latestRequest.current && setLoading(false));
  };

  const what = seriesNoun(entry.id, series.region_label, entry.label);
  const esRow = series.balance_sheet.rows.find((r) => r.id === "ending_stocks");
  const suRow = series.balance_sheet.rows.find((r) => r.id === "stocks_to_use_pct");
  const cols = series.balance_sheet.columns;
  const n = cols.length - 1;
  const newCrop = cols[n];
  const es = esRow?.values[n];
  const su = suRow?.values[n];
  const d = decimals(series.unit, es?.value ?? 0);
  const stu = stuView(series);

  const attrs = Object.keys(ATTR_LABEL).filter((a) => series.revisions[a]?.length);
  const activeAttr = attrs.includes(attr) ? attr : attrs[0];
  const rev = activeAttr ? revView(series, activeAttr, 5, 23) : null;
  const revUnit = activeAttr === "stocks_to_use_pct" ? "%" : activeAttr === "yield" ? "" : (series.unit_label ?? "");

  const drvYears = series.drivers.map((x) => x.market_year);
  const activeMy = drvMy && drvYears.includes(drvMy) ? drvMy : drvYears[drvYears.length - 1];
  const wf = waterfallView(series, activeMy, series.previous_report_month);
  const dim = loading ? "opacity-60" : "";
  const stuRank = stu.now !== null && stu.n >= 5 ? t("tight.rank", { k: stu.k, n: stu.n }) : null;

  return (
    <>
      <TopBar
        title={
          <>
            {entry.label} <span className="text-muted">· {series.region_label}</span>
          </>
        }
        release={release}
      >
        <CommodityPills pills={pills} active={entry.id} />
      </TopBar>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="m-0 text-[13px] text-muted">
          {monthLabel(series.report_month)} WASDE · {series.unit_label}
        </p>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">
            <T k="commodity.region" />
          </span>
          <select
            value={region}
            onChange={(e) => selectRegion(e.target.value)}
            className="min-h-11 rounded-lg border border-line bg-card px-3 text-ink"
          >
            {entry.regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="card m-0 p-3 text-sm text-down">
          {error}
        </p>
      )}

      <section aria-label="Key numbers" className={`grid-fit-220 ${dim}`}>
        <Stat title={`Ending stocks ${newCrop?.market_year ?? ""} ${flagLabel(newCrop?.flag)}`} value={num(es?.value, d)}>
          <Delta value={es?.delta} digits={d} /> <span className="text-muted">vs last month · {unitShort(series.unit)}</span>
        </Stat>
        <Stat title={`Stocks-to-use ${newCrop?.market_year ?? ""}`} value={`${num(su?.value, 1)}%`}>
          <Delta value={su?.delta} digits={1} suffix=" pt" /> <span className="text-muted">vs last month</span>
        </Stat>
        <Stat title="Where it sits in history" value={stuRank ? `${stu.k} of ${stu.n}` : "—"}>
          <span className="text-muted">{stuRank ? "past seasons were tighter (final values)" : "Needs at least 5 completed seasons"}</span>
        </Stat>
        <Stat title={`Old crop ${cols[n - 1]?.market_year ?? ""}`} value={num(esRow?.values[n - 1]?.value, d)}>
          <Delta value={esRow?.values[n - 1]?.delta} digits={d} /> <span className="text-muted">ending stocks vs last month</span>
        </Stat>
      </section>

      <div className={`grid-fit-380 items-start ${dim}`}>
        <section className="card min-w-0 p-5" aria-labelledby="h-bs">
          <div className="eyebrow">WASDE · balance sheet</div>
          <h2 id="h-bs" className="m-0 text-[17px] font-bold">
            <T k="commodity.bs" />
          </h2>
          <p className="mb-4 mt-1 text-[13px] text-muted">
            {series.unit_label} · change vs {series.previous_report_month ? monthLabel(series.previous_report_month) : "previous report"} under each value
          </p>
          <BalanceSheet series={series} />
        </section>

        <section className="card flex min-w-0 flex-col gap-2 p-5" aria-labelledby="h-drv">
          <div>
            <div className="eyebrow">WASDE · why stocks moved</div>
            <h2 id="h-drv" className="m-0 text-[17px] font-bold">
              <T k="commodity.drivers" />
            </h2>
          </div>
          {drvYears.length > 0 && <Tabs label="Marketing year" items={drvYears.map((y) => ({ id: y, label: y }))} value={activeMy} onChange={setDrvMy} />}
          {wf ? (
            <>
              <Waterfall steps={wf.steps} ariaLabel={`${what}. ${wf.aria}`} format={(v) => num(v, wf.digits)} />
              <p className="m-0 text-xs text-muted">
                Each bar is a line&apos;s effect on ending stocks: more domestic use or exports lowers stocks, so they appear with the opposite sign of the balance-sheet change.
              </p>
              <ChartTable caption={wf.aria} head={["Step", `Effect on ending stocks (${unitShort(series.unit)})`]} rows={wf.rows} />
            </>
          ) : (
            <p className="py-12 text-center text-sm text-muted">
              <T k="wf.none" />
            </p>
          )}
        </section>
      </div>

      <section className={`card flex flex-col gap-2 p-5 ${dim}`} aria-labelledby="h-rev">
        <div>
          <div className="eyebrow">WASDE · how USDA&apos;s view evolved</div>
          <h2 id="h-rev" className="m-0 text-[17px] font-bold">
            <T k="commodity.revisions" />
          </h2>
        </div>
        {attrs.length > 0 && (
          <Tabs label="Balance-sheet line" items={attrs.map((a) => ({ id: a, label: ATTR_LABEL[a] }))} value={activeAttr} onChange={setAttr} />
        )}
        {rev ? (
          <>
            <MultiLine
              lines={rev.lines}
              xMax={rev.xMax}
              xTicks={rev.xTicks}
              height={260}
              ariaLabel={`Revision paths of ${what} ${ATTR_LABEL[activeAttr].toLowerCase()} for ${rev.firstMy} to ${rev.lastMy}; the ${rev.lastMy} value has moved between ${num(rev.curMin, rev.digits)} and ${num(rev.curMax, rev.digits)} since ${rev.since}.`}
              format={(v) => num(v, rev.digits > 1 ? 1 : rev.digits)}
            />
            <p className="m-0 text-xs text-muted">
              {revUnit ? `${revUnit}. ` : ""}Month 0 is the first projection in May; after 12 months the projection becomes an estimate. Blue: {rev.lastMy}; grey: {rev.greyFrom}–{rev.greyTo}.
            </p>
            <ChartTable caption={`${what} ${ATTR_LABEL[activeAttr]} revision paths`} head={rev.head} rows={rev.rows} />
          </>
        ) : (
          <p className="text-sm text-muted">No revision history for this region.</p>
        )}
      </section>

      <section className={`card flex flex-col gap-2 p-5 ${dim}`} aria-labelledby="h-su">
        <div className="flex flex-wrap justify-between gap-2">
          <div>
            <div className="eyebrow">WASDE · tight or loose?</div>
            <h2 id="h-su" className="m-0 text-[17px] font-bold">
              <T k="commodity.stu" />
            </h2>
          </div>
          {stu.now !== null && (
            <div className="text-right">
              <div className="mono text-xl font-semibold">{num(stu.now, 1)}%</div>
              {stuRank && <div className="text-xs text-muted">{stuRank}</div>}
            </div>
          )}
        </div>
        {stu.bars.length ? (
          <>
            <Bar
              items={stu.bars}
              ariaLabel={`${what} stocks-to-use by marketing year, ${stu.from} to ${stu.to}; ${stu.nowMy} ${num(stu.now, 1)}%${stuRank ? `; ${stuRank}` : ""}.`}
              format={(v) => `${num(v, 0)}%`}
            />
            <p className="m-0 text-xs text-muted">
              Grey: final value of completed seasons; blue: {stu.nowMy} projection{stu.estMy ? `; mid-tone: ${stu.estMy} estimate` : ""}. n = {stu.n} final seasons.
              {series.region === "world" || series.region === "world_less_china"
                ? " World: ending stocks ÷ domestic use."
                : " Ending stocks ÷ total use (domestic + exports)."}
            </p>
            <ChartTable caption={`${what} stocks-to-use history`} head={["Marketing year", "Stocks-to-use", "Ending stocks", "Status"]} rows={stu.rows} />
          </>
        ) : (
          <p className="text-sm text-muted">Stocks-to-use is not available for this region.</p>
        )}
      </section>

      <Explore series={series} />
    </>
  );
}
