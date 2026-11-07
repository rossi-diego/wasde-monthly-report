import { expect, test } from "@playwright/test";

// Runs against the static export locally, and against the live URL after each deploy
// (E2E_BASE_URL), where it also proves the site shows the latest ingested report.

test("home shows the latest report and headlines", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(meta.latest.label);
  await expect(page.getByRole("heading", { name: "Headlines" })).toBeVisible();
  expect(await page.locator("ol > li").count()).toBeGreaterThan(0);
  if (process.env.EXPECTED_REPORT_LABEL) expect(meta.latest.label).toBe(process.env.EXPECTED_REPORT_LABEL);
});

test("commodity page renders charts and switches region", async ({ page }) => {
  await page.goto("/commodity/corn/");
  await expect(page.getByRole("heading", { name: /Balance sheet/ })).toBeVisible();
  await expect(page.locator('[role="img"] svg').first()).toBeVisible();
  await page.getByLabel("Region").selectOption("world");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("World");
});

test("explorer loads parquet and exports excel", async ({ page }) => {
  await page.goto("/downloads/");
  await expect(page.getByText(/values match/)).toBeVisible({ timeout: 30_000 });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Excel" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);
});

test("prebuilt downloads exist", async ({ page }) => {
  const meta = await (await page.request.get("/data/meta.json")).json();
  for (const d of meta.downloads) {
    const r = await page.request.head(`/data/${d.url}`);
    expect(r.status(), d.file).toBe(200);
  }
});
