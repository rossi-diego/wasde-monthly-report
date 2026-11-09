import { test } from "@playwright/test";

// Dev helper (ignored unless SHOTS_DIR is set): README screenshots in both themes.
const OUT = process.env.SHOTS_DIR ?? "shots";

for (const scheme of ["light", "dark"] as const) {
  test(`@shots ${scheme}`, async ({ page }, info) => {
    if (info.project.name !== "desktop") test.skip();
    await page.setViewportSize({ width: 1360, height: 900 });
    await page.emulateMedia({ colorScheme: scheme });
    const pages: [string, string, number][] = [
      ["home", "/", 0],
      ["commodity", "/commodity/corn/", 0],
      ["revisions", "/commodity/corn/", 1300],
      ["downloads", "/downloads/", 0],
    ];
    for (const [name, url, scroll] of pages) {
      await page.goto(url);
      await page.waitForTimeout(1200);
      if (scroll) await page.evaluate((y) => window.scrollTo(0, y), scroll);
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${OUT}/${name}-${scheme}.png` });
    }
  });
}
