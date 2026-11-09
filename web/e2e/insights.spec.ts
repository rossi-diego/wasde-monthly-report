import { expect, test } from "@playwright/test";

import { monthName, monthYear, shortDate } from "../lib/format";
import { kpiFromSeries } from "../lib/insights";
import type { Series } from "../lib/types";

// Pure unit tests of the derivations behind the KPI tiles (no browser page needed).

type Cell = { value: number | null; prev: number | null; delta: number | null };

function series(cell: Cell, unit = "mmt"): Series {
  return {
    unit,
    balance_sheet: {
      columns: [{ market_year: "2026/27", flag: "proj" }],
      rows: [
        { id: "ending_stocks", label: "Ending stocks", values: [cell] },
        { id: "stocks_to_use_pct", label: "Stocks-to-use (%)", values: [{ value: 28.1, prev: null, delta: null }] },
      ],
    },
    revisions: {},
  } as unknown as Series;
}

const opts = { id: "t", title: "Test", color: "red", context: "stu" as const };

test("a first projection (no previous value) is 'new', never 'unchanged'", () => {
  const k = kpiFromSeries(series({ value: 124.28, prev: null, delta: null }), "ending_stocks", "2026/27", opts);
  expect(k?.dir).toBe("new");
  expect(k?.deltaAbs).toBe("");
  expect(k?.deltaPct).toBeNull();
});

test("a null delta with a previous value is still not 'unchanged'", () => {
  const k = kpiFromSeries(series({ value: 124.28, prev: 124.02, delta: null }), "ending_stocks", "2026/27", opts);
  expect(k?.dir).toBe("new");
});

test("a zero delta is 'flat'", () => {
  const k = kpiFromSeries(series({ value: 186, prev: 186, delta: 0 }), "ending_stocks", "2026/27", opts);
  expect(k?.dir).toBe("flat");
});

test("the change keeps its published precision (MMT: +0.26, not +0.3)", () => {
  const k = kpiFromSeries(series({ value: 124.28, prev: 124.02, delta: 0.26 }), "ending_stocks", "2026/27", opts);
  expect(k?.dir).toBe("up");
  expect(k?.value).toBe("124.3");
  expect(k?.deltaAbs).toBe("0.26");
  expect(k?.deltaPct).toBe("+0.2%");
});

test("dates and months follow the language", () => {
  expect(monthYear("2026-10", "en")).toBe("October 2026");
  expect(monthYear("2026-10", "pt")).toBe("outubro de 2026");
  expect(monthName("2026-09", "long", "pt")).toBe("setembro");
  expect(shortDate("2026-10-09T00:00:00", true, "en")).toBe("Oct 9, 2026");
  expect(shortDate("2026-10-09T00:00:00", true, "pt")).toBe("9 out 2026");
  expect(shortDate("2026-11-10", false, "pt")).toBe("10 nov");
});
