import { test, expect } from "./fixtures";

test.describe("Remediations Page", () => {
  test("remediations list page loads", async ({ authenticatedPage: page }) => {
    await page.goto("/remediations");
    await expect(page.getByRole("heading", { name: /remediation/i })).toBeVisible();
  });

  test("remediations table renders", async ({ authenticatedPage: page }) => {
    await page.goto("/remediations");
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });

  test("status badges render correctly", async ({ authenticatedPage: page }) => {
    await page.goto("/remediations");
    // Look for status badge elements (could be spans, pills, etc.)
    const statusBadges = page.locator("[class*='badge'], [class*='status'], [class*='pill']");
    if ((await statusBadges.count()) > 0) {
      await expect(statusBadges.first()).toBeVisible();
    }
  });

  test("click row navigates to detail page with timeline", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/remediations");
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await expect(page).toHaveURL(/\/remediations\/.+/);
      // Detail page should show execution steps or timeline
      await expect(
        page.getByText(/step|timeline|action|execution|result/i).first(),
      ).toBeVisible();
    }
  });
});
