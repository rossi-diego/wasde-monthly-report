import { expect, test, type Page } from "@playwright/test";

import type { EsrCommodity, EsrIndex, Insight, InsightsDoc } from "../lib/data-contract";
import { share, shortDate, tonnes } from "../lib/format";
import { formatParam, heroView } from "../lib/insight-text";

// Copy-vs-JSON contract (plan §6): every number the hero, the home cards and the Export Sales
// header print must equal the published params. Skipped for a data release built before cut A.

async function json<T>(page: Page, url: string): Promise<T | null> {
  const r = await page.request.get(url);
  return r.ok() ? ((await r.json()) as T) : null;
}

test("hero sentence and subline render insights.json hero", async ({ page }) => {
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  test.skip(!doc, "no insights.json in this build");
  await page.goto("/");
  const h = heroView(doc!.hero, "en");
  const hero = page.getByTestId("hero");
  await expect(hero).toHaveAttribute("data-kind", h.kind);
  await expect(page.getByTestId("hero-text")).toHaveText(h.text);
  if (h.sub) await expect(page.getByTestId("hero-sub")).toHaveText(h.sub);
  // The numbers inside the copy are the JSON's: n_reports and the since date.
  const sinceText = shortDate(doc!.hero.since, true, "en")!;
  await expect(hero).toContainText(String(doc!.hero.n_reports) + (h.kind === "story" ? " reports since " : " USDA reports released since "));
  await expect(hero).toContainText(sinceText);
  for (const c of doc!.hero.clauses) {
    for (const id of c.insight_ids) expect(doc!.insights.find((i) => i.id === id)?.suppressed_reason, id).toBeNull();
  }

  await page.getByRole("button", { name: "Português" }).click();
  await expect(page.getByTestId("hero-text")).toHaveText(heroView(doc!.hero, "pt").text);
  await page.getByRole("button", { name: "English" }).click();
});

test("home cards print exactly the insight params, n and the small-sample chip", async ({ page }) => {
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  test.skip(!doc, "no insights.json in this build");
  await page.goto("/");
  const shown = doc!.home_cards.map((id) => doc!.insights.find((i) => i.id === id)).filter((i): i is Insight => Boolean(i) && i!.suppressed_reason === null);
  await expect(page.getByTestId("insight-card")).toHaveCount(shown.length);
  for (const i of shown) {
    const card = page.locator(`[data-insight-id="${i.id}"]`);
    await expect(card).toBeVisible();
    const valueEl = card.locator("[data-param]");
    const param = (await valueEl.getAttribute("data-param"))!;
    expect(i.params, `${i.id} renders ${param}`).toHaveProperty(param);
    await expect(valueEl).toHaveText(formatParam(i, param));
    await expect(card.getByTestId("n")).toHaveText(`n = ${i.n}`);
    await expect(card.getByTestId("small-sample")).toHaveCount(i.caveats.includes("small_sample") ? 1 : 0);
    if (i.rule === "E1") {
      await expect(card).toContainText(share(i.params.hist_min as number));
      await expect(card).toContainText(share(i.params.hist_max as number));
    }
    // Never a percentile below n = 10.
    if ((i.n ?? 0) < 10) await expect(card).not.toContainText(/percentile|tighter than \d/);
  }
  // Suppressed insights never appear as findings.
  for (const i of doc!.insights.filter((x) => x.suppressed_reason !== null)) {
    await expect(page.locator(`[data-insight-id="${i.id}"]`)).toHaveCount(0);
  }
});

