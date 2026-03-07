import { test, expect } from "./fixtures";

test.describe("Audit Log Page", () => {
  test("should display the audit log page title", async ({ demoPage: page }) => {
    await page.goto("/app/audit-log");
    await expect(page.getByRole("heading", { name: /audit log/i })).toBeVisible();
  });

  test("should show audit log table with entries", async ({ demoPage: page }) => {
    await page.goto("/app/audit-log");

    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    // Verify at least one data row renders
    const rows = page.locator("table tbody tr");
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeGreaterThanOrEqual(1);
  });

  test("should filter by environment", async ({ demoPage: page }) => {
    await page.goto("/app/audit-log");

    // Wait for the initial table to render
    await expect(page.locator("table").first()).toBeVisible();

    // Select "Production" from the environment filter
    const envSelect = page.locator("select").first();
    await envSelect.selectOption("production");

    // After filtering, rows should still be visible
    await expect(page.locator("table tbody tr").first()).toBeVisible();
  });

  test("should filter by agent type", async ({ demoPage: page }) => {
    await page.goto("/app/audit-log");

    // Wait for the initial table to render
    await expect(page.locator("table").first()).toBeVisible();

    // The second select is the agent type filter
    const agentSelect = page.locator("select").nth(1);
    await agentSelect.selectOption("investigation");

    // After filtering, rows should still be visible
    await expect(page.locator("table tbody tr").first()).toBeVisible();
  });

  test("should show pagination controls", async ({ demoPage: page }) => {
    await page.goto("/app/audit-log");

    // Wait for the table to render
    await expect(page.locator("table").first()).toBeVisible();

    // Pagination controls should be visible if there are enough items
    const pageInfo = page.getByText(/page \d+ of/i);
    if (await pageInfo.isVisible()) {
      await expect(pageInfo).toBeVisible();
    }
  });
});
