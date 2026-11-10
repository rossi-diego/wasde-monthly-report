import { mainNav } from "./nav";
import { expect, test } from "@playwright/test";

// Runs against the static export locally, and against the live URL after each deploy
// (E2E_BASE_URL), where it also proves the site shows the latest ingested report.

const ROUTES = [
  "/",
  "/reports/",
  "/reports/wasde/",
  "/reports/export-sales/",
  "/reports/oilseed-crush/",
  "/reports/crop-progress/",
  "/reports/grain-stocks/",
  "/commodities/soybeans/",
  "/commodities/corn/",
  "/commodity/corn/",
  "/commodity/soybeans/",
  "/data/",
  "/downloads/",
  "/methodology/",
];

test("home is a front door: hero, one tile per report, top revisions and the commodity pages", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  const ov = await (await page.request.get("/data/overview.json")).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("USDA reports at a glance");
  if (meta.latest.wasde_number) await expect(page.getByText(`WASDE #${meta.latest.wasde_number}`)).toBeVisible();
  // The sections that repeat the detail pages are gone from the overview.
  for (const id of ["lens-teaser", "kpi", "stu-rank"]) await expect(page.getByTestId(id), id).toHaveCount(0);
  await expect(page.getByRole("group", { name: "Commodity" })).toHaveCount(0);
  // What changed: the top 3 overview.json highlights, then the full list on /reports/wasde/.
  await expect(page.getByRole("heading", { name: /What changed in WASDE vs/ })).toBeVisible();
  await expect(page.locator('[aria-labelledby="h-chg-top"] li')).toHaveCount(Math.min(3, ov.highlights.length));
  await expect(page.getByRole("link", { name: "All revisions →" })).toHaveAttribute("href", "/reports/wasde/#h-chg");
  // Explore by commodity: one link per commodity page.
  const explore = page.getByTestId("explore-link");
  await expect(explore).toHaveCount(2);
  for (let i = 0; i < 2; i++) await expect(explore.nth(i)).toHaveAttribute("href", /^\/commodities\/[a-z_]+\/$/);
  if (process.env.EXPECTED_REPORT_LABEL) expect(meta.latest.label).toBe(process.env.EXPECTED_REPORT_LABEL);
});

test("biggest revisions list on /reports/wasde/ matches overview.json", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  const ov = await (await page.request.get("/data/overview.json")).json();
  await page.goto("/reports/wasde/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(meta.latest.label);
  await expect(page.locator('[aria-labelledby="h-chg"] ol > li')).toHaveCount(ov.highlights.length);
  await expect(page.getByRole("heading", { name: /Biggest revisions vs/ })).toBeVisible();
  if (meta.downloads.some((d: { file: string }) => /\.xlsx$/.test(d.file)))
    await expect(page.locator('[aria-labelledby="h-chg"]').getByRole("link", { name: /All changes \(Excel\)/ })).toBeVisible();
});

for (const lang of ["en", "pt"] as const) {
  test(`home layout budget (${lang}): about one screen at 1440px, one chart, no sideways scroll at 360px`, async ({ page }) => {
    // pt-BR strings run longer: the budget must hold in both languages.
    if (lang === "pt") await page.addInitScript(() => localStorage.setItem("usda-lang", "pt"));
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(1400);
    // The only chart on the overview is the lead card evidence range strip.
    await expect(page.locator('main svg[role="img"]')).toHaveCount(await page.locator('[data-origin="hero"]').count());
    // Tiles in one row have the same height, and stay dense (the full story is on the report pages).
    const boxes = await page.locator('[data-testid="report-tiles"] > *').evaluateAll((els) => els.map((e) => e.getBoundingClientRect()));
    if (boxes.length) {
      const hs = boxes.map((b) => b.height);
      expect(Math.max(...hs) - Math.min(...hs)).toBeLessThanOrEqual(1);
      // EN about 255px plus one wrapped context line (the context and the verdict chip wrap
      // instead of being cut); pt-BR copy may add one more line (the subgrid keeps rows aligned).
      expect(Math.max(...hs)).toBeLessThanOrEqual(lang === "pt" ? 300 : 280);
      // The tiles sit above the fold at 1440x900.
      expect(Math.max(...boxes.map((b) => b.bottom))).toBeLessThanOrEqual(900);
    }
    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto("/");
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(3000); // the nav is a Menu drawer below 1024px
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  });
}

