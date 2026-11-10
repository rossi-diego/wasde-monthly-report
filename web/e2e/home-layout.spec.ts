import { expect, test, type Page } from "@playwright/test";

import type { InsightsDoc } from "../lib/data-contract";
import { homeTiles } from "../lib/lens";

// Layout contract of the overview (the "top-anchored dashboard" consensus): the title, the solid
// report tiles right under it (values and footers on shared lines), then two card rows on one
// 7 | 5 grid whose cards stretch to equal heights. Geometry is measured in the browser.

type Box = { top: number; bottom: number; left: number; right: number; width: number; height: number };

const box = (e: Element): Box => {
  const r = e.getBoundingClientRect();
  return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height };
};

async function open(page: Page, width: number, height: number, opts: { scheme?: "light" | "dark"; lang?: "en" | "pt" } = {}) {
  const { scheme = "light", lang = "en" } = opts;
  await page.emulateMedia({ colorScheme: scheme });
  await page.addInitScript(
    ([l, s]) => {
      localStorage.setItem("usda-lang", l);
      if (s === "dark") localStorage.setItem("usda-theme", "dark");
    },
    [lang, scheme] as const,
  );
  await page.setViewportSize({ width, height });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", lang === "pt" ? "pt-BR" : "en");
  if (scheme === "dark") await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.waitForTimeout(300);
}

async function geometry(page: Page) {
  return page.evaluate(() => {
    const b = (e: Element) => {
      const r = e.getBoundingClientRect();
      return { top: r.top + scrollY, bottom: r.bottom + scrollY, left: r.left, right: r.right, width: r.width, height: r.height };
    };
    const tiles = [...document.querySelectorAll(".report-tile")].map((t) => ({
      ...b(t),
      value: b(t.querySelector('[data-testid="tile-value"]')!).top,
      footer: b(t.querySelector('[data-testid="tile-footer"]')!).top,
    }));
    const row = (id: string) => [...document.querySelectorAll(`[data-testid="${id}"] > *`)].map(b);
    return {
      h1: b(document.querySelector("h1")!),
      tiles,
      rowB: row("home-row-b"),
      rowC: row("home-row-c"),
      scrollW: document.documentElement.scrollWidth,
      scrollH: document.documentElement.scrollHeight,
    };
  });
}

const spread = (xs: number[]) => (xs.length ? Math.max(...xs) - Math.min(...xs) : 0);

/** Groups tiles into visual rows (same top). */
const rows = <T extends { top: number }>(tiles: T[]) => {
  const out: T[][] = [];
  for (const t of tiles) {
    const r = out.find((g) => Math.abs(g[0].top - t.top) <= 1);
    if (r) r.push(t);
    else out.push([t]);
  }
  return out;
};

async function tileCount(page: Page): Promise<number> {
  const doc = (await (await page.request.get("/data/insights.json")).json().catch(() => null)) as InsightsDoc | null;
  return doc ? homeTiles(doc).length : 0;
}

// Criteria 1–3 (and 10 for dark / PT).
async function checkTopAndRows(page: Page, width: number) {
  const g = await geometry(page);
  test.skip(!g.tiles.length, "no report tiles in this build");
  if (width >= 1280) {
    expect(g.tiles[0].top, "first tile right under the title").toBeLessThanOrEqual(150);
    expect(spread(g.tiles.map((t) => t.top)), "tile tops").toBeLessThanOrEqual(1);
    expect(spread(g.tiles.map((t) => t.height)), "tile heights").toBeLessThanOrEqual(1);
  }
  for (const r of rows(g.tiles)) {
    expect(spread(r.map((t) => t.value)), "values share a line").toBeLessThanOrEqual(1);
    expect(spread(r.map((t) => t.footer)), "footers share a line").toBeLessThanOrEqual(1);
  }
  if (width >= 1280) {
    for (const [name, r] of [["row B", g.rowB], ["row C", g.rowC]] as const) {
      expect(spread(r.map((c) => c.top)), `${name} tops`).toBeLessThanOrEqual(1);
      expect(spread(r.map((c) => c.bottom)), `${name} bottoms`).toBeLessThanOrEqual(1);
    }
    if (g.rowB.length === 2 && g.rowC.length === 2) expect(Math.abs(g.rowB[1].left - g.rowC[1].left), "shared 7 | 5 column line").toBeLessThanOrEqual(1);
  }
  return g;
}

