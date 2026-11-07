"use client";

import { useCallback } from "react";

import EChart, { axisCommon, baseOption, type Tokens } from "@/components/EChart";
import { decimals, flagLabel, num } from "@/lib/format";
import type { Series } from "@/lib/types";

export default function StocksToUseChart({ series }: { series: Series }) {
  const hist = series.stocks_to_use_history.filter((h) => h.stocks_to_use_pct !== null);

  const option = useCallback(
    (t: Tokens) => {
      const finals = hist.filter((h) => h.status === "final").map((h) => h.stocks_to_use_pct as number);
      const sorted = [...finals].sort((a, b) => a - b);
      const median = sorted.length ? sorted[Math.floor(sorted.length / 2)] : null;
      const d = decimals(series.unit, hist.at(-1)?.ending_stocks ?? 0);
      return {
        ...baseOption(t),
        grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
        tooltip: {
          ...baseOption(t).tooltip,
          trigger: "item",
          formatter: (p: { dataIndex: number }) => {
            const h = hist[p.dataIndex];
            return `<b>${h.market_year}</b> ${h.status === "current" ? flagLabel(h.flag) : "final"}<br/>Stocks-to-use <b>${num(h.stocks_to_use_pct, 1)}%</b><br/>Ending stocks ${num(h.ending_stocks, d)} ${series.unit_label ?? ""}`;
          },
        },
        xAxis: {
          type: "category",
          data: hist.map((h) => h.market_year),
          ...axisCommon(t),
          splitLine: { show: false },
          axisLabel: { color: t.muted, fontSize: 11, interval: hist.length > 14 ? 1 : 0 },
        },
        yAxis: { type: "value", name: "%", nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisCommon(t) },
        series: [
          {
            type: "bar",
            barMaxWidth: 24,
            data: hist.map((h) => ({
              value: h.stocks_to_use_pct,
              itemStyle: {
                color: h.status === "current" ? t.series1 : t.barMuted,
                borderRadius: [4, 4, 0, 0],
              },
              label:
                h.status === "current"
                  ? { show: true, position: "top", color: t.ink, fontSize: 11, formatter: `${num(h.stocks_to_use_pct, 1)}%` }
                  : { show: false },
            })),
            markLine: median !== null
              ? {
                  silent: true,
                  symbol: "none",
                  lineStyle: { color: t.muted, width: 1, type: "solid" },
                  label: { formatter: `Median, final years: ${num(median, 1)}%`, color: t.ink2, fontSize: 10, position: "insideEndTop", backgroundColor: t.surface, padding: [2, 4] },
                  data: [{ yAxis: median }],
                }
              : undefined,
          },
        ],
      };
    },
    [hist, series.unit, series.unit_label],
  );

  if (!hist.length) return <p className="text-sm text-muted">Stocks-to-use is not available for this region.</p>;
  return (
    <>
      <EChart option={option} height={300} ariaLabel="Stocks-to-use ratio by marketing year" />
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-xs text-muted">Show as table</summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <table className="w-full text-xs">
            <thead className="text-muted">
              <tr>
                <th className="text-left font-normal">Marketing year</th>
                <th className="text-right font-normal">Ending stocks</th>
                <th className="text-right font-normal">Stocks-to-use</th>
                <th className="text-right font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {hist.map((h) => (
                <tr key={h.market_year} className="border-t border-line">
                  <td>{h.market_year}</td>
                  <td className="tabular text-right">{num(h.ending_stocks, decimals(series.unit, h.ending_stocks ?? 0))}</td>
                  <td className="tabular text-right">{num(h.stocks_to_use_pct, 1)}%</td>
                  <td className="text-right">{h.status === "current" ? flagLabel(h.flag) : "final"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
