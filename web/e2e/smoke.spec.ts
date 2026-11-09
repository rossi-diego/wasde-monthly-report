import { expect, test, type Page } from "@playwright/test";

// Runs against the static export locally, and against the live URL after each deploy
// (E2E_BASE_URL), where it also proves the site shows the latest ingested report.

const ROUTES = ["/", "/reports/", "/commodity/corn/", "/commodity/soybeans/", "/data/", "/downloads/", "/methodology/"];

type Hist = { market_year: string; stocks_to_use_pct: number | null; status: "final" | "current" };

/** The rank sentence, recomputed from the published JSON (copy-vs-data contract). */
async function expectedRank(page: Page, commodity: string) {
  const s = await (await page.request.get(`/data/commodities/${commodity}/united_states.json`)).json();
  const hist = (s.stocks_to_use_history as Hist[]).filter((h) => h.stocks_to_use_pct !== null);
  const finals = hist.filter((h) => h.status === "final").map((h) => h.stocks_to_use_pct as number);
  const now = hist.filter((h) => h.status === "current").at(-1)!.stocks_to_use_pct as number;
  return `${finals.filter((v) => v < now).length} of ${finals.length} past seasons were tighter`;
}

test("home shows the latest report, KPI tiles and the data-derived rank", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(meta.latest.label);
  if (meta.latest.wasde_number) await expect(page.getByText(`WASDE #${meta.latest.wasde_number}`)).toBeVisible();
  await expect(page.getByTestId("kpi")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: /Biggest revisions vs/ })).toBeVisible();
  await expect(page.getByTestId("stu-rank")).toHaveText(await expectedRank(page, "soybeans"));

  await page.getByRole("group", { name: "Commodity" }).getByRole("button", { name: "Corn", exact: true }).click();
  await expect(page.getByTestId("stu-rank")).toHaveText(await expectedRank(page, "corn"));
  await expect(page.getByRole("heading", { name: /U\.S\. corn stocks-to-use/ })).toBeVisible();
  if (process.env.EXPECTED_REPORT_LABEL) expect(meta.latest.label).toBe(process.env.EXPECTED_REPORT_LABEL);
});

test("biggest revisions list matches overview.json", async ({ page }) => {
  const ov = await (await page.request.get("/data/overview.json")).json();
  await page.goto("/");
  const items = page.locator('[aria-labelledby="h-chg"] ol > li');
  await expect(items).toHaveCount(ov.highlights.length);
});

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
  await expect(page.getByRole("heading", { name: "Other USDA reports" })).toBeVisible();
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
  await expect(page.getByRole("heading", { level: 1 })).toContainText("O que o USDA disse");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  await page.getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("What USDA said");
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
