import { expect, test, type Page } from "@playwright/test";

import type { CrushCommodity, CrushIndex, Insight, InsightsDoc } from "../lib/data-contract";
import { bushels, lbPerBu, share, shortDate } from "../lib/format";
import { cardView, formatParam } from "../lib/insight-text";
import { NOPA_NOTE } from "../lib/nopa";

// NASS crush (cut B): copy-vs-JSON contract for the crush card and page, the NOPA note, the
// history window, and the crush entries of /reports and /data. Skipped for a build without crush.

async function json<T>(page: Page, url: string): Promise<T | null> {
  const r = await page.request.get(url);
  return r.ok() ? ((await r.json()) as T) : null;
}

async function crush(page: Page) {
  const idx = await json<CrushIndex>(page, "/data/reports/oilseed_crush/index.json");
  if (!idx) return null;
  const d = (await json<CrushCommodity>(page, `/data/${idx.commodities[0].file}`))!;
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  return { idx, d, doc };
}

test("crush page header numbers equal the crush JSON and F1", async ({ page }) => {
  const c = await crush(page);
  test.skip(!c, "no crush data in this build");
  const { d, doc } = c!;
  await page.goto("/reports/oilseed-crush/");
  await expect(page.getByTestId("crush-month")).toHaveText(bushels(d.kpis.month_crushed_bu));
  await expect(page.getByTestId("crush-mytd")).toHaveText(bushels(d.kpis.cum_bu));
  await expect(page.getByTestId("crush-yield")).toHaveText(lbPerBu(d.kpis.oil_yield_lb_bu));
  await expect(page.getByTestId("crush-next")).toHaveText(shortDate(d.next_release, true, "en") ?? "—");
  if (d.target.crush_bu !== null) {
    await expect(page.getByTestId("crush-target")).toContainText(bushels(d.target.crush_bu));
    await expect(page.getByTestId("crush-target")).toContainText(share(d.kpis.pct_of_target));
  }
  const f1 = doc?.insights.find((i) => i.id === "F1:soybeans");
  if (f1 && f1.suppressed_reason === null) {
    await expect(page.getByTestId("crush-lead")).toContainText(share(f1.params.pct as number));
    await expect(page.getByTestId("crush-lead")).toContainText(`n = ${f1.n}`);
    expect(f1.params.pct).toBeCloseTo(d.kpis.pct_of_target!, 3);
  }
  if (d.target.crush_bu && d.kpis.cum_bu !== null) {
    // Independent of the published share: the page must print the true ratio rounded once
    // (198,828,501 / 2,780,000,000 = 0.071521 → 7.2%, never a pre-rounded 0.0715 → 7.1%).
    const truth = share(d.kpis.cum_bu / d.target.crush_bu);
    await expect(page.getByTestId("crush-target")).toContainText(truth);
    if (f1 && f1.suppressed_reason === null) await expect(page.getByTestId("crush-lead")).toContainText(truth);
  }
  if (d.pace.series.some((s) => s.points.some((p) => p[1] !== null))) {
    await expect(page.getByTestId("pace-deviation")).toContainText("minus the 5-yr mean");
  }
  const f2 = doc?.insights.find((i) => i.id === "F2:soybeans");
  if (f2 && f2.suppressed_reason === null && (f2.params.required_monthly_bu as number) > 0) {
    await expect(page.getByTestId("crush-needed")).toContainText(bushels(f2.params.required_monthly_bu as number));
    await expect(page.getByTestId("crush-needed")).toContainText(`${f2.params.months_remaining} months left`);
  }
  const f3 = doc?.insights.find((i) => i.id === "F3:soybeans");
  if (f3 && f3.suppressed_reason === null && f3.params.position) {
    await expect(page.getByTestId("crush-yield-line")).toContainText(lbPerBu(f3.params.hist_min as number));
    await expect(page.getByTestId("crush-yield-line")).toContainText(`n = ${f3.n}`);
  }
  await expect(page.getByTestId("pace-legend")).toContainText("% of the USDA projection at the time");
  await expect(page.locator('[data-testid^="chapter-"]')).toHaveCount(3);
  await expect(page.getByTestId("crush-explore")).not.toHaveAttribute("open", "");
});

test("crush page carries the exact NOPA note, the outbound link and the 2015-10+ window", async ({ page }) => {
  const c = await crush(page);
  test.skip(!c, "no crush data in this build");
  await page.goto("/reports/oilseed-crush/");
  const note = page.getByTestId("nopa-note");
  await expect(note.locator("p")).toHaveText(NOPA_NOTE);
  await expect(note.getByRole("link")).toHaveAttribute("href", "https://www.nopa.org/");
  await expect(page.getByTestId("crush-window")).toContainText("October 2015");
  await expect(page.locator("main")).not.toContainText(/since 2010/i);
});

test("the home crush card prints the insight params (amber, n, source date)", async ({ page }) => {
  const c = await crush(page);
  test.skip(!c?.doc, "no crush data in this build");
  const doc = c!.doc!;
  const id = doc.home_cards.find((x) => x.startsWith("F"));
  test.skip(!id, "no crush card passed its gates in this build");
  const i = doc.insights.find((x) => x.id === id) as Insight;
  await page.goto("/");
  const card = page.locator(`[data-insight-id="${id}"]`);
  await expect(card).toBeVisible();
  const v = cardView(i, "en")!;
  await expect(card.locator("[data-param]")).toHaveText(formatParam(i, v.valueParam));
  await expect(card.getByTestId("n")).toHaveText(`n = ${i.n}`);
  await expect(card.getByTestId("card-source")).toContainText(`NASS crush ${shortDate(c!.idx.latest.release_key, true, "en")}`);
  await expect(card.getByTestId("small-sample")).toHaveCount(i.caveats.includes("small_sample") ? 1 : 0);
  await expect(card).toContainText("2015-10+");
  await expect(card.getByRole("link", { name: /Open the chart/ })).toHaveAttribute("href", "/reports/oilseed-crush/");
  await page.getByRole("button", { name: "Português" }).click();
  await expect(card.locator("[data-param]")).toHaveText(formatParam(i, v.valueParam, "pt"));
  await expect(card).not.toContainText("crude oil per bushel");
  await page.getByRole("button", { name: "English" }).click();
});

test("crush is live in the nav, on /reports and in the data catalogue", async ({ page }) => {
  const c = await crush(page);
  test.skip(!c, "no crush data in this build");
  await page.goto("/reports/");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: /Crush \(NASS\)/ })).toHaveAttribute("href", "/reports/oilseed-crush/");
  const card = page.locator("#oilseed_crush");
  await expect(card).toContainText(shortDate(c!.idx.latest.release_key, true, "en")!);
  await expect(card.getByTestId("freshness")).toBeVisible();
  await page.goto("/data/");
  await expect(page.locator("#report-oilseed_crush")).toBeVisible();
  await expect(page.getByTestId("vintage-oilseed_crush")).toContainText("stored as published");
  await page.goto("/reports/oilseed-crush/");
  await page.getByRole("button", { name: "Português" }).click();
  const main = page.locator("main");
  for (const word of ["What is still needed", "Oil yield per bushel", "Next NASS release", "Take this report"]) {
    await expect(main, word).not.toContainText(word);
  }
  await page.getByRole("button", { name: "English" }).click();
});
