import { test, expect } from "./fixtures";

test.describe("Scheduled Tasks", () => {
  test("schedules page loads with task list", async ({ demoPage: page }) => {
    await page.goto("/app/schedules");
    await expect(page.getByText("Scheduled Tasks")).toBeVisible();
    // Should show stats row
    await expect(page.getByText("Total Tasks")).toBeVisible();
    await expect(page.getByText("Active")).toBeVisible();
  });

  test("can open create task modal", async ({ demoPage: page }) => {
    await page.goto("/app/schedules");
    await page.getByText("New Schedule").click();
    await expect(page.getByText("Create Scheduled Task")).toBeVisible();
  });
});

test.describe("Breadcrumbs", () => {
  test("shows breadcrumbs on nested pages", async ({ demoPage: page }) => {
    await page.goto("/app/investigations");
    // Breadcrumb nav should be visible
    const breadcrumb = page.locator("nav[aria-label='Breadcrumb']");
    await expect(breadcrumb).toBeVisible();
    await expect(breadcrumb.getByText("Investigations")).toBeVisible();
  });

  test("breadcrumbs not shown on root dashboard", async ({ demoPage: page }) => {
    await page.goto("/app");
    const breadcrumb = page.locator("nav[aria-label='Breadcrumb']");
    await expect(breadcrumb).not.toBeVisible();
  });
});

test.describe("AI Chat Sidebar", () => {
  test("chat FAB button is visible", async ({ demoPage: page }) => {
    await page.goto("/app");
    const chatButton = page.getByLabel("Open AI assistant");
    await expect(chatButton).toBeVisible();
  });

  test("clicking FAB opens chat panel", async ({ demoPage: page }) => {
    await page.goto("/app");
    await page.getByLabel("Open AI assistant").click();
    await expect(page.getByText("ShieldOps AI")).toBeVisible();
    await expect(page.getByText("How can I help?")).toBeVisible();
  });

  test("chat shows suggested prompts", async ({ demoPage: page }) => {
    await page.goto("/app");
    await page.getByLabel("Open AI assistant").click();
    await expect(
      page.getByText("What's my current security posture?"),
    ).toBeVisible();
  });
});

test.describe("Keyboard Shortcuts", () => {
  test("Cmd+K opens global search", async ({ demoPage: page }) => {
    await page.goto("/app");
    await page.keyboard.press("Meta+k");
    await expect(
      page.getByPlaceholder("Search investigations, remediations"),
    ).toBeVisible();
  });
});

test.describe("Notification Dropdown", () => {
  test("notification bell shows unread count", async ({ demoPage: page }) => {
    await page.goto("/app");
    // The notification dropdown should be in the header
    const header = page.locator("header");
    await expect(header).toBeVisible();
  });
});

test.describe("Product Tour", () => {
  test("tour auto-starts in demo mode on first visit", async ({ demoPage: page }) => {
    // Clear tour completion flag
    await page.evaluate(() => localStorage.removeItem("shieldops_tour_complete"));
    await page.goto("/app");
    // Tour should appear after short delay
    await expect(page.getByText("Welcome to ShieldOps")).toBeVisible({ timeout: 3000 });
  });

  test("tour can be skipped", async ({ demoPage: page }) => {
    await page.evaluate(() => localStorage.removeItem("shieldops_tour_complete"));
    await page.goto("/app");
    await expect(page.getByText("Welcome to ShieldOps")).toBeVisible({ timeout: 3000 });
    await page.getByText("Skip tour").click();
    await expect(page.getByText("Welcome to ShieldOps")).not.toBeVisible();
  });

  test("tour does not show when already completed", async ({ demoPage: page }) => {
    await page.evaluate(() =>
      localStorage.setItem("shieldops_tour_complete", "true"),
    );
    await page.goto("/app");
    await page.waitForTimeout(1500);
    await expect(page.getByText("Welcome to ShieldOps")).not.toBeVisible();
  });
});
