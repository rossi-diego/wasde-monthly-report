"use client";

import { useRef, useState } from "react";

import BalanceSheet from "@/components/BalanceSheet";
import Delta from "@/components/Delta";
import DriversWaterfall from "@/components/DriversWaterfall";
import RevisionChart from "@/components/RevisionChart";
import StocksToUseChart from "@/components/StocksToUseChart";
import { decimals, flagLabel, monthLabel, num, unitShort } from "@/lib/format";
import type { CommodityIndex, Series } from "@/lib/types";

type Entry = CommodityIndex[number];

export default function CommodityView({ entry, initial }: { entry: Entry; initial: Series }) {
  const [region, setRegion] = useState("united_states");
  const [series, setSeries] = useState<Series>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      .then((s) => id === latestRequest.current && setSeries(s))
      .catch((e: Error) => id === latestRequest.current && setError(`Could not load ${next}: ${e.message}`))
      .finally(() => id === latestRequest.current && setLoading(false));
  };

  const esRow = series.balance_sheet.rows.find((r) => r.id === "ending_stocks");
  const suRow = series.balance_sheet.rows.find((r) => r.id === "stocks_to_use_pct");
  const cols = series.balance_sheet.columns;
  const n = cols.length - 1;
  const newCrop = cols[n];
  const es = esRow?.values[n];
  const su = suRow?.values[n];
  const d = decimals(series.unit, es?.value ?? 0);
  const pctile = series.stocks_to_use_percentile;

  return (
    <div className="min-w-0 space-y-8">
      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-brand">{monthLabel(series.report_month)} WASDE</p>
            <h1 className="text-3xl font-semibold tracking-tight">
              {entry.label} <span className="text-ink-2">· {series.region_label}</span>
            </h1>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">Region</span>
            <select
              value={region}
              onChange={(e) => selectRegion(e.target.value)}
              className="rounded-lg border border-line bg-surface px-3 py-2 text-ink"
            >
              {entry.regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error && <p className="rounded-lg bg-surface-2 p-3 text-sm text-down">{error}</p>}

        <div className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-4 ${loading ? "opacity-60" : ""}`}>
          <div className="card p-4">
            <p className="text-sm text-ink-2">
              Ending stocks {newCrop?.market_year} {flagLabel(newCrop?.flag)}
            </p>
            <p className="mt-1 text-3xl font-semibold">{num(es?.value, d)}</p>
            <p className="text-sm">
              <Delta value={es?.delta} digits={d} /> <span className="text-muted">vs last month · {unitShort(series.unit)}</span>
            </p>
          </div>
          <div className="card p-4">
            <p className="text-sm text-ink-2">Stocks-to-use {newCrop?.market_year}</p>
            <p className="mt-1 text-3xl font-semibold">{num(su?.value, 1)}%</p>
            <p className="text-sm">
              <Delta value={su?.delta} digits={1} suffix=" pt" /> <span className="text-muted">vs last month</span>
            </p>
          </div>
          <div className="card p-4">
            <p className="text-sm text-ink-2">Where it sits in history</p>
            <p className="mt-1 text-3xl font-semibold">{pctile === null ? "—" : `${Math.round(pctile * 100)}th`}</p>
            <p className="text-sm text-muted">
              {pctile === null
                ? "Needs ≥10 completed marketing years"
                : `percentile of stocks-to-use, ${series.n_final_years} final marketing years`}
            </p>
          </div>
          <div className="card p-4">
            <p className="text-sm text-ink-2">Old crop {cols[n - 1]?.market_year}</p>
            <p className="mt-1 text-3xl font-semibold">{num(esRow?.values[n - 1]?.value, d)}</p>
            <p className="text-sm">
              <Delta value={esRow?.values[n - 1]?.delta} digits={d} />{" "}
              <span className="text-muted">ending stocks vs last month</span>
            </p>
          </div>
        </div>
      </section>

      <div className={`grid items-start gap-6 lg:grid-cols-5 ${loading ? "opacity-60" : ""}`}>
        <section className="card min-w-0 p-5 lg:col-span-3" aria-labelledby="h-bs">
          <h2 id="h-bs" className="text-lg font-semibold">
            Balance sheet
          </h2>
          <p className="mb-4 text-sm text-muted">
            {series.unit_label} · change vs{" "}
            {series.previous_report_month ? monthLabel(series.previous_report_month) : "previous report"} under each value
          </p>
          <BalanceSheet series={series} />
        </section>
        <section className="card min-w-0 p-5 lg:col-span-2" aria-labelledby="h-drv">
          <h2 id="h-drv" className="text-lg font-semibold">
            Why ending stocks changed
          </h2>
          <p className="mb-2 text-sm text-muted">
            Month-over-month revision split into its drivers. Bars push stocks up (blue) or down (red).
          </p>
          <DriversWaterfall series={series} />
        </section>
      </div>

      <section className={`card p-5 ${loading ? "opacity-60" : ""}`} aria-labelledby="h-rev">
        <h2 id="h-rev" className="text-lg font-semibold">
          How USDA&apos;s estimate evolved
        </h2>
        <p className="mb-2 text-sm text-muted">
          Each line is one marketing year, from its first projection in May (month 0) to its last estimate — aligned so
          years compare at the same point of the season.
        </p>
        <RevisionChart series={series} />
      </section>

      <section className={`card p-5 ${loading ? "opacity-60" : ""}`} aria-labelledby="h-su">
        <h2 id="h-su" className="text-lg font-semibold">
          Stocks-to-use by marketing year
        </h2>
        <p className="mb-2 text-sm text-muted">
          Last published value for completed years; the current projection and estimate are highlighted.
          {series.region === "world" || series.region === "world_less_china"
            ? " World: ending stocks ÷ domestic use."
            : " Ending stocks ÷ total use (domestic + exports)."}
        </p>
        <StocksToUseChart series={series} />
      </section>
    </div>
  );
}
