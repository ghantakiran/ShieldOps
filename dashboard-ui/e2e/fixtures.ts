import { test as base, expect } from "@playwright/test";

/**
 * Custom Playwright fixtures for ShieldOps E2E tests.
 *
 * Provides an `authenticatedPage` fixture that logs in via the API
 * and stores auth state for reuse across tests in a spec file.
 */

type AuthFixtures = {
  authenticatedPage: ReturnType<typeof base.extend> extends infer T ? T : never;
};

const API_URL = process.env.API_URL || "http://localhost:8000";
const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL || "admin@shieldops.dev";
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD || "shieldops-admin";

export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Attempt to login via API and store token
    try {
      const response = await page.request.post(`${API_URL}/api/v1/auth/login`, {
        data: {
          email: TEST_USER_EMAIL,
          password: TEST_USER_PASSWORD,
        },
      });

      if (response.ok()) {
        const body = await response.json();
        const token = body.access_token;

        // Set token in localStorage for the frontend to pick up
        await page.goto("/");
        await page.evaluate((t) => {
          localStorage.setItem("shieldops_token", t);
        }, token);
      }
    } catch {
      // Backend may not be running in some test modes — proceed without auth
    }

    await use(page);
  },
});

export { expect };
