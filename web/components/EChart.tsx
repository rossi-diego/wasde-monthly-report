"use client";

import { BarChart, CustomChart, LineChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef, useState } from "react";

echarts.use([
  LineChart,
  BarChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  AriaComponent,
  SVGRenderer,
]);

export type Tokens = Record<
  | "surface"
  | "ink"
  | "ink2"
  | "muted"
  | "grid"
  | "axis"
  | "series1"
  | "series2"
  | "context"
  | "up"
  | "down"
  | "neutral"
  | "barMuted",
  string
>;

const VARS: Record<keyof Tokens, string> = {
  surface: "--surface",
  ink: "--ink",
  ink2: "--ink-2",
  muted: "--muted",
  grid: "--grid",
  axis: "--axis",
  series1: "--series-1",
  series2: "--series-2",
  context: "--context",
  up: "--up",
  down: "--down",
  neutral: "--neutral",
  barMuted: "--bar-muted",
};

function readTokens(): Tokens {
  const cs = getComputedStyle(document.documentElement);
  return Object.fromEntries(
    Object.entries(VARS).map(([k, v]) => [k, cs.getPropertyValue(v).trim()]),
  ) as Tokens;
}

/** Re-reads CSS tokens whenever the theme (OS or toggle) changes. */
export function useTokens(): Tokens | null {
  const [tokens, setTokens] = useState<Tokens | null>(null);
  useEffect(() => {
    const update = () => setTokens(readTokens());
    update();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      mq.removeEventListener("change", update);
      mo.disconnect();
    };
  }, []);
  return tokens;
}

/** Shared recessive chrome: hairline solid grid, muted axis text, tooltip on surface. */
export function baseOption(t: Tokens) {
  return {
    animationDuration: 300,
    textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif", color: t.ink2 },
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.grid,
      borderWidth: 1,
      textStyle: { color: t.ink, fontSize: 12 },
      extraCssText: "border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.12);",
    },
    aria: { enabled: true },
  };
}

export const axisCommon = (t: Tokens) => ({
  axisLine: { lineStyle: { color: t.axis } },
  axisTick: { show: false },
  axisLabel: { color: t.muted, fontSize: 11 },
  splitLine: { lineStyle: { color: t.grid, width: 1, type: "solid" as const } },
});

type Props = {
  option: (t: Tokens) => echarts.EChartsCoreOption;
  height?: number;
  ariaLabel: string;
};

export default function EChart({ option, height = 320, ariaLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const tokens = useTokens();

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    if (chart.current && tokens) chart.current.setOption(option(tokens), { notMerge: true });
  }, [option, tokens]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
