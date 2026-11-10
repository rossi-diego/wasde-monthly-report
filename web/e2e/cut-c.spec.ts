import fs from "node:fs";
import { fileURLToPath } from "node:url";

import { mainNav } from "./nav";
import { expect, test, type Page } from "@playwright/test";

import type { CommodityLens, CropProgressCrop, CropProgressIndex, GrainStocksCommodity, GrainStocksIndex, Insight, InsightsDoc, LensIndex } from "../lib/data-contract";
import { num, share, withNumberLang } from "../lib/format";
import { cardView, formatParam } from "../lib/insight-text";
import { alsoReleased, homeTiles, lensBlocks } from "../lib/lens";
import { cropProgressText, finalRatings, grainStocksText } from "../lib/report-views";

// Cut C (Crop Progress, Grain Stocks, commodity lenses, full pt-BR): copy-vs-JSON contract for
// the new cards and pages, in EN and PT, plus frozen-clock off-season checks on a fixture.
// Page tests skip for a build without the cut-C JSON.

async function json<T>(page: Page, url: string): Promise<T | null> {
  const r = await page.request.get(url);
  return r.ok() ? ((await r.json()) as T) : null;
}

const fixture = <T,>(rel: string): T => JSON.parse(fs.readFileSync(fileURLToPath(new URL(`./fixtures/${rel}`, import.meta.url)), "utf-8")) as T;

