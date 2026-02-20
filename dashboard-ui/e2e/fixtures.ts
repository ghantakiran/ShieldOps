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

// ── Mock API response factories ──────────────────────────────────────

/** Seed both localStorage keys so ProtectedRoute + useAuthStore.hydrate() work. */
export async function seedAuth(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem("shieldops_token", "test-jwt-token");
    localStorage.setItem(
      "shieldops_user",
      JSON.stringify({
        id: "usr_001",
        email: "admin@shieldops.dev",
        name: "Admin User",
        role: "admin",
        is_active: true,
      }),
    );
  });
}

/** Mock audit-logs endpoint. */
export function mockAuditLogs(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/audit-logs*", (route) => {
    const url = new URL(route.request().url());
    const environment = url.searchParams.get("environment") || "";
    const agentType = url.searchParams.get("agent_type") || "";

    const allItems = [
      {
        id: "al_001",
        timestamp: "2026-02-19T10:30:00Z",
        agent_type: "investigation",
        action: "analyze_logs",
        target_resource: "web-server-prod-01",
        environment: "production",
        risk_level: "low",
        policy_evaluation: "allowed",
        approval_status: null,
        outcome: "success",
        reasoning: "Log analysis completed",
        actor: "agent:investigation-01",
      },
      {
        id: "al_002",
        timestamp: "2026-02-19T10:45:00Z",
        agent_type: "remediation",
        action: "restart_service",
        target_resource: "api-gateway-staging",
        environment: "staging",
        risk_level: "medium",
        policy_evaluation: "allowed",
        approval_status: "approved",
        outcome: "success",
        reasoning: "Service restarted after OOM",
        actor: "agent:remediation-01",
      },
      {
        id: "al_003",
        timestamp: "2026-02-19T11:00:00Z",
        agent_type: "security",
        action: "rotate_credentials",
        target_resource: "db-prod-cluster",
        environment: "production",
        risk_level: "high",
        policy_evaluation: "allowed",
        approval_status: "approved",
        outcome: "success",
        reasoning: "Credential rotation per policy",
        actor: "agent:security-01",
      },
    ];

    let filtered = allItems;
    if (environment) {
      filtered = filtered.filter((i) => i.environment === environment);
    }
    if (agentType) {
      filtered = filtered.filter((i) => i.agent_type === agentType);
    }

    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: filtered,
        total: filtered.length,
        limit: 50,
        offset: 0,
      }),
    });
  });
}

/** Mock playbooks list endpoint. */
export function mockPlaybooks(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/playbooks", (route) => {
    if (route.request().method() !== "GET") {
      route.fallback();
      return;
    }
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        playbooks: [
          {
            name: "high-cpu-remediation",
            version: "1.2.0",
            description: "Automated remediation for sustained high CPU alerts",
            trigger: { alert_type: "high_cpu", severity: ["critical", "high"] },
            decision_tree_count: 5,
          },
          {
            name: "pod-crash-loop-fix",
            version: "1.0.0",
            description: "Investigate and fix Kubernetes pod crash loops",
            trigger: { alert_type: "pod_crash_loop", severity: ["critical"] },
            decision_tree_count: 3,
          },
          {
            name: "disk-full-cleanup",
            version: "2.0.1",
            description: "Clean up disk space when usage exceeds threshold",
            trigger: { alert_type: "disk_full", severity: ["high", "medium"] },
            decision_tree_count: 4,
          },
        ],
        total: 3,
      }),
    });
  });
}

/** Mock playbook detail endpoint (for expand). */
export function mockPlaybookDetail(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/playbooks/*", (route) => {
    if (route.request().url().includes("/trigger")) {
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
      return;
    }
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        name: "high-cpu-remediation",
        version: "1.2.0",
        description: "Automated remediation for sustained high CPU alerts",
        trigger: { alert_type: "high_cpu", severity: ["critical", "high"] },
        investigation: { check_processes: true, analyze_metrics: true },
        remediation: { restart_service: true, scale_up: true },
        validation: { verify_cpu_below_threshold: true },
      }),
    });
  });
}

/** Mock users list endpoint. */
export function mockUsers(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/users*", (route) => {
    if (route.request().method() !== "GET") {
      route.fallback();
      return;
    }
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "usr_001",
            email: "admin@shieldops.dev",
            name: "Admin User",
            role: "admin",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "usr_002",
            email: "operator@shieldops.dev",
            name: "Op User",
            role: "operator",
            is_active: true,
            created_at: "2026-01-15T00:00:00Z",
          },
          {
            id: "usr_003",
            email: "viewer@shieldops.dev",
            name: "View User",
            role: "viewer",
            is_active: false,
            created_at: "2026-02-01T00:00:00Z",
          },
        ],
        total: 3,
        limit: 50,
        offset: 0,
      }),
    });
  });
}

/** Mock analytics MTTR trend endpoint. */
export function mockAnalyticsMttr(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/analytics/mttr*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        period: "30d",
        data_points: [
          { date: "2026-02-10T00:00:00Z", avg_duration_ms: 360000, count: 5 },
          { date: "2026-02-11T00:00:00Z", avg_duration_ms: 300000, count: 8 },
          { date: "2026-02-12T00:00:00Z", avg_duration_ms: 240000, count: 6 },
          { date: "2026-02-13T00:00:00Z", avg_duration_ms: 180000, count: 10 },
        ],
        current_mttr_minutes: 3.0,
      }),
    });
  });
}

/** Mock analytics summary endpoint. */
export function mockAnalyticsSummary(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/analytics/summary*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_investigations: 42,
        total_remediations: 28,
        auto_resolved_percent: 67.5,
        mean_time_to_resolve_seconds: 180,
        investigations_by_status: {
          completed: 30,
          in_progress: 8,
          pending: 2,
          failed: 2,
        },
        remediations_by_status: {
          completed: 20,
          executing: 4,
          pending_approval: 2,
          failed: 1,
          rolled_back: 1,
        },
      }),
    });
  });
}

/** Mock analytics resolution-rate endpoint. */
export function mockAnalyticsResolutionRate(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/analytics/resolution-rate*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        period: "30d",
        automated_rate: 0.675,
        manual_rate: 0.325,
        total_incidents: 40,
      }),
    });
  });
}

/** Mock analytics agent-accuracy endpoint. */
export function mockAnalyticsAgentAccuracy(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/analytics/agent-accuracy*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        period: "30d",
        accuracy: 0.92,
        total_investigations: 42,
      }),
    });
  });
}

/** Mock agents list endpoint. */
export function mockAgentsList(page: import("@playwright/test").Page) {
  return page.route("**/api/v1/agents/*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "agent_001",
          agent_type: "investigation",
          environment: "production",
          status: "running",
          last_heartbeat: "2026-02-19T10:30:00Z",
          registered_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "agent_002",
          agent_type: "remediation",
          environment: "production",
          status: "idle",
          last_heartbeat: "2026-02-19T10:29:00Z",
          registered_at: "2026-01-01T00:00:00Z",
        },
      ]),
    });
  });
}
