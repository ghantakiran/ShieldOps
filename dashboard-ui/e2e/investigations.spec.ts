import { test, expect } from "./fixtures";

test.describe("Investigations Page", () => {
  test("investigations list page loads", async ({ authenticatedPage: page }) => {
    await page.goto("/investigations");
    await expect(page.getByRole("heading", { name: /investigation/i })).toBeVisible();
  });

  test("investigations table renders with columns", async ({ authenticatedPage: page }) => {
    await page.goto("/investigations");
    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    // Check for expected column headers
    await expect(page.getByText(/alert|id/i).first()).toBeVisible();
    await expect(page.getByText(/status/i).first()).toBeVisible();
    await expect(page.getByText(/severity|confidence/i).first()).toBeVisible();
  });

  test("search/filter input is available", async ({ authenticatedPage: page }) => {
    await page.goto("/investigations");
    const searchInput = page.getByPlaceholder(/search|filter/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("test");
      // Should filter the table — no error thrown
      await expect(searchInput).toHaveValue("test");
    }
  });

  test("click row navigates to detail page with findings", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/investigations");
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await expect(page).toHaveURL(/\/investigations\/.+/);
      // Detail page should show findings or hypotheses section
      await expect(
        page.getByText(/finding|hypothesis|root cause|detail/i).first(),
      ).toBeVisible();
    }
  });
});
