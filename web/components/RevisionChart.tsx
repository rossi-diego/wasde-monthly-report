"use client";

import { useCallback, useMemo, useState } from "react";

import EChart, { axisCommon, baseOption, type Tokens } from "@/components/EChart";
import { CYCLE_LABEL, decimals, monthLabel, num } from "@/lib/format";
import type { Series } from "@/lib/types";

const ATTR_LABEL: Record<string, string> = {
  ending_stocks: "Ending stocks",
  production: "Production",
  stocks_to_use_pct: "Stocks-to-use %",
  exports: "Exports",
  domestic_total: "Domestic use",
  yield: "Yield",
};

export default function RevisionChart({ series }: { series: Series }) {
  const attrs = Object.keys(ATTR_LABEL).filter((a) => series.revisions[a]?.length);
  const [attr, setAttr] = useState("ending_stocks");
  const active = attrs.includes(attr) ? attr : attrs[0];
  const lines = useMemo(() => series.revisions[active] ?? [], [series, active]);

  const option = useCallback(
    (t: Tokens) => {
      const n = lines.length;
      const unit = active === "stocks_to_use_pct" ? "%" : active === "yield" ? "" : series.unit_label ?? "";
      const sample = lines.at(-1)?.points.at(-1)?.[1] ?? 0;
      const d = active === "stocks_to_use_pct" || active === "yield" ? 1 : decimals(series.unit, sample);
      const colorFor = (i: number) => (i === n - 1 ? t.series1 : i === n - 2 ? t.series2 : t.context);
      const maxX = Math.min(24, Math.max(12, ...lines.flatMap((l) => l.points.map((p) => p[0] ?? 0))));
      return {
        ...baseOption(t),
        grid: { left: 8, right: 64, top: 40, bottom: 8, containLabel: true },
        legend: {
          top: 0,
          left: 0,
          icon: "roundRect",
          itemWidth: 14,
          itemHeight: 3,
          textStyle: { color: t.ink2, fontSize: 11 },
          data: lines.slice(-2).map((l) => l.market_year).reverse(),
        },
        tooltip: {
          ...baseOption(t).tooltip,
          trigger: "axis",
          axisPointer: { type: "line", lineStyle: { color: t.axis, width: 1 } },
          formatter: (ps: { seriesName: string; value: [number, number, string]; color: string }[]) => {
            if (!ps.length) return "";
            const head = `<b>${CYCLE_LABEL(ps[0].value[0])}</b> · month ${ps[0].value[0]} of the cycle`;
            const rows = [...ps]
              .reverse()
              .map(
                (p) =>
                  `<span style="display:inline-block;width:8px;height:8px;border-radius:4px;background:${p.color};margin-right:6px"></span>${p.seriesName}: <b>${num(p.value[1], d)}</b> <span style="color:${t.muted}">(${monthLabel(p.value[2], "short")})</span>`,
              )
              .join("<br/>");
            return `${head}<br/>${rows}`;
          },
        },
        xAxis: {
          type: "value",
          min: 0,
          max: maxX,
          interval: 3,
          ...axisCommon(t),
          splitLine: { show: false },
          axisLabel: { color: t.muted, fontSize: 11, formatter: (v: number) => CYCLE_LABEL(v) },
        },
        yAxis: {
          type: "value",
          scale: true,
          name: unit,
          nameTextStyle: { color: t.muted, fontSize: 11, align: "left" },
          ...axisCommon(t),
        },
        series: lines.map((l, i) => {
          const isKey = i >= n - 2;
          return {
            name: l.market_year,
            type: "line",
            data: l.points
              .filter((p) => p[0] !== null && p[1] !== null && (p[0] as number) <= 24)
              .map((p) => [p[0], p[1], p[2]]),
            showSymbol: false,
            symbolSize: 8,
            lineStyle: { width: isKey ? 2.5 : 1.5, color: colorFor(i), cap: "round", join: "round" },
            itemStyle: { color: colorFor(i), borderColor: t.surface, borderWidth: 2 },
            z: isKey ? 3 : 1,
            emphasis: { focus: "series" },
            endLabel: isKey
              ? { show: true, formatter: "{a}", color: t.ink2, fontSize: 11, distance: 6 }
              : undefined,
            markLine:
              i === n - 1
                ? {
                    silent: true,
                    symbol: "none",
                    lineStyle: { color: t.axis, width: 1, type: "solid" },
                    label: { formatter: "Proj. → Est.", color: t.muted, fontSize: 10, position: "insideEndTop" },
                    data: [{ xAxis: 12 }],
                  }
                : undefined,
          };
        }),
      };
    },
    [lines, active, series.unit, series.unit_label],
  );

  if (!attrs.length) return <p className="text-sm text-muted">No revision history for this region.</p>;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1" role="tablist" aria-label="Balance-sheet line">
        {attrs.map((a) => (
          <button
            key={a}
            type="button"
            role="tab"
            aria-selected={a === active}
            onClick={() => setAttr(a)}
            className={`rounded-full px-3 py-1 text-xs ${a === active ? "bg-accent text-white" : "border border-line text-ink-2 hover:bg-surface-2"}`}
          >
            {ATTR_LABEL[a]}
          </button>
        ))}
      </div>
      <EChart option={option} height={380} ariaLabel={`${ATTR_LABEL[active]} revision paths by marketing year`} />
      <p className="mt-2 text-xs text-muted">
        Blue = current marketing year, orange = previous, gray = the six years before. Hover to compare years at the same point
        of the season.
      </p>
    </div>
  );
}
