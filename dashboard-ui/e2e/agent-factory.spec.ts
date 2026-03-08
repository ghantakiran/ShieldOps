import { test, expect } from "./fixtures";

test.describe("Agent Factory Pages", () => {
  test("pipeline runs page loads with data table", async ({ demoPage: page }) => {
    await page.goto("/app/pipeline");
    await expect(page.getByText("Pipeline Runs")).toBeVisible();
    await expect(page.getByText("Total Runs")).toBeVisible();
    await expect(page.getByText("Active")).toBeVisible();
    // Table should have rows
    const rows = page.locator("tbody tr");
    await expect(rows.first()).toBeVisible();
  });

  test("pipeline runs can be filtered by status", async ({ demoPage: page }) => {
    await page.goto("/app/pipeline");
    const filter = page.locator("select");
    await filter.selectOption("completed");
    // Only completed rows should remain
    const badges = page.locator("tbody").getByText("completed");
    await expect(badges.first()).toBeVisible();
  });

  test("pipeline run row expands to show timeline", async ({ demoPage: page }) => {
    await page.goto("/app/pipeline");
    // Click first row to expand
    const firstRow = page.locator("tbody tr").first();
    await firstRow.click();
    // Timeline should appear
    await expect(page.getByText("Timeline")).toBeVisible();
  });

  test("workflows page loads with active runs", async ({ demoPage: page }) => {
    await page.goto("/app/workflows");
    await expect(page.getByText("Workflows")).toBeVisible();
    await expect(page.getByText("active")).toBeVisible();
    // Should show escalation policies section
    await expect(page.getByText("Escalation Policies")).toBeVisible();
  });

  test("workflows run button opens dropdown", async ({ demoPage: page }) => {
    await page.goto("/app/workflows");
    await page.getByText("Run Workflow").click();
    await expect(page.getByText("Incident Response")).toBeVisible();
    await expect(page.getByText("Security Scan")).toBeVisible();
    await expect(page.getByText("Proactive Check")).toBeVisible();
  });

  test("api keys page loads with key table", async ({ demoPage: page }) => {
    await page.goto("/app/api-keys");
    await expect(page.getByText("API Keys")).toBeVisible();
    await expect(page.getByText("Create New Key")).toBeVisible();
    // Should show key prefix column
    const keyPrefixes = page.locator("code");
    await expect(keyPrefixes.first()).toBeVisible();
  });

  test("api keys create modal opens", async ({ demoPage: page }) => {
    await page.goto("/app/api-keys");
    await page.getByText("Create New Key").click();
    await expect(page.getByText("Create New API Key")).toBeVisible();
    await expect(page.getByPlaceholder("e.g. Production CI/CD")).toBeVisible();
  });

  test("agent factory page loads with task templates", async ({ demoPage: page }) => {
    await page.goto("/app");
    await expect(page.getByText("Agent Factory")).toBeVisible();
  });

  test("agent history page loads", async ({ demoPage: page }) => {
    await page.goto("/app/agent-history");
    await expect(page.getByText("Agent History")).toBeVisible();
  });

  test("war room page loads", async ({ demoPage: page }) => {
    await page.goto("/app/war-room");
    await expect(page.getByText("War Room")).toBeVisible();
  });
});
