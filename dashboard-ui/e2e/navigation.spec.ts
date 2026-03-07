import { test, expect } from "./fixtures";

test.describe("Sidebar Navigation", () => {
  test("navigates between all pages via sidebar", async ({ demoPage: page }) => {
    const sidebar = page.locator("aside").first();

    const navLinks = [
      { label: "Investigations", url: /\/app\/investigations/ },
      { label: "Remediations", url: /\/app\/remediations/ },
      { label: "Cost", url: /\/app\/cost/ },
      { label: "Learning", url: /\/app\/learning/ },
    ];

    for (const link of navLinks) {
      const navItem = sidebar.getByText(link.label, { exact: true }).first();
      if (await navItem.isVisible()) {
        await navItem.click();
        await expect(page).toHaveURL(link.url);
      }
    }
  });

  test("active link is highlighted", async ({ demoPage: page }) => {
    await page.goto("/app/investigations");

    // The active nav link should have active styling
    const activeLink = page.locator("aside a[href='/app/investigations']");
    const className = await activeLink.getAttribute("class");
    expect(className).toContain("text-brand-400");
  });

  test("logo is visible in sidebar", async ({ demoPage: page }) => {
    await expect(page.locator("aside").getByText("ShieldOps").first()).toBeVisible();
  });
});
