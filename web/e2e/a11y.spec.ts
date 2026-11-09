import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// axe on every route, in EN and PT, light and dark: no serious or critical violations.
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
  "/methodology/",
];

// Every route in English and Portuguese, light and dark.
for (const lang of ["en", "pt"] as const) {
  for (const scheme of ["light", "dark"] as const) {
    for (const url of ROUTES) {
      test(`axe ${lang} ${scheme} ${url}`, async ({ page }) => {
        // The language is a stored preference (applied after hydration).
        if (lang === "pt") await page.addInitScript(() => localStorage.setItem("usda-lang", "pt"));
        await page.emulateMedia({ colorScheme: scheme });
        await page.goto(url);
        await expect(page.locator("html")).toHaveAttribute("lang", lang === "pt" ? "pt-BR" : "en");
        await page.waitForTimeout(400);
        const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        expect(
          bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`),
          `${lang} ${scheme} ${url}`,
        ).toEqual([]);
      });
    }
  }
}

test("focus rings on the dark data strip are white (3:1 against the strip)", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const links = page.locator('[aria-labelledby="h-data"] a');
  await expect(links.first()).toBeVisible();
  for (let i = 0; i < (await links.count()); i++) {
    await links.nth(i).focus();
    const color = await links.nth(i).evaluate((el) => getComputedStyle(el).outlineColor);
    expect(color, `link ${i}`).toBe("rgb(255, 255, 255)");
  }
});

test("white text on every solid report tile passes colour contrast in dark mode", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  const tiles = page.locator('[data-testid="report-tiles"]');
  test.skip((await tiles.count()) === 0, "no report tiles in this build");
  await page.waitForTimeout(400);
  const { violations } = await new AxeBuilder({ page }).include('[data-testid="report-tiles"]').withRules(["color-contrast"]).analyze();
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});

test("keyboard focus is visible on the first controls", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab"); // skip link
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Tab");
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
});
