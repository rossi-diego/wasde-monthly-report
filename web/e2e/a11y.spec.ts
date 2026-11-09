import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// axe on every route, in light and dark: no serious or critical violations.
const ROUTES = ["/", "/reports/", "/reports/wasde/", "/reports/export-sales/", "/commodity/corn/", "/commodity/soybeans/", "/data/", "/methodology/"];

for (const scheme of ["light", "dark"] as const) {
  for (const url of ROUTES) {
    test(`axe ${scheme} ${url}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto(url);
      await page.waitForTimeout(400);
      const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(
        bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`),
        `${scheme} ${url}`,
      ).toEqual([]);
    });
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

test("keyboard focus is visible on the first controls", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab"); // skip link
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Tab");
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
});
