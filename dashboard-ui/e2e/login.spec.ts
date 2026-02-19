import { test, expect } from "@playwright/test";

test.describe("Login Page", () => {
  test("shows login form with email and password fields", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in|log in/i })).toBeVisible();
  });

  test("valid login redirects to dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("admin@shieldops.dev");
    await page.getByLabel(/password/i).fill("shieldops-admin");
    await page.getByRole("button", { name: /sign in|log in/i }).click();

    // Should redirect away from /login
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("invalid credentials shows error message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("bad@example.com");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /sign in|log in/i }).click();

    await expect(page.getByText(/invalid|error|unauthorized/i)).toBeVisible();
  });

  test("empty fields prevent form submission via HTML validation", async ({ page }) => {
    await page.goto("/login");
    const emailInput = page.getByLabel(/email/i);

    // Click submit without filling anything
    await page.getByRole("button", { name: /sign in|log in/i }).click();

    // HTML5 required validation should keep us on the login page
    await expect(page).toHaveURL(/\/login/);
    // The email field should have a validation message
    const validity = await emailInput.evaluate(
      (el: HTMLInputElement) => el.validity.valueMissing,
    );
    expect(validity).toBe(true);
  });
});
