import { test, expect } from "./fixtures";

test.describe("Learning Page", () => {
  test("learning page loads with cycles table", async ({ authenticatedPage: page }) => {
    await page.goto("/learning");
    await expect(page.getByRole("heading", { name: /learning/i })).toBeVisible();
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });

  test("playbook library section renders", async ({ authenticatedPage: page }) => {
    await page.goto("/learning");
    await expect(page.getByText(/playbook/i).first()).toBeVisible();
  });

  test("Trigger Learning Cycle button is visible", async ({ authenticatedPage: page }) => {
    await page.goto("/learning");
    await expect(
      page.getByRole("button", { name: /trigger|start|run.*learning/i }),
    ).toBeVisible();
  });
});
