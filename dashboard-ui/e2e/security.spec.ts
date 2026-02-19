import { test, expect } from "./fixtures";

test.describe("Security Page", () => {
  test("security page loads with scans table", async ({ authenticatedPage: page }) => {
    await page.goto("/security");
    await expect(page.getByRole("heading", { name: /security/i })).toBeVisible();
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });

  test("Run Scan button is visible", async ({ authenticatedPage: page }) => {
    await page.goto("/security");
    await expect(
      page.getByRole("button", { name: /run scan|start scan|new scan/i }),
    ).toBeVisible();
  });

  test("vulnerability list renders for selected scan", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/security");
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