async function toPt(page: Page) {
  await page.getByRole("button", { name: "Português" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
}
async function toEn(page: Page) {
  await page.getByRole("button", { name: "English" }).click();
}

// ------------------------------------------------------------------ pure (no page)

test("numbers follow the language: 1,234.5 in EN, 1.234,5 in pt-BR", () => {
  expect(withNumberLang("en", () => num(1234.5, 1))).toBe("1,234.5");
  expect(withNumberLang("pt", () => num(1234.5, 1))).toBe("1.234,5");
  expect(withNumberLang("pt", () => share(0.6554))).toBe("65,5%");
  expect(num(1234.5, 1)).toBe("1,234.5"); // the locale is restored afterwards
});

test("off-season fixture (frozen clock 2026-12-08): Crop Progress is closed and off the home page", () => {
  const doc = fixture<InsightsDoc>("offseason/insights.json");
  expect(doc.seasons?.crop_progress.state).toBe("closed");
  expect(doc.seasons?.crop_progress.shown_on_home).toBe(false);
  // Hidden December–March: neither the capped row nor "also released" shows Crop Progress.
  const homeReports = doc.home_cards.map((id) => doc.insights.find((i) => i.id === id)?.report_id);
  expect(homeReports).not.toContain("crop_progress");
  expect(alsoReleased(doc).map((i) => i.report_id)).not.toContain("crop_progress");
  // C2/C3 are season_closed (never findings); C1 is the final rating vs the 5 prior final ratings.
  for (const i of doc.insights.filter((x) => x.rule === "C2" || x.rule === "C3")) expect(i.suppressed_reason, i.id).toBe("season_closed");
  const c1 = doc.insights.find((i) => i.id === "C1:corn") as Insight;
  expect(c1.suppressed_reason).toBeNull();
  expect(c1.caveats).toContain("own_5yr_final_rating");
  const v = cardView(c1, "en")!;
  expect(v.eyebrow).toBe("Crop Progress · season closed");
  expect(v.context[0]).toBe(
    `Season closed: final GE ${num(c1.params.ge_pct as number)}% vs 5-yr ${num(c1.params.hist_mean as number, 1)}% (${num(c1.params.hist_min as number)}%–${num(c1.params.hist_max as number)}%)`,
  );
  expect(cardView(c1, "pt")!.context[0]).toMatch(/^Safra encerrada: BE final/);
  expect(finalRatings(c1)).toHaveLength(c1.n! + 1);
  // The report page text: closed lead, closed season chapter, next season date.
  const corn = fixture<CropProgressCrop>("offseason/reports/crop_progress/corn.json");
  const idx = fixture<CropProgressIndex>("offseason/reports/crop_progress/index.json");
  const t = cropProgressText(corn, doc, "en", idx.season?.last_scheduled ?? null);
  expect(t.closed).toBe(true);
  expect(t.lead).toMatch(/^Season closed: final GE \d+% vs 5-yr/);
  expect(t.lead).toContain(`n = ${c1.n}`);
  expect(t.seasonLine).toContain("is closed");
  expect(t.stageLine).toBeNull(); // C2 suppressed
  expect(t.sub).toContain("next season starts");
});

test("in-season fixture: Crop Progress is open and its card is eligible for the home page", () => {
  const doc = fixture<InsightsDoc>("cut-c/insights.json");
  expect(doc.seasons?.crop_progress.state).toBe("in_season");
  const cp = [...doc.home_cards.map((id) => doc.insights.find((i) => i.id === id)!), ...alsoReleased(doc)].filter((i) => i.report_id === "crop_progress");
  expect(cp).toHaveLength(1);
  const gs = [...doc.home_cards.map((id) => doc.insights.find((i) => i.id === id)!), ...alsoReleased(doc)].filter((i) => i.report_id === "grain_stocks");
  expect(gs).toHaveLength(1);
  for (const i of [...cp, ...gs]) {
    expect(i.suppressed_reason).toBeNull();
    expect(cardView(i, "en")).not.toBeNull();
  }
});

test("in-season fixture: a crop whose season ended (spring wheat) is final, not stale, and not in the next release", () => {
  const doc = fixture<InsightsDoc>("cut-c/insights.json");
  const idx = fixture<CropProgressIndex>("cut-c/reports/crop_progress/index.json");
  const sw = fixture<CropProgressCrop>("cut-c/reports/crop_progress/spring_wheat.json");
  expect(idx.season?.state).toBe("in_season");
  expect(sw.season_state).toBe("closed");
  expect(sw.season_scope).toBe("crop");
  const ids = doc.insights.filter((i) => i.id.endsWith(":spring_wheat"));
  for (const i of ids) expect(i.suppressed_reason, i.id).not.toBe("stale_input");
  const c1 = doc.insights.find((i) => i.id === "C1:spring_wheat") as Insight;
  expect(c1.suppressed_reason).toBeNull();
  expect(c1.window).toBe("prior_5_seasons_final_rating");
  // Never the home story while the report's season is open.
  expect(doc.home_cards).not.toContain("C1:spring_wheat");
  for (const lang of ["en", "pt"] as const) {
    const v = cropProgressText(sw, doc, lang, idx.season?.last_scheduled ?? null);
    expect(v.cropDone).toBe(true);
    expect(v.stats.next).toBe("—"); // not "next release Nov 9" for a crop that release won't include
    expect(v.lead).toContain(`n = ${c1.n}`);
    if (lang === "en") {
      expect(v.lead).toMatch(/^Spring wheat: season complete\. Final GE \d+%/);
      expect(v.sub).toMatch(/^Season complete for this crop/);
      expect(v.stageDoneLine).toMatch(/^Season complete: Spring wheat left the weekly report/);
    }
  }
});

test("in-season fixture: the header never shows a 5-yr comparison the gates hid", () => {
  const doc = fixture<InsightsDoc>("cut-c/insights.json");
  for (const crop of ["corn", "soybeans", "winter_wheat"]) {
    const d = fixture<CropProgressCrop>(`cut-c/reports/crop_progress/${crop}.json`);
    const c3 = doc.insights.find((i) => i.id === `C3:${crop}`) as Insight;
    const v = cropProgressText(d, doc, "en");
    if (c3.suppressed_reason !== null) {
      expect(v.stats.ciSub, crop).toBe(`1–5 scale · not compared with the 5 prior seasons (n = ${c3.n})`);
      if (d.condition?.ci_5yr_mean != null) expect(v.stats.ciSub, crop).not.toContain(num(d.condition.ci_5yr_mean, 2));
    } else expect(v.stats.ciSub, crop).toContain(`n = ${c3.n}`);
    // One specific note names what is hidden and its n, instead of two generic boxes.
    const c1 = doc.insights.find((i) => i.id === `C1:${crop}`) as Insight;
    if (c1.suppressed_reason === "n_below_min") expect(v.nBelowLine, crop).toContain("within ±3 days");
    // "Last year" blanks say why.
    if (d.condition && d.condition.nass_prev_year_ge_pct === null) expect(v.stats.geSub, crop).toContain("not published (no NASS release that week in 2025)");
  }
});

test("G2 caveats are worded exactly as the plan states", () => {
  const doc = fixture<InsightsDoc>("cut-c/insights.json");
  const g2 = doc.insights.find((i) => i.rule === "G2" && i.suppressed_reason === null) as Insight;
  const v = cardView(g2, "en")!;
  expect(v.caveats).toContain("imports omitted; small for corn/soy");
  expect(v.caveats).toContain(
    "NASS may revise production on the same day (Small Grains Summary / annual Crop Production); this uses the WASDE figure public at release",
  );
});

test("percentiles only from n ≥ 10, and small samples are labelled, in every C/G card", () => {
  for (const rel of ["cut-c/insights.json", "offseason/insights.json"]) {
    const doc = fixture<InsightsDoc>(rel);
    for (const i of doc.insights.filter((x) => /^[CG]/.test(x.rule) && x.suppressed_reason === null)) {
      const v = cardView(i, "en");
      if (!v) continue;
      const text = [v.title, v.value, ...v.context].join(" ");
      if ((i.n ?? 0) < 10) {
        expect(text, i.id).not.toMatch(/percentile|Larger than \d+%/);
        expect(v.small, i.id).toBe(true);
      }
    }
  }
});

// ------------------------------------------------------------------ pages

test("home: Crop Progress (green) and Grain Stocks (violet) cards print their params, n and source", async ({ page }) => {
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  test.skip(!doc?.insights.some((i) => i.report_id === "crop_progress"), "no Crop Progress insights in this build");
  await page.goto("/");
  const shown = [...doc!.home_cards.map((id) => doc!.insights.find((i) => i.id === id)!), ...alsoReleased(doc!)].filter(
    (i) => i && i.suppressed_reason === null && (i.report_id === "crop_progress" || i.report_id === "grain_stocks"),
  );
  await expect(page.locator('[data-testid="insight-card"][data-origin="also"]')).toHaveCount(homeTiles(doc!).filter((x) => x.origin === "also").length);
  for (const i of shown) {
    const card = page.locator(`[data-insight-id="${i.id}"]`);
    await expect(card).toBeVisible();
    const v = cardView(i, "en")!;
    await expect(card.locator("[data-param]")).toHaveText(formatParam(i, v.valueParam));
    await expect(card.getByTestId("n")).toHaveText(`n = ${i.n}`);
    await expect(card.getByTestId("small-sample")).toHaveCount(i.caveats.includes("small_sample") ? 1 : 0);
    await expect(card.getByTestId("card-source")).toContainText(i.report_id === "crop_progress" ? "Crop Progress" : "Grain Stocks");
    // Solid report tiles: the report colour is the background (deep in both themes).
    const bg = await card.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg, i.id).toBe(i.report_id === "crop_progress" ? "rgb(21, 128, 61)" : "rgb(109, 40, 217)");
  }
  // No placeholder cards left for v1 reports.
  await expect(page.getByText("Layout preview")).toHaveCount(0);
  await toPt(page);
  for (const i of shown) {
    await expect(page.locator(`[data-insight-id="${i.id}"] [data-param]`)).toHaveText(formatParam(i, cardView(i, "pt")!.valueParam, "pt"));
  }
  await toEn(page);
});

test("Crop Progress page: header numbers and chapter sentences equal the JSON (EN and PT)", async ({ page }) => {
  const idx = await json<CropProgressIndex>(page, "/data/reports/crop_progress/index.json");
  test.skip(!idx, "no Crop Progress data in this build");
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  for (const c of idx!.crops.slice(0, 2)) {
    const d = (await json<CropProgressCrop>(page, `/data/${c.file}`))!;
    await page.goto(`/reports/crop-progress/?c=${c.id}`);
    for (const lang of ["en", "pt"] as const) {
      if (lang === "pt") await toPt(page);
      const v = cropProgressText(d, doc, lang, idx!.season?.last_scheduled ?? null);
      await expect(page.getByTestId("cp-lead")).toHaveText(v.lead);
      await expect(page.getByTestId("cp-stage")).toHaveText(v.stats.stage);
      await expect(page.getByTestId("cp-ge")).toHaveText(v.stats.ge);
      await expect(page.getByTestId("cp-ci")).toHaveText(v.stats.ci);
      await expect(page.getByTestId("cp-next")).toHaveText(v.stats.next);
      if (v.stageLine) await expect(page.getByTestId("cp-stage-line")).toHaveText(v.stageLine);
      await expect(page.getByTestId("cp-season-line")).toHaveText(v.seasonLine);
      if (lang === "pt") await toEn(page);
    }
    await expect(page.locator('[data-testid^="chapter-"]')).toHaveCount(3);
    await expect(page.getByTestId("cp-explore")).not.toHaveAttribute("open", "");
    await expect(page.getByTestId("season-closed")).toHaveCount(d.season_state === "closed" ? 1 : 0);
    const c2 = doc?.insights.find((i) => i.id === `C2:${c.id}`);
    if (c2?.suppressed_reason === null) await expect(page.getByTestId("cp-stage-legend")).toContainText("NASS 5-yr average (as published)");
  }
});

test("Grain Stocks page: header numbers, G1–G3 sentences and the exact G2 caveats", async ({ page }) => {
  const idx = await json<GrainStocksIndex>(page, "/data/reports/grain_stocks/index.json");
  test.skip(!idx, "no Grain Stocks data in this build");
  const doc = await json<InsightsDoc>(page, "/data/insights.json");
  for (const c of idx!.commodities.slice(0, 2)) {
    const d = (await json<GrainStocksCommodity>(page, `/data/${c.file}`))!;
    await page.goto(`/reports/grain-stocks/?c=${c.id}`);
    for (const lang of ["en", "pt"] as const) {
      if (lang === "pt") await toPt(page);
      const v = grainStocksText(d, doc, lang);
      await expect(page.getByTestId("gs-lead")).toHaveText(v.lead);
      await expect(page.getByTestId("gs-total")).toHaveText(v.stats.total);
      await expect(page.getByTestId("gs-farm")).toHaveText(v.stats.farm);
      await expect(page.getByTestId("gs-yoy")).toHaveText(v.stats.yoy);
      if (v.g1Line) await expect(page.getByTestId("gs-g1-line")).toContainText(v.g1Line);
      if (v.g2Line) await expect(page.getByTestId("gs-g2-line")).toHaveText(v.g2Line);
      if (v.g3Line) await expect(page.getByTestId("gs-g3-line")).toHaveText(v.g3Line);
      if (lang === "pt") await toEn(page);
    }
    const g2 = doc?.insights.find((i) => i.id === `G2:${c.id}`);
    if (g2?.suppressed_reason === null) {
      const ch2 = page.getByTestId("chapter-2");
      await expect(ch2).toContainText("imports omitted; small for corn/soy");
      await expect(ch2).toContainText("NASS may revise production on the same day (Small Grains Summary / annual Crop Production); this uses the WASDE figure public at release");
      await expect(ch2.getByTestId("n")).toHaveText(`n = ${g2.n}`);
    }
    const g1 = doc?.insights.find((i) => i.id === `G1:${c.id}`);
    if (g1?.suppressed_reason === null && (g1.n ?? 0) < 10) await expect(page.getByTestId("chapter-1")).not.toContainText("percentile");
    await expect(page.locator('[data-testid^="chapter-"]')).toHaveCount(3);
    await expect(page.getByTestId("gs-explore")).not.toHaveAttribute("open", "");
  }
});

test("commodity lenses: every report's latest number equals lens JSON, with chapter links (EN and PT)", async ({ page }) => {
  const idx = await json<LensIndex>(page, "/data/lens/index.json");
  test.skip(!idx, "no commodity lenses in this build");
  for (const c of idx!.commodities) {
    const lens = (await json<CommodityLens>(page, `/data/${c.file}`))!;
    await page.goto(`/commodities/${c.id}/`);
    await expect(page.getByTestId("lens-block")).toHaveCount(lens.reports.length);
    for (const lang of ["en", "pt"] as const) {
      if (lang === "pt") await toPt(page);
      for (const b of lensBlocks(lens, lang)) {
        const block = page.locator(`[data-testid="lens-block"][data-report="${b.reportId}"]`);
        for (const r of b.rows) {
          const row = block.locator(`[data-metric="${r.metric}"]`);
          await expect(row.getByTestId("lens-value")).toHaveText(r.value);
          if (lang === "en") await expect(row.getByRole("link")).toHaveAttribute("href", r.href);
        }
      }
      if (lang === "pt") await toEn(page);
    }
  }
  const nav = await mainNav(page);
  await expect(nav.getByRole("link", { name: "Soybeans" })).toHaveAttribute("href", "/commodities/soybeans/");
  await expect(nav.getByRole("link", { name: "Corn", exact: true })).toHaveAttribute("href", "/commodities/corn/");
});

test("Crop Progress and Grain Stocks are live in the nav, on /reports and in the catalogue", async ({ page }) => {
  const cp = await json<CropProgressIndex>(page, "/data/reports/crop_progress/index.json");
  test.skip(!cp, "no Crop Progress data in this build");
  await page.goto("/reports/");
  const nav = await mainNav(page);
  await expect(nav.getByRole("link", { name: /Crop Progress/ })).toHaveAttribute("href", "/reports/crop-progress/");
  await expect(nav.getByRole("link", { name: /Grain Stocks/ })).toHaveAttribute("href", "/reports/grain-stocks/");
  await expect(page.locator("#crop_progress").getByTestId("freshness")).toBeVisible();
  await expect(page.locator("#crop_progress").getByTestId("cp-season-state")).toHaveAttribute("data-state", cp!.season?.state ?? "in_season");
  await expect(page.locator("#grain_stocks").getByTestId("freshness")).toBeVisible();
  await page.goto("/data/");
  await expect(page.locator("#report-crop_progress")).toBeVisible();
  await expect(page.locator("#report-grain_stocks")).toBeVisible();
  await expect(page.locator('[data-testid="dataset-row"][data-report="grain_stocks"]')).toHaveCount(3);
});

test("Portuguese mode leaves no English UI copy on the new pages, the methodology and the catalogue", async ({ page }) => {
  const cp = await json<CropProgressIndex>(page, "/data/reports/crop_progress/index.json");
  test.skip(!cp, "no Crop Progress data in this build");
  const words: Record<string, string[]> = {
    "/reports/crop-progress/": ["Where the season stands", "Stage pace", "rated good or excellent", "Take this report", "Next release", "small sample", "week ending"],
    "/reports/grain-stocks/": ["Ending stocks vs", "Implied use", "Who holds the stocks", "imports omitted", "Next release", "small sample"],
    "/commodities/soybeans/": ["Open the chapter", "Ending stocks", "Released", "Marketing year", "Week ending"],
    "/methodology/": ["How the numbers", "Sources", "Harmonization", "Season closed", "This page is available in English only"],
    "/data/": ["Download Excel", "Reports from", "Versioned copy", "Ready-made files", "values match"],
    "/": ["Also released", "One commodity, every report", "Open the chart", "Open report", "Explore by commodity", "All revisions", "What changed"],
    "/reports/oilseed-crush/": ["NOPA members represent", "proprietary and not redistributed", "About NOPA"],
  };
  for (const [url, list] of Object.entries(words)) {
    await page.goto(url);
    await toPt(page);
    const main = page.locator("main");
    for (const w of list) await expect(main, `${url}: ${w}`).not.toContainText(w);
    await toEn(page);
  }
});
