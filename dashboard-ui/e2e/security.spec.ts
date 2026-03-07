import { test, expect } from "./fixtures";

test.describe("Security Page", () => {
  test("security page loads with overview metrics", async ({ demoPage: page }) => {
    await page.goto("/app/security");
    await expect(page.getByRole("heading", { name: /security/i }).first()).toBeVisible();
    // Overview tab shows metric cards, not a table
    await expect(page.getByText(/security score|total vulnerabilities/i).first()).toBeVisible();
  });

  test("Run Scan button is visible", async ({ demoPage: page }) => {
    await page.goto("/app/security");
    await expect(
      page.getByRole("button", { name: /run scan|start scan|new scan/i }),
    ).toBeVisible();
  });

  test("vulnerability list renders for selected scan", async ({ demoPage: page }) => {
    await page.goto("/app/security");
    // Click the first scan row if available
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      // Should show vulnerabilities or scan details
      await expect(
        page.getByText(/vulnerabilit|cve|finding|severity/i).first(),
      ).toBeVisible();
    }
  });
});
