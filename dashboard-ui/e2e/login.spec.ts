import { test, expect } from "@playwright/test";

test.describe("Login Page", () => {
  test("shows login form with email and password fields", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();
  });

  test("shows ShieldOps branding", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("ShieldOps").first()).toBeVisible();
  });

  test("empty fields prevent form submission via HTML validation", async ({ page }) => {
    await page.goto("/login");
    const emailInput = page.getByLabel(/email/i);

    // Click submit without filling anything
    await page.getByRole("button", { name: "Sign In", exact: true }).click();

    // HTML5 required validation should keep us on the login page
    await expect(page).toHaveURL(/\/login/);
    // The email field should have a validation message
    const validity = await emailInput.evaluate(
      (el: HTMLInputElement) => el.validity.valueMissing,
    );
    expect(validity).toBe(true);
  });
});
