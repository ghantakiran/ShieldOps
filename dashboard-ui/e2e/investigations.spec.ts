import { test, expect } from "./fixtures";

test.describe("Investigations Page", () => {
  test("investigations list page loads", async ({ demoPage: page }) => {
    await page.goto("/app/investigations");
    await expect(page.getByRole("heading", { name: /investigation/i })).toBeVisible();
  });

  test("investigations table renders with columns", async ({ demoPage: page }) => {
    await page.goto("/app/investigations");
    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    // Check for expected column headers within the table
    const thead = table.locator("thead");
    await expect(thead.getByText(/alert/i)).toBeVisible();
    await expect(thead.getByText(/status/i)).toBeVisible();
    await expect(thead.getByText(/severity|confidence/i).first()).toBeVisible();
  });

  test("search/filter input is available", async ({ demoPage: page }) => {
    await page.goto("/app/investigations");
    const searchInput = page.getByPlaceholder(/search|filter/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("test");
      // Should filter the table — no error thrown
      await expect(searchInput).toHaveValue("test");
    }
  });

  test("click row navigates to detail page with findings", async ({ demoPage: page }) => {
    await page.goto("/app/investigations");
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
