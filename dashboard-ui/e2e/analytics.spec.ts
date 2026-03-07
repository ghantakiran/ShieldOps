import { test, expect } from "./fixtures";

test.describe("Analytics Page", () => {
  test("should display the analytics page title", async ({ demoPage: page }) => {
    await page.goto("/app/analytics");
    await expect(page.getByRole("heading", { name: /^analytics$/i })).toBeVisible();
    await expect(
      page.getByText(/platform performance and resolution metrics/i),
    ).toBeVisible();
  });

  test("should show MTTR chart section", async ({ demoPage: page }) => {
    await page.goto("/app/analytics");
    await expect(
      page.getByRole("heading", { name: /mttr trend/i }),
    ).toBeVisible();
  });

  test("should show resolution rate section", async ({ demoPage: page }) => {
    await page.goto("/app/analytics");
    await expect(
      page.getByRole("heading", { name: /resolution rate/i }),
    ).toBeVisible();
  });

  test("should show agent accuracy section", async ({ demoPage: page }) => {
    await page.goto("/app/analytics");
    await expect(
      page.getByRole("heading", { name: /agent accuracy/i }),
    ).toBeVisible();
  });
});
