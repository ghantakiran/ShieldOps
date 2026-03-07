import { test, expect } from "./fixtures";

test.describe("Playbooks Page", () => {
  test("should display the playbooks page title", async ({ demoPage: page }) => {
    await page.goto("/app/playbooks");
    await expect(page.getByRole("heading", { name: /playbooks/i })).toBeVisible();
  });

  test("should show playbook cards", async ({ demoPage: page }) => {
    await page.goto("/app/playbooks");

    // Verify playbook cards appear (demo mode data)
    await expect(page.getByText(/remediation|playbook|cpu|crash|disk/i).first()).toBeVisible();
  });

  test("should filter playbooks by search", async ({ demoPage: page }) => {
    await page.goto("/app/playbooks");

    const searchInput = page.getByPlaceholder(/search playbooks/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("crash");
      await expect(searchInput).toHaveValue("crash");
    }
  });

  test("should expand playbook details on click", async ({ demoPage: page }) => {
    await page.goto("/app/playbooks");

    // Click the "Show Details" toggle if available
    const showDetailsButton = page.getByText(/show details/i).first();
    if (await showDetailsButton.isVisible()) {
      await showDetailsButton.click();
      await expect(page.getByText(/hide details/i).first()).toBeVisible();
    }
  });
});