test.describe("home layout", () => {
  test.beforeEach(({}, info) => test.skip(info.project.name !== "desktop", "viewport-driven: desktop project only"));

  for (const [w, h] of [
    [1440, 900],
    [1280, 800],
  ] as const) {
    test(`${w}: tiles under the title, aligned rows, no floating block, no half-empty card`, async ({ page }) => {
      await open(page, w, h);
      const g = await checkTopAndRows(page, w);
      // 4. Nothing floats between the title and the tiles (only the section label).
      expect(g.tiles[0].top - g.h1.bottom).toBeLessThanOrEqual(90);
      expect(await page.locator('[data-testid^="home-row"] [class*="self-center"]').count()).toBe(0);
      // 5. Every card is filled: the content above its footer takes >= 70% of its inner height.
      const fill = await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid^="home-row"] > *')].map((card) => {
          const cs = getComputedStyle(card);
          const r = card.getBoundingClientRect();
          const innerTop = r.top + parseFloat(cs.paddingTop) + parseFloat(cs.borderTopWidth);
          const innerBottom = r.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);
          const footer = card.querySelector('[data-testid="card-footer"]');
          const kids = [...card.children];
          const first = kids[0].getBoundingClientRect().top;
          const end = footer ? footer.getBoundingClientRect().top : kids[kids.length - 1].getBoundingClientRect().bottom;
          const inner = innerBottom - innerTop - (footer ? footer.getBoundingClientRect().height : 0);
          return { id: card.getAttribute("data-testid"), ratio: (end - first) / inner };
        }),
      );
      for (const f of fill) expect(f.ratio, `${f.id} content fill`).toBeGreaterThanOrEqual(0.7);
      if (w === 1440) {
        // 6. Lead and changes fully visible above the fold; about one screen in all.
        expect(Math.max(...g.rowB.map((c) => c.bottom))).toBeLessThanOrEqual(780);
        expect(g.scrollH).toBeLessThanOrEqual(1100);
      }
      expect(g.scrollW).toBe(w);
    });
  }

  for (const [w, h] of [
    [1024, 768],
    [768, 1024],
  ] as const) {
    test(`${w}: tiles 3 + 2 without an empty cell, values and footers aligned per row`, async ({ page }) => {
      await open(page, w, h);
      const g = await checkTopAndRows(page, w);
      expect(g.scrollW).toBe(w);
      if (g.tiles.length !== 5) return;
      const [a, b, c, d, e] = g.tiles;
      expect(spread([a.top, b.top, c.top])).toBeLessThanOrEqual(1);
      expect(Math.abs(d.top - e.top)).toBeLessThanOrEqual(1);
      expect(d.top).toBeGreaterThan(a.top);
      expect(d.width).toBeGreaterThan(a.width);
      expect(e.width).toBeGreaterThan(c.width);
      // Both rows fill the same width: no empty cell.
      expect(Math.abs(a.left - d.left)).toBeLessThanOrEqual(1);
      expect(Math.abs(c.right - e.right)).toBeLessThanOrEqual(1);
      // Below 1024px the sidebar is a 56px app bar and the header toggles are not repeated.
      if (w < 1024) {
        await expect(page.getByTestId("app-bar")).toBeVisible();
        await expect(page.getByRole("button", { name: "Português" })).toHaveCount(1);
      }
    });
  }

  test("360: app bar first, tiles on the first screen with n and release date, no sideways scroll", async ({ page }) => {
    await open(page, 360, 780);
    await checkPhone(page);
  });

  test("360: the Menu drawer holds the nav and closes with Escape", async ({ page }) => {
    await open(page, 360, 780);
    const menu = page.getByRole("button", { name: "Menu" });
    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav).toBeHidden();
    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
    await expect(nav.getByRole("link", { name: /Export Sales/ })).toBeVisible();
    await expect(nav.getByTestId("pipeline-releases")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(nav).toBeHidden();
    await expect(menu).toBeFocused();
    // Following a link closes it.
    await menu.click();
    await nav.getByRole("link", { name: /Export Sales/ }).click();
    await expect(page).toHaveURL(/\/reports\/export-sales\/$/);
    await expect(nav).toBeHidden();
  });

  // 10. Dark and PT keep the layout.
  for (const opts of [{ scheme: "dark" as const }, { lang: "pt" as const }, { scheme: "dark" as const, lang: "pt" as const }]) {
    const tag = `${opts.scheme ?? "light"} ${opts.lang ?? "en"}`;
    test(`${tag}: criteria 1–3 at 1440 and 1280, phone checks at 360`, async ({ page }) => {
      for (const [w, h] of [
        [1440, 900],
        [1280, 800],
      ] as const) {
        await open(page, w, h, opts);
        await checkTopAndRows(page, w);
      }
      await open(page, 360, 780, opts);
      await checkPhone(page);
    });
  }

  test("PT at 1440 changes the tile row height by at most one title line", async ({ page }) => {
    await open(page, 1440, 900);
    const en = await geometry(page);
    test.skip(!en.tiles.length, "no report tiles in this build");
    await open(page, 1440, 900, { lang: "pt" });
    const pt = await geometry(page);
    // One line of 12px copy (about 18px) plus its 6px row gap.
    expect(Math.abs(pt.tiles[0].height - en.tiles[0].height)).toBeLessThanOrEqual(24);
    expect(Math.abs(pt.rowB[0].height - en.rowB[0].height)).toBeLessThanOrEqual(30);
  });

  // 9 + 11. Honesty and scope: one finding per report with n, chip and dates; nothing removed returns.
  test("one tile per report, one lead, one revisions, one data and one explore card; n, chips and dates on each", async ({ page }) => {
    await open(page, 1440, 900);
    const n = await tileCount(page);
    test.skip(n === 0, "no insights.json in this build");
    const doc = (await (await page.request.get("/data/insights.json")).json()) as InsightsDoc;
    await expect(page.locator(".report-tile")).toHaveCount(n);
    await expect(page.getByTestId("lead-card")).toHaveCount(1);
    await expect(page.getByTestId("revisions-top")).toHaveCount(1);
    await expect(page.getByTestId("data-card")).toHaveCount(1);
    await expect(page.getByTestId("explore")).toHaveCount(await page.getByTestId("explore-link").count() ? 1 : 0);
    for (const id of ["lens-teaser", "kpi", "stu-rank", "data-strip"]) await expect(page.getByTestId(id), id).toHaveCount(0);
    // Tiles come before the lead card.
    const order = await page.evaluate(() => {
      const t = document.querySelector('[data-testid="report-tiles"]')!;
      const l = document.querySelector('[data-testid="lead-card"]')!;
      return Boolean(t.compareDocumentPosition(l) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(order).toBe(true);
    for (const { insight: i } of homeTiles(doc)) {
      const tile = page.locator(`.report-tile[data-insight-id="${i.id}"]`);
      await expect(tile.getByTestId("n")).toHaveText(`n = ${i.n}`);
      await expect(tile.getByTestId("small-sample")).toHaveCount(i.caveats.includes("small_sample") ? 1 : 0);
      await expect(tile.getByTestId("tile-date")).not.toBeEmpty();
      const notes = tile.getByTestId("card-notes");
      if (i.caveats.some((c) => c !== "small_sample")) await expect(notes).not.toHaveAttribute("open");
    }
    const lead = page.getByTestId("lead-card");
    await expect(lead.getByTestId("hero-text")).toBeVisible();
    if (await lead.getByTestId("insight-card").count()) {
      await expect(lead.getByTestId("n")).toBeVisible();
      await expect(lead.getByTestId("card-source")).toContainText("Source: ");
      const notes = lead.getByTestId("card-notes");
      if (await notes.count()) await expect(notes).not.toHaveAttribute("open");
    }
    await expect(page.getByTestId("revisions-source")).toContainText("Source: WASDE ");
  });
});

// 7. Phone: app bar first, the first tiles on the first screen, nothing sideways.
async function checkPhone(page: Page) {
  const g = await geometry(page);
  expect(g.scrollW, "no horizontal scroll").toBe(360);
  const bar = await page.getByTestId("app-bar").evaluate(box);
  expect(bar.height).toBeLessThanOrEqual(56);
  expect(bar.top).toBe(0);
  if (!g.tiles.length) return;
  expect(g.tiles[0].top).toBeLessThanOrEqual(230);
  expect(g.tiles.filter((t) => t.top < 780).length).toBeGreaterThanOrEqual(Math.min(3, g.tiles.length));
  const tiles = page.locator(".report-tile");
  for (let k = 0; k < (await tiles.count()); k++) {
    await expect(tiles.nth(k).getByTestId("n")).toBeVisible();
    await expect(tiles.nth(k).getByTestId("tile-date")).toBeVisible();
  }
}
