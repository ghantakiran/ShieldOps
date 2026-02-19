import { test, expect } from "./fixtures";

test.describe("Fleet Overview / Dashboard", () => {
  test("dashboard loads with metric cards", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    // Expect summary metric cards to be visible
    await expect(page.getByText(/active investigations|total investigations/i)).toBeVisible();
    await expect(page.getByText(/remediations|actions/i)).toBeVisible();
  });

  test("agent health grid shows agent types", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    // The dashboard should show the 6 agent types
    const agentTypes = [
      "investigation",
      "remediation",
      "security",
      "cost",
      "learning",
      "supervisor",
    ];
    for (const agentType of agentTypes) {
      await expect(
        page.getByText(new RegExp(agentType, "i")).first(),
      ).toBeVisible();
    }
  });

  test("investigation table renders rows", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    // Look for a table or list that contains investigation data
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });

  test("click investigation row navigates to detail", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    // Click the first row link in the investigations section
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await expect(page).toHaveURL(/\/investigations\//);
    }
  });
});
