import { test, expect, seedAuth, mockAuditLogs } from "./fixtures";

test.describe("Audit Log Page", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await mockAuditLogs(page);
    await seedAuth(page);
  });

  test("should display the audit log page title", async ({ authenticatedPage: page }) => {
    await page.goto("/audit-log");
    await expect(page.getByRole("heading", { name: /audit log/i })).toBeVisible();
  });

  test("should show audit log table with entries", async ({ authenticatedPage: page }) => {
    await page.goto("/audit-log");

    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    // Verify column headers are present
    await expect(page.getByText(/timestamp/i).first()).toBeVisible();
    await expect(page.getByText(/agent/i).first()).toBeVisible();
    await expect(page.getByText(/action/i).first()).toBeVisible();
    await expect(page.getByText(/outcome/i).first()).toBeVisible();

    // Verify at least one data row renders
    const rows = page.locator("table tbody tr");
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeGreaterThanOrEqual(1);
  });

  test("should filter by environment", async ({ authenticatedPage: page }) => {
    await page.goto("/audit-log");

    // Wait for the initial table to render
    await expect(page.locator("table").first()).toBeVisible();

    // Select "Production" from the environment filter
    const envSelect = page.locator("select").first();
    await envSelect.selectOption("production");

    // After filtering, rows should still be visible (our mock has production entries)
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    // The filtered entries should show "production" environment
    await expect(page.getByText("production").first()).toBeVisible();
  });

  test("should filter by agent type", async ({ authenticatedPage: page }) => {
    await page.goto("/audit-log");

    // Wait for the initial table to render
    await expect(page.locator("table").first()).toBeVisible();

    // The second select is the agent type filter
    const agentSelect = page.locator("select").nth(1);
    await agentSelect.selectOption("investigation");

    // After filtering, rows should still be visible
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    // The filtered entries should show "investigation" agent type
    await expect(page.getByText("investigation").first()).toBeVisible();
  });

  test("should paginate results", async ({ authenticatedPage: page }) => {
    // Override the audit-logs route to return enough items for pagination
    await page.route("**/api/v1/audit-logs*", (route) => {
      const url = new URL(route.request().url());
      const offset = parseInt(url.searchParams.get("offset") || "0", 10);

      // Simulate 120 total entries with 50-per-page
      const items = Array.from({ length: 50 }, (_, i) => ({
        id: `al_${offset + i + 1}`,
        timestamp: "2026-02-19T10:30:00Z",
        agent_type: "investigation",
        action: `action_${offset + i + 1}`,
        target_resource: `resource-${offset + i + 1}`,
        environment: "production",
        risk_level: "low",
        policy_evaluation: "allowed",
        approval_status: null,
        outcome: "success",
        reasoning: "Completed",
        actor: "agent:investigation-01",
      }));

      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items,
          total: 120,
          limit: 50,
          offset,
        }),
      });
    });

    await page.goto("/audit-log");

    // Wait for the table to render
    await expect(page.locator("table").first()).toBeVisible();

    // Pagination controls should be visible
    await expect(page.getByText(/page 1 of/i)).toBeVisible();

    // Click the next page button (ChevronRight)
    const nextButton = page.locator("button").filter({ has: page.locator("svg") }).last();
    await nextButton.click();

    // Should show page 2
    await expect(page.getByText(/page 2 of/i)).toBeVisible();
  });
});
