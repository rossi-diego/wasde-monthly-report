"use client";

import { useCallback, useState } from "react";

import EChart, { axisCommon, baseOption, type Tokens } from "@/components/EChart";
import { decimals, num } from "@/lib/format";
import type { Series } from "@/lib/types";

export default function DriversWaterfall({ series }: { series: Series }) {
  const drivers = series.drivers;
  const [idx, setIdx] = useState(drivers.length - 1);
  const drv = drivers[Math.min(idx, drivers.length - 1)];

  const option = useCallback(
    (t: Tokens) => {
      if (!drv) return {};
      const d = decimals(series.unit, drv.to ?? 0);
      const comps = drv.components.filter((c) => c.value !== null && Math.abs(c.value) > 1e-9);
      const SHORT: Record<string, string> = {
        beginning_stocks: "Beg. stocks",
        production: "Production",
        production_area: "Area",
        production_yield: "Yield",
        imports: "Imports",
        domestic_total: "Dom. use",
        exports: "Exports",
        other: "Other",
      };
      const labels = ["Last month", ...comps.map((c) => SHORT[c.id] ?? c.label), "This month"];
      const fullLabels = ["Last month", ...comps.map((c) => c.label), "This month"];
      // Floating bars: invisible base + visible magnitude, starting from last month's stocks.
      const base: (number | string)[] = [0];
      const vis: { value: number; itemStyle: { color: string; borderRadius: number[] } }[] = [
        { value: drv.from ?? 0, itemStyle: { color: t.neutral, borderRadius: [4, 4, 0, 0] } },
      ];
      let level = drv.from ?? 0;
      for (const c of comps) {
        const v = c.value ?? 0;
        base.push(v >= 0 ? level : level + v);
        vis.push({ value: Math.abs(v), itemStyle: { color: v >= 0 ? t.up : t.down, borderRadius: [4, 4, 4, 4] } });
        level += v;
      }
      base.push(0);
      vis.push({ value: drv.to ?? level, itemStyle: { color: t.neutral, borderRadius: [4, 4, 0, 0] } });
      const signedVals = [drv.from ?? 0, ...comps.map((c) => c.value ?? 0), drv.to ?? 0];
      // Domain from the running stock levels (not from 0): the change is the story, not the level.
      const levels = [drv.from ?? 0];
      for (const c of comps) levels.push(levels[levels.length - 1] + (c.value ?? 0));
      levels.push(drv.to ?? 0);
      const lo = Math.min(...levels);
      const hi = Math.max(...levels);
      const span = Math.max(hi - lo, Math.abs(hi) * 0.02, 1);
      const step = 10 ** Math.floor(Math.log10(span / 2));
      const axisMin = Math.floor((lo - span * 0.6) / step) * step;
      const axisMax = Math.ceil((hi + span * 0.25) / step) * step;
      return {
        ...baseOption(t),
        grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
        tooltip: {
          ...baseOption(t).tooltip,
          trigger: "axis",
          axisPointer: { type: "shadow", shadowStyle: { color: "rgba(127,127,127,0.08)" } },
          formatter: (p: { dataIndex: number }[]) => {
            const i = p[1]?.dataIndex ?? p[0].dataIndex;
            const v = signedVals[i];
            const total = i === 0 || i === labels.length - 1;
            if (total) return `<b>${fullLabels[i]}</b><br/>Ending stocks ${num(v, d)} ${series.unit_label ?? ""}`;
            const id = comps[i - 1]?.id;
            const flip = id === "domestic_total" || id === "exports";
            const line = flip ? `<br/><span style="color:${t.muted}">${fullLabels[i]} itself ${v < 0 ? "rose" : "fell"} by ${num(Math.abs(v), d)}</span>` : "";
            return `<b>${fullLabels[i]}</b><br/>Effect on ending stocks: ${v > 0 ? "+" : "−"}${num(Math.abs(v), d)} ${series.unit_label ?? ""}${line}`;
          },
        },
        xAxis: { type: "category", data: labels, ...axisCommon(t), splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0, rotate: labels.length > 5 ? 30 : 0, hideOverlap: false } },
        yAxis: {
          type: "value",
          ...axisCommon(t),
          min: axisMin,
          max: axisMax,
          axisLabel: { color: t.muted, fontSize: 11, formatter: (v: number) => num(v, d) },
        },
        series: [
          { type: "bar", stack: "w", data: base, itemStyle: { color: "transparent" }, emphasis: { disabled: true }, silent: true, barMaxWidth: 24 },
          {
            type: "bar",
            stack: "w",
            data: vis,
            barMaxWidth: 24,
            label: {
              show: true,
              position: "top",
              color: t.ink2,
              fontSize: 11,
              formatter: (p: { dataIndex: number }) => {
                const i = p.dataIndex;
                const v = signedVals[i];
                if (i === 0 || i === labels.length - 1) return num(v, d);
                return `${v > 0 ? "+" : "−"}${num(Math.abs(v), d)}`;
              },
            },
          },
        ],
      };
    },
    [drv, series.unit, series.unit_label],
  );

  if (!drv) return <p className="text-sm text-muted">No month-over-month comparison available.</p>;
  const unchanged = (drv.from ?? 0) === (drv.to ?? 0) && drv.components.every((c) => !c.value);
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1" role="tablist" aria-label="Marketing year">
        {drivers.map((x, i) => (
          <button
            key={x.market_year}
            type="button"
            role="tab"
            aria-selected={i === idx}
            onClick={() => setIdx(i)}
            className={`rounded-full px-3 py-1 text-xs ${i === idx ? "bg-accent text-white" : "border border-line text-ink-2 hover:bg-surface-2"}`}
          >
            {x.market_year}
          </button>
        ))}
      </div>
      {unchanged ? (
        <p className="py-16 text-center text-sm text-muted">No revision to {drv.market_year} ending stocks this month.</p>
      ) : (
        <>
          <EChart option={option} height={300} ariaLabel={`Ending stocks drivers for ${drv.market_year}`} />
          <p className="mt-1 text-xs text-muted">
            Bars show each line&apos;s effect on ending stocks: higher domestic use or exports lowers stocks, so they
            appear with the opposite sign of the balance-sheet change.
          </p>
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-xs text-muted">Show as table</summary>
            <table className="mt-2 w-full text-xs">
              <tbody>
                <tr className="border-t border-line">
                  <td className="py-1">Last month</td>
                  <td className="tabular py-1 text-right">{num(drv.from, decimals(series.unit, drv.from ?? 0))}</td>
                </tr>
                {drv.components
                  .filter((c) => c.value !== null && Math.abs(c.value) > 1e-9)
                  .map((c) => (
                    <tr key={c.id} className="border-t border-line">
                      <td className="py-1">{c.label}</td>
                      <td className="tabular py-1 text-right">
                        {(c.value ?? 0) > 0 ? "+" : "−"}
                        {num(Math.abs(c.value ?? 0), decimals(series.unit, drv.to ?? 0))}
                      </td>
                    </tr>
                  ))}
                <tr className="border-t border-line font-medium">
                  <td className="py-1">This month</td>
                  <td className="tabular py-1 text-right">{num(drv.to, decimals(series.unit, drv.to ?? 0))}</td>
                </tr>
              </tbody>
            </table>
          </details>
        </>
      )}
    </div>
  );
}
