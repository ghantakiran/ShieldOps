import { test, expect } from "./fixtures";

test.describe("Learning Page", () => {
  test("learning page loads with cycles section", async ({ demoPage: page }) => {
    await page.goto("/app/learning");
    await expect(page.getByRole("heading", { name: "Learning Center" })).toBeVisible();
    // Wait for cycle data to render (table on desktop, cards on mobile)
    await expect(page.getByText(/pattern_extraction|threshold_tuning/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("playbook library section renders", async ({ demoPage: page }) => {
    await page.goto("/app/learning");
    await expect(page.getByText(/playbook/i).first()).toBeVisible();
  });

  test("Trigger Learning Cycle button is visible", async ({ demoPage: page }) => {
    await page.goto("/app/learning");
    await expect(
      page.getByRole("button", { name: /trigger|start|run.*learning/i }),
    ).toBeVisible();
  });
});
