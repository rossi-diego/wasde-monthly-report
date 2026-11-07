import { test } from "@playwright/test";
const OUT = process.env.SHOTS_DIR ?? "shots";
for (const scheme of ["light", "dark"] as const) {
  test(`@shots ${scheme}`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme });
    for (const [name, url] of [["home", "/"], ["corn", "/commodity/corn/"], ["downloads", "/downloads/"]]) {
      await page.goto(url);
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `${OUT}/${info.project.name}-${scheme}-${name}.png`, fullPage: true });
    }
  });
}