test("commodity page renders charts and switches region", async ({ page }) => {
  await page.goto("/commodity/corn/");
  await expect(page.getByRole("heading", { name: /Balance sheet/ })).toBeVisible();
  await expect(page.locator('svg[role="img"]').first()).toBeVisible();
  await page.getByLabel("Region").selectOption("world");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("World");
});

test("explore section loads the interactive chart on demand", async ({ page }) => {
  await page.goto("/commodity/soybeans/");
  await page.getByText(/^Explore:/).click();
  await expect(page.locator('div[role="img"] svg').first()).toBeVisible({ timeout: 30_000 });
});

test("explorer loads parquet and exports excel", async ({ page }) => {
  await page.goto("/data/");
  await expect(page.getByText(/values match/)).toBeVisible({ timeout: 30_000 });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Excel" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);
});

test("reports index shows WASDE dates from meta.json", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  await page.goto("/reports/");
  await expect(page.getByRole("heading", { name: /WASDE/ })).toBeVisible();
  await expect(page.locator("#wasde")).toContainText(meta.latest.label);
  // Since cut C every v1 report is live: no placeholder section is left.
  await expect(page.getByRole("heading", { name: "Other USDA reports" })).toHaveCount(0);
});

test("prebuilt downloads exist", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  for (const d of meta.downloads) {
    const r = await page.request.head(`/data/${d.url}`);
    expect(r.status(), d.file).toBe(200);
  }
});

test("no dead internal links", async ({ page }) => {
  const seen = new Set<string>();
  for (const url of ROUTES) {
    await page.goto(url);
    const hrefs = await page.locator("a[href]").evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    for (const h of hrefs) {
      expect(h, `empty or placeholder link on ${url}`).not.toMatch(/^#?$/);
      if (!h.startsWith("/") || seen.has(h)) continue;
      seen.add(h);
      const r = await page.request.head(h.split("#")[0]);
      expect(r.status(), `${h} (from ${url})`).toBe(200);
    }
  }
});

test("theme and language toggles work and persist", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByRole("button", { name: "Dark mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Português" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Relatórios do USDA em resumo");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  await page.getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("USDA reports at a glance");
});

test("Portuguese mode has no English months or chrome on the home page", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  const EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const latestEn = EN_MONTHS[Number(meta.latest.report_month.slice(5, 7)) - 1];
  const prevEn = meta.previous_report_month ? EN_MONTHS[Number(meta.previous_report_month.slice(5, 7)) - 1] : latestEn;
  await page.goto("/");
  await page.getByRole("button", { name: "Português" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Relatórios do USDA em resumo");
  const main = page.locator("main");
  for (const word of [latestEn, prevEn, "Raised", "Cut to", "Unchanged", "Step", "Marketing year", "ending stocks"]) {
    await expect(main, word).not.toContainText(word);
  }
  await expect(page.getByRole("heading", { name: /O que mudou no WASDE vs/ })).toBeVisible();
  await page.getByRole("button", { name: "English" }).click();
});

test("commodity pages keep the WASDE nav item current", async ({ page }) => {
  await page.goto("/commodity/corn/");
  const nav = await mainNav(page);
  await expect(nav.getByRole("link", { name: /WASDE/ })).toHaveAttribute("aria-current", "true");
});

test("on a 360px phone the title is on the first screen and every commodity pill is visible", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/");
  const h1 = await page.getByRole("heading", { level: 1 }).boundingBox();
  expect(h1, "h1 box").not.toBeNull();
  expect(h1!.y + h1!.height).toBeLessThanOrEqual(780);
  // The overview has no commodity pills; the commodity pages do.
  await page.goto("/commodity/soybeans/");
  const pills = page.getByRole("group", { name: "Commodity" }).getByRole("button");
  for (let i = 0; i < (await pills.count()); i++) {
    const b = (await pills.nth(i).boundingBox())!;
    expect(b.x, `pill ${i}`).toBeGreaterThanOrEqual(0);
    expect(b.x + b.width, `pill ${i}`).toBeLessThanOrEqual(360);
  }
});

test("pages never scroll horizontally at 360px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  for (const url of ROUTES) {
    await page.goto(url);
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, url).toBeLessThanOrEqual(0);
  }
});
