import type { Page } from "@playwright/test";

/** The main navigation. Below 1024px it lives in the Menu drawer under the app bar, closed by
 *  default: this opens it first when the Menu button is showing. */
export async function mainNav(page: Page) {
  const menu = page.getByRole("button", { name: /^(Menu)$/ });
  if (await menu.isVisible()) {
    if ((await menu.getAttribute("aria-expanded")) !== "true") await menu.click();
  }
  return page.getByRole("navigation", { name: /^(Main|Principal)$/ });
}
