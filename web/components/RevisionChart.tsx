"use client";

import { useState } from "react";

import { useLang, useT } from "@/components/chrome/I18n";
import EChart, { axisCommon, baseOption, type Tokens } from "@/components/EChart";
import { decimals, monthOf, num } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import type { Series } from "@/lib/types";

const ATTRS = ["ending_stocks", "production", "stocks_to_use_pct", "exports", "domestic_total", "yield"] as const;

export default function RevisionChart({ series }: { series: Series }) {
  const t0 = useT();
  const { lang } = useLang();
  const label = (a: string) => t0(`rc.attr.${a}` as Key);
  // cycle month 0 = May of the marketing-year start; +1y after twelve months
  const cycle = (m: number) => `${monthOf(((m + 4) % 12) + 1, "short", lang)}${m >= 12 ? ` +${Math.floor(m / 12)}${lang === "pt" ? "a" : "y"}` : ""}`;
  const monthText = (m: string) => `${monthOf(Number(m.slice(5, 7)), "short", lang)} ${m.slice(0, 4)}`;
  const ATTR_LABEL = Object.fromEntries(ATTRS.map((a) => [a, label(a)])) as Record<string, string>;
  const attrs = ATTRS.filter((a) => series.revisions[a]?.length) as string[];
  const [attr, setAttr] = useState("ending_stocks");
  const active = attrs.includes(attr) ? attr : attrs[0];
  const lines = series.revisions[active] ?? [];

  // The React compiler memoizes this callback on its inputs (lines, unit, language).
  const option = (t: Tokens) => {
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
            const head = `<b>${cycle(ps[0].value[0])}</b> · ${t0("rc.month", { m: ps[0].value[0] })}`;
            const rows = [...ps]
              .reverse()
              .map(
                (p) =>
                  `<span style="display:inline-block;width:8px;height:8px;border-radius:4px;background:${p.color};margin-right:6px"></span>${p.seriesName}: <b>${num(p.value[1], d)}</b> <span style="color:${t.muted}">(${monthText(p.value[2])})</span>`,
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
          axisLabel: { color: t.muted, fontSize: 11, hideOverlap: true, formatter: (v: number) => cycle(v) },
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
                    label: { formatter: t0("rc.projEst"), color: t.muted, fontSize: 10, position: "insideEndTop" },
                    data: [{ xAxis: 12 }],
                  }
                : undefined,
          };
        }),
      };
    };

  if (!attrs.length) return <p className="text-sm text-muted">{t0("rc.none")}</p>;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1" role="tablist" aria-label={t0("rc.tabs")}>
        {attrs.map((a) => (
          <button
            key={a}
            type="button"
            role="tab"
            aria-selected={a === active}
            onClick={() => setAttr(a)}
            className={`min-h-11 rounded-full px-3 text-xs font-semibold ${a === active ? "bg-[var(--pill-active)] text-white" : "border border-line text-ink hover:bg-nav-active"}`}
          >
            {ATTR_LABEL[a]}
          </button>
        ))}
      </div>
      <EChart option={option} height={380} ariaLabel={t0("rc.aria", { attr: ATTR_LABEL[active] })} />
      <p className="mt-2 text-xs text-muted">{t0("rc.note")}</p>
    </div>
  );
}
