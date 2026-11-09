import { test } from "@playwright/test";

// Dev helper (ignored unless SHOTS_DIR is set): README screenshots.
//   SHOTS_DIR=../docs/screenshots npx playwright test shots --project=desktop
const OUT = process.env.SHOTS_DIR ?? "shots";

for (const scheme of ["light", "dark"] as const) {
  test(`@shots ${scheme}`, async ({ page }, info) => {
    if (info.project.name !== "desktop") test.skip();
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/home-${scheme}.png`, fullPage: true });
    for (const [name, url] of [
      ["commodity", "/commodity/corn/"],
      ["downloads", "/data/"],
    ] as const) {
      await page.goto(url);
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/${name}-${scheme}.png` });
    }
  });
}

test("@shots mobile", async ({ page }, info) => {
  if (info.project.name !== "desktop") test.skip();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.waitForTimeout(800);
  // First ~2 screens: stacked sidebar, top bar, KPI tiles and the first chart.
  await page.screenshot({ path: `${OUT}/home-mobile.png`, fullPage: true, clip: { x: 0, y: 0, width: 390, height: 1800 } });
});
