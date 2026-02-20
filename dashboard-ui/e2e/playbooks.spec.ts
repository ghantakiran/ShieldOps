import {
  test,
  expect,
  seedAuth,
  mockPlaybooks,
  mockPlaybookDetail,
} from "./fixtures";

test.describe("Playbooks Page", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await mockPlaybooks(page);
    await mockPlaybookDetail(page);
    await seedAuth(page);
  });

  test("should display the playbooks page title", async ({ authenticatedPage: page }) => {
    await page.goto("/playbooks");
    await expect(page.getByRole("heading", { name: /playbooks/i })).toBeVisible();
  });

  test("should show playbook cards", async ({ authenticatedPage: page }) => {
    await page.goto("/playbooks");

    // Verify playbook names appear
    await expect(page.getByText("high-cpu-remediation")).toBeVisible();
    await expect(page.getByText("pod-crash-loop-fix")).toBeVisible();
    await expect(page.getByText("disk-full-cleanup")).toBeVisible();

    // Verify descriptions appear
    await expect(
      page.getByText(/automated remediation for sustained high cpu/i),
    ).toBeVisible();
  });

  test("should filter playbooks by search", async ({ authenticatedPage: page }) => {
    await page.goto("/playbooks");

    // All three cards should be visible initially
    await expect(page.getByText("high-cpu-remediation")).toBeVisible();
    await expect(page.getByText("pod-crash-loop-fix")).toBeVisible();

    // Type a search term that matches only one playbook
    const searchInput = page.getByPlaceholder(/search playbooks/i);
    await searchInput.fill("crash");

    // Only the matching playbook should remain visible
    await expect(page.getByText("pod-crash-loop-fix")).toBeVisible();
    await expect(page.getByText("high-cpu-remediation")).not.toBeVisible();
    await expect(page.getByText("disk-full-cleanup")).not.toBeVisible();
  });

  test("should expand playbook details on click", async ({ authenticatedPage: page }) => {
    await page.goto("/playbooks");

    // Click the "Show Details" toggle on the first playbook card
    const showDetailsButton = page.getByText(/show details/i).first();
    await expect(showDetailsButton).toBeVisible();
    await showDetailsButton.click();

    // The expanded detail should show investigation/remediation sections
    await expect(page.getByText(/investigation/i).first()).toBeVisible();
    await expect(page.getByText(/remediation/i).first()).toBeVisible();

    // The toggle text should change to "Hide Details"
    await expect(page.getByText(/hide details/i).first()).toBeVisible();
  });
});