test("Export Sales header numbers equal the commodity JSON and E1", async ({ page }) => {
  const idx = await json<EsrIndex>(page, "/data/reports/export_sales/index.json");
  test.skip(!idx, "no Export Sales data in this build");
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  for (const c of idx!.commodities.slice(0, 2)) {
    const d = (await json<EsrCommodity>(page, `/data/${c.file}`))!;
    await page.goto(`/reports/export-sales/?c=${c.id}`);
    await expect(page.getByTestId("esr-commitments")).toHaveText(tonnes(d.kpis.total_commitment_mt));
    await expect(page.getByTestId("esr-target")).toHaveText(tonnes(d.target.exports_mt));
    await expect(page.getByTestId("esr-next")).toHaveText(shortDate(d.next_release, true, "en") ?? "—");
    const e1 = doc?.insights.find((i) => i.id === `E1:${c.id}`);
    if (e1 && e1.suppressed_reason === null && e1.params.pct !== null) {
      await expect(page.getByTestId("esr-lead")).toContainText(share(e1.params.pct as number));
      await expect(page.getByTestId("esr-lead")).toContainText(`n = ${e1.n}`);
    }
    await expect(page.getByTestId("pace-legend")).toContainText("% of the USDA projection at the time");
    await expect(page.locator('[data-testid^="chapter-"]')).toHaveCount(3);
  }
});

test("E2 is suppressed (not a finding) when fewer than 6 weeks remain", async ({ page }) => {
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  test.skip(!doc, "no insights.json in this build");
  for (const e2 of doc!.insights.filter((i) => i.rule === "E2")) {
    if ((e2.params.weeks_remaining as number) < doc!.gates.e2_min_weeks_remaining) expect(e2.suppressed_reason).toBe("weeks_remaining_below_min");
  }
  const sup = doc!.insights.find((i) => i.rule === "E2" && i.suppressed_reason !== null);
  if (!sup) return;
  await page.goto(`/reports/export-sales/?c=${sup.commodity_id}`);
  await expect(page.getByTestId("chapter-3").getByTestId("suppressed")).toBeVisible();
  await expect(page.getByTestId("esr-needed")).toHaveCount(0);
});

test("data catalogue lists every catalog.json dataset with its links", async ({ page }) => {
  const cat = await json<{ files: { report_id: string; dataset: string; legacy_alias_of: string | null }[] }>(page, "/data/catalog.json");
  test.skip(!cat || Array.isArray(cat), "no release catalogue in this build");
  await page.goto("/data/");
  const datasets = new Set(cat!.files.filter((f) => !f.legacy_alias_of).map((f) => `${f.report_id}:${f.dataset}`));
  await expect(page.getByTestId("dataset-row")).toHaveCount(datasets.size);
  await expect(page.getByTestId("datapackage-link")).toBeVisible();
  await expect(page.getByTestId("vintage-export_sales")).toContainText("latest revision");
  await page.getByRole("button", { name: "Commodity", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Soybeans", exact: true })).toBeVisible();
});

test("Portuguese mode translates the new report pages", async ({ page }) => {
  const idx = await json<EsrIndex>(page, "/data/reports/export_sales/index.json");
  test.skip(!idx, "no Export Sales data in this build");
  for (const url of ["/reports/export-sales/", "/reports/wasde/", "/reports/"]) {
    await page.goto(url);
    await page.getByRole("button", { name: "Português" }).click();
    const main = page.locator("main");
    for (const word of ["Week ending", "Commitments", "Who is buying", "What changed", "Tight or loose", "Next release", "small sample", "Open the chart"]) {
      await expect(main, `${url}: ${word}`).not.toContainText(word);
    }
    await page.getByRole("button", { name: "English" }).click();
  }
});

test("reports index shows Export Sales next to WASDE with freshness", async ({ page }) => {
  const idx = await json<EsrIndex>(page, "/data/reports/export_sales/index.json");
  test.skip(!idx, "no Export Sales data in this build");
  await page.goto("/reports/");
  const card = page.locator("#export_sales");
  await expect(card).toContainText(shortDate(idx!.latest.week_ending, true, "en")!);
  await expect(card.getByTestId("freshness")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: /Export Sales/ })).toHaveAttribute("href", "/reports/export-sales/");
});
