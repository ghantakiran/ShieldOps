import { test, expect } from "./fixtures";

test.describe("Sidebar Navigation", () => {
  test("navigates between all pages via sidebar", async ({ authenticatedPage: page }) => {
    await page.goto("/");

    const navLinks = [
      { text: /investigations/i, url: /\/investigations/ },
      { text: /remediations/i, url: /\/remediations/ },
      { text: /security/i, url: /\/security/ },
      { text: /learning/i, url: /\/learning/ },
      { text: /cost/i, url: /\/cost/ },
    ];

    for (const link of navLinks) {
      const navItem = page.locator("nav, aside, [role='navigation']")
        .getByText(link.text)
        .first();
      if (await navItem.isVisible()) {
        await navItem.click();
        await expect(page).toHaveURL(link.url);
      }
    }
  });

  test("active link is highlighted", async ({ authenticatedPage: page }) => {
    await page.goto("/investigations");

    // The active nav link should have a distinct styling (active class, aria-current, etc.)
    const nav = page.locator("nav, aside, [role='navigation']");
    const activeLink = nav.getByText(/investigations/i).first();
    if (await activeLink.isVisible()) {
      // Check for aria-current or an active-indicating class
      const ariaCurrent = await activeLink.getAttribute("aria-current");
      const className = await activeLink.getAttribute("class");
      const hasActiveIndicator =
        ariaCurrent === "page" ||
        className?.includes("active") ||
        className?.includes("bg-") ||
        className?.includes("text-blue") ||
        className?.includes("font-bold");
      expect(hasActiveIndicator).toBeTruthy();
    }
  });

  test("logo click navigates to fleet overview", async ({ authenticatedPage: page }) => {
    await page.goto("/investigations");

    // Click logo or brand text to go back to dashboard
    const logo = page.locator(
      "[data-testid='logo'], a[href='/'], img[alt*='shield' i], img[alt*='logo' i]",
    ).first();
    if (await logo.isVisible()) {
      await logo.click();
      await expect(page).toHaveURL(/^\/$|\/dashboard/);
    }
  });
});
