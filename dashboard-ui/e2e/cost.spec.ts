import { test, expect } from "./fixtures";

test.describe("Cost Page", () => {
  test("cost page loads with summary metrics", async ({ demoPage: page }) => {
    await page.goto("/app/cost");
    await expect(page.getByRole("heading", { name: "Cost Analysis" })).toBeVisible();
    // Should show cost summary cards or metrics
    await expect(
      page.getByText(/total|spend|savings|cost/i).first(),
    ).toBeVisible();
  });

  test("anomaly table renders", async ({ demoPage: page }) => {
    await page.goto("/app/cost");
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });
});
