import { test, expect } from "./fixtures";

test.describe("Cost Page", () => {
  test("cost page loads with summary metrics", async ({ authenticatedPage: page }) => {
    await page.goto("/cost");
    await expect(page.getByRole("heading", { name: /cost/i })).toBeVisible();
    // Should show cost summary cards or metrics
    await expect(
      page.getByText(/total|spend|savings|cost/i).first(),
    ).toBeVisible();
  });

  test("anomaly table renders", async ({ authenticatedPage: page }) => {
    await page.goto("/cost");
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });
});
