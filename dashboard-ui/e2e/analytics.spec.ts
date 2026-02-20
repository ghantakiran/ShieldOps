import {
  test,
  expect,
  seedAuth,
  mockAnalyticsSummary,
  mockAnalyticsMttr,
  mockAnalyticsResolutionRate,
  mockAnalyticsAgentAccuracy,
  mockAgentsList,
} from "./fixtures";

test.describe("Analytics Page", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    // The Analytics page fetches multiple endpoints concurrently:
    // - /analytics/summary (main page load)
    // - /agents/ (for active agent count)
    // - /analytics/mttr (MTTR trend chart)
    // - /analytics/resolution-rate (resolution rate chart)
    // - /analytics/agent-accuracy (agent accuracy gauge)
    await mockAnalyticsSummary(page);
    await mockAgentsList(page);
    await mockAnalyticsMttr(page);
    await mockAnalyticsResolutionRate(page);
    await mockAnalyticsAgentAccuracy(page);
    await seedAuth(page);
  });

  test("should display the analytics page title", async ({ authenticatedPage: page }) => {
    await page.goto("/analytics");
    await expect(page.getByRole("heading", { name: /^analytics$/i })).toBeVisible();
    await expect(
      page.getByText(/platform performance and resolution metrics/i),
    ).toBeVisible();
  });

  test("should show MTTR chart section", async ({ authenticatedPage: page }) => {
    await page.goto("/analytics");

    // The MTTR Trend section heading
    await expect(
      page.getByRole("heading", { name: /mttr trend/i }),
    ).toBeVisible();

    // Current MTTR badge should display
    await expect(page.getByText(/current.*3\.0m/i)).toBeVisible();
  });

  test("should show resolution rate section", async ({ authenticatedPage: page }) => {
    await page.goto("/analytics");

    // The Resolution Rate section heading
    await expect(
      page.getByRole("heading", { name: /resolution rate/i }),
    ).toBeVisible();

    // Should show incident count badge
    await expect(page.getByText(/40 incidents/i)).toBeVisible();
  });

  test("should show agent accuracy section", async ({ authenticatedPage: page }) => {
    await page.goto("/analytics");

    // The Agent Accuracy section heading
    await expect(
      page.getByRole("heading", { name: /agent accuracy/i }),
    ).toBeVisible();

    // Should display the accuracy percentage
    await expect(page.getByText("92%")).toBeVisible();
  });
});
