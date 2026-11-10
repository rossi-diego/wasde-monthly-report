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
      ["export-sales", "/reports/export-sales/"],
      ["crush", "/reports/oilseed-crush/"],
      ["crop-progress", "/reports/crop-progress/"],
      ["grain-stocks", "/reports/grain-stocks/"],
      ["lens", "/commodities/soybeans/"],
      ["commodity", "/commodity/corn/"],
      ["downloads", "/data/"],
    ] as const) {
      await page.goto(url);
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/${name}-${scheme}.png`, fullPage: name !== "commodity" && name !== "downloads" });
    }
    if (process.env.SHOTS_ALL) {
      for (const [name, url] of [
        ["wasde", "/reports/wasde/"],
        ["reports", "/reports/"],
        ["data-full", "/data/"],
      ] as const) {
        await page.goto(url);
        await page.waitForTimeout(800);
        await page.screenshot({ path: `${OUT}/${name}-${scheme}.png`, fullPage: true });
      }
    }
  });
}

test("@shots pt", async ({ page }, info) => {
  if (info.project.name !== "desktop") test.skip();
  await page.addInitScript(() => localStorage.setItem("usda-lang", "pt"));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ colorScheme: "light" });
  for (const [name, url] of [
    ["home-pt", "/"],
    ["crop-progress-pt", "/reports/crop-progress/"],
  ] as const) {
    await page.goto(url);
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  }
});

test("@shots mobile", async ({ page }, info) => {
  if (info.project.name !== "desktop") test.skip();
  await page.setViewportSize({ width: 360, height: 780 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.waitForTimeout(800);
  // First screens: stacked sidebar, top bar, hero, evidence card and the report tiles.
  await page.screenshot({ path: `${OUT}/home-mobile.png`, fullPage: true, clip: { x: 0, y: 0, width: 360, height: 2200 } });
  if (process.env.SHOTS_ALL) {
    await page.goto("/reports/export-sales/");
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/export-sales-mobile.png`, fullPage: true });
  }
});
