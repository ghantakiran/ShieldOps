import { test, expect, seedAuth, mockUsers } from "./fixtures";

test.describe("User Management Page", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await mockUsers(page);
    await seedAuth(page);
  });

  test("should display user management page for admin", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/users");
    await expect(
      page.getByRole("heading", { name: /user management/i }),
    ).toBeVisible();
    await expect(page.getByText(/manage users, roles, and access/i)).toBeVisible();
  });

  test("should show user table", async ({ authenticatedPage: page }) => {
    await page.goto("/users");

    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    // Verify column headers
    await expect(page.getByText(/user/i).first()).toBeVisible();
    await expect(page.getByText(/role/i).first()).toBeVisible();
    await expect(page.getByText(/status/i).first()).toBeVisible();

    // Verify user data renders
    await expect(page.getByText("Admin User")).toBeVisible();
    await expect(page.getByText("admin@shieldops.dev")).toBeVisible();
    await expect(page.getByText("Op User")).toBeVisible();
    await expect(page.getByText("View User")).toBeVisible();
  });

  test("should open invite modal", async ({ authenticatedPage: page }) => {
    await page.goto("/users");

    // Click the "Invite User" button
    await page.getByRole("button", { name: /invite user/i }).click();

    // Modal should appear with form fields
    await expect(
      page.getByRole("heading", { name: /invite user/i }),
    ).toBeVisible();
    await expect(page.getByPlaceholder(/jane doe/i)).toBeVisible();
    await expect(page.getByPlaceholder(/jane@company\.com/i)).toBeVisible();
    await expect(page.getByPlaceholder(/minimum 8 characters/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /create user/i }),
    ).toBeVisible();
  });

  test("should close invite modal on cancel", async ({ authenticatedPage: page }) => {
    await page.goto("/users");

    // Open the modal
    await page.getByRole("button", { name: /invite user/i }).click();
    await expect(
      page.getByRole("heading", { name: /invite user/i }),
    ).toBeVisible();

    // Click the Cancel button inside the modal
    await page.getByRole("button", { name: /cancel/i }).click();

    // Modal should be closed — the "Create User" button should no longer be visible
    await expect(
      page.getByRole("button", { name: /create user/i }),
    ).not.toBeVisible();
  });

  test("should show role dropdown for each user", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/users");

    // Each user row should have a role <select> element
    const roleSelects = page.locator("table tbody select");
    expect(await roleSelects.count()).toBeGreaterThanOrEqual(1);

    // The first select (for Admin User) should have admin/operator/viewer options
    const firstSelect = roleSelects.first();
    await expect(firstSelect).toBeVisible();

    const options = firstSelect.locator("option");
    const optionTexts = await options.allTextContents();
    expect(optionTexts).toContain("Admin");
    expect(optionTexts).toContain("Operator");
    expect(optionTexts).toContain("Viewer");
  });
});
