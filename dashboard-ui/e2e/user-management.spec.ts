import { test, expect } from "./fixtures";

test.describe("User Management Page", () => {
  test("should display user management page", async ({ demoPage: page }) => {
    await page.goto("/app/users");
    await expect(
      page.getByRole("heading", { name: /user management/i }),
    ).toBeVisible();
  });

  test("should show user table", async ({ demoPage: page }) => {
    await page.goto("/app/users");

    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    // Verify column headers
    await expect(page.getByText(/user/i).first()).toBeVisible();
    await expect(page.getByText(/role/i).first()).toBeVisible();
    await expect(page.getByText(/status/i).first()).toBeVisible();
  });

  test("should open invite modal", async ({ demoPage: page }) => {
    await page.goto("/app/users");

    // Click the "Invite User" button
    await page.getByRole("button", { name: /invite user/i }).click();

    // Modal should appear with form fields
    await expect(
      page.getByRole("heading", { name: /invite user/i }),
    ).toBeVisible();
  });

  test("should close invite modal on cancel", async ({ demoPage: page }) => {
    await page.goto("/app/users");

    // Open the modal
    await page.getByRole("button", { name: /invite user/i }).click();
    await expect(
      page.getByRole("heading", { name: /invite user/i }),
    ).toBeVisible();

    // Click the Cancel button inside the modal
    await page.getByRole("button", { name: /cancel/i }).click();

    // Modal should be closed
    await expect(
      page.getByRole("button", { name: /create user/i }),
    ).not.toBeVisible();
  });
});
