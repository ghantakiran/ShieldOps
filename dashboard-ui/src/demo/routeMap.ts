/**
 * Maps API URL patterns to demo fixture handlers.
 * When demo mode is active, the API client resolves requests from here
 * instead of making real HTTP calls.
 */
import { DEMO_USER } from "./config";
import * as fixtures from "./fixtures";
import { DEMO_PIPELINE_RUNS } from "./pipelineData";
import { DEMO_WORKFLOW_RUNS } from "./workflowData";
import { DEMO_API_KEYS } from "./apiKeyData";

type RouteHandler = (params: Record<string, string>, body?: unknown) => unknown;

interface Route {
  pattern: RegExp;
  handler: RouteHandler;
}

const routes: Route[] = [
  // ── Auth ──────────────────────────────────────────────────────────
  {
    pattern: /^\/auth\/login$/,
    handler: () => ({ access_token: "demo-token-shieldops-2024", token_type: "bearer" }),
  },
  {
    pattern: /^\/auth\/me$/,
    handler: () => DEMO_USER,
  },

  // ── Agents ────────────────────────────────────────────────────────
  {
    pattern: /^\/agents\/?\??.*$/,
    handler: () => fixtures.getAgents(),
  },

  // ── Investigations ────────────────────────────────────────────────
  {
    pattern: /^\/investigations\/([^/?]+)\/timeline$/,
    handler: (p) => fixtures.getInvestigationTimeline(p[1]),
  },
  {
    pattern: /^\/investigations\/([^/?]+)$/,
    handler: (p) => fixtures.getInvestigationDetail(p[1]) ?? {},
  },
  {
    pattern: /^\/investigations\/?\??.*$/,
    handler: () => fixtures.getInvestigations(),
  },

  // ── Remediations ──────────────────────────────────────────────────
  {
    pattern: /^\/remediations\/([^/?]+)\/rollback$/,
    handler: () => ({ status: "rolled_back", message: "Rollback initiated (demo)" }),
  },
  {
    pattern: /^\/remediations\/([^/?]+)$/,
    handler: (p) => fixtures.getRemediationDetail(p[1]) ?? {},
  },
  {
    pattern: /^\/remediations\/?\??.*$/,
    handler: () => fixtures.getRemediations(),
  },

  // ── Security ──────────────────────────────────────────────────────
  {
    pattern: /^\/security\/scans/,
    handler: () => fixtures.getSecurityScans(),
  },
  {
    pattern: /^\/security\/posture/,
    handler: () => fixtures.getSecurityPosture(),
  },

  // ── Vulnerabilities ───────────────────────────────────────────────
  {
    pattern: /^\/vulnerabilities\/stats/,
    handler: () => fixtures.getVulnerabilityStats(),
  },
  {
    pattern: /^\/vulnerabilities\/([^/?]+)\/status$/,
    handler: () => ({ status: "updated" }),
  },
  {
    pattern: /^\/vulnerabilities\/([^/?]+)\/comments$/,
    handler: () => ({ id: "comment-new", status: "created" }),
  },
  {
    pattern: /^\/vulnerabilities\/([^/?]+)\/accept-risk$/,
    handler: () => ({ status: "accepted" }),
  },
  {
    pattern: /^\/vulnerabilities\/([^/?]+)$/,
    handler: (p) => fixtures.getVulnerabilityDetail(p[1]) ?? {},
  },
  {
    pattern: /^\/vulnerabilities\??.*$/,
    handler: () => fixtures.getVulnerabilities(),
  },

  // ── Analytics ─────────────────────────────────────────────────────
  {
    pattern: /^\/analytics\/summary/,
    handler: () => fixtures.getAnalyticsSummary(),
  },
  {
    pattern: /^\/analytics\/mttr/,
    handler: () => fixtures.getMttrTrend(),
  },
  {
    pattern: /^\/analytics\/resolution-rate/,
    handler: () => fixtures.getResolutionRate(),
  },
  {
    pattern: /^\/analytics\/agent-accuracy/,
    handler: () => fixtures.getAgentAccuracy(),
  },
  {
    pattern: /^\/analytics\/agent-performance/,
    handler: () => fixtures.getAgentPerformance(),
  },
  {
    pattern: /^\/analytics\/api-usage\/endpoints/,
    handler: () => fixtures.getApiUsageEndpoints(),
  },
  {
    pattern: /^\/analytics\/api-usage\/hourly/,
    handler: () => fixtures.getApiUsageHourly(),
  },
  {
    pattern: /^\/analytics\/api-usage\/by-org/,
    handler: () => fixtures.getApiUsageByOrg(),
  },
  {
    pattern: /^\/analytics\/api-usage/,
    handler: () => fixtures.getApiUsageSummary(),
  },

  // ── Cost ──────────────────────────────────────────────────────────
  {
    pattern: /^\/cost\/summary/,
    handler: () => fixtures.getCostSummary(),
  },

  // ── Learning ──────────────────────────────────────────────────────
  {
    pattern: /^\/learning\/cycles/,
    handler: () => fixtures.getLearningCycles(),
  },

  // ── Playbooks ─────────────────────────────────────────────────────
  {
    pattern: /^\/playbooks\/custom\/([^/?]+)\/dry-run$/,
    handler: () => ({ status: "success", output: "Dry run completed (demo)" }),
  },
  {
    pattern: /^\/playbooks\/custom\/([^/?]+)$/,
    handler: () => fixtures.getCustomPlaybooks()[0] ?? {},
  },
  {
    pattern: /^\/playbooks\/custom/,
    handler: () => fixtures.getCustomPlaybooks(),
  },
  {
    pattern: /^\/playbooks\/validate/,
    handler: () => ({ valid: true, errors: [] }),
  },
  {
    pattern: /^\/playbooks\/([^/?]+)\/trigger$/,
    handler: () => ({ status: "triggered", message: "Playbook triggered (demo)" }),
  },
  {
    pattern: /^\/playbooks\/([^/?]+)$/,
    handler: () => fixtures.getPlaybooks()[0] ?? {},
  },
  {
    pattern: /^\/playbooks/,
    handler: () => fixtures.getPlaybooks(),
  },

  // ── Audit Logs ────────────────────────────────────────────────────
  {
    pattern: /^\/audit-logs/,
    handler: () => fixtures.getAuditLogs(),
  },

  // ── Billing ───────────────────────────────────────────────────────
  {
    pattern: /^\/billing\/plans/,
    handler: () => fixtures.getBillingPlans(),
  },
  {
    pattern: /^\/billing\/subscription/,
    handler: () => fixtures.getBillingSubscription(),
  },
  {
    pattern: /^\/billing\/usage/,
    handler: () => fixtures.getBillingUsage(),
  },
  {
    pattern: /^\/billing\/checkout/,
    handler: () => ({ session_id: "demo", url: "#" }),
  },
  {
    pattern: /^\/billing\/cancel/,
    handler: () => ({ status: "cancelled" }),
  },

  // ── System Health ─────────────────────────────────────────────────
  {
    pattern: /^\/health\/detailed/,
    handler: () => fixtures.getHealthDetailed(),
  },

  // ── Compliance ────────────────────────────────────────────────────
  {
    pattern: /^\/compliance\/trends/,
    handler: () => fixtures.getComplianceTrends(),
  },
  {
    pattern: /^\/compliance\/evidence/,
    handler: () => ({ evidence: [], total: 0 }),
  },
  {
    pattern: /^\/compliance\/report/,
    handler: () => fixtures.getComplianceReport(),
  },

  // ── Search ────────────────────────────────────────────────────────
  {
    pattern: /^\/search\?q=([^&]*)/,
    handler: (p) => fixtures.getSearchResults(decodeURIComponent(p[1] ?? "")),
  },
  {
    pattern: /^\/search/,
    handler: () => fixtures.getSearchResults(""),
  },

  // ── Marketplace ───────────────────────────────────────────────────
  {
    pattern: /^\/marketplace\/categories/,
    handler: () => fixtures.getMarketplaceCategories(),
  },
  {
    pattern: /^\/marketplace\/deploy/,
    handler: () => ({ status: "deployed" }),
  },
  {
    pattern: /^\/marketplace\/templates/,
    handler: () => fixtures.getMarketplaceTemplates(),
  },

  // ── Onboarding ────────────────────────────────────────────────────
  {
    pattern: /^\/onboarding/,
    handler: () => fixtures.getOnboardingStatus(),
  },

  // ── Users ─────────────────────────────────────────────────────────
  {
    pattern: /^\/users\/me\/notification-preferences/,
    handler: () => fixtures.getNotificationPreferences(),
  },
  {
    pattern: /^\/users\/([^/?]+)\/role$/,
    handler: () => ({ status: "updated" }),
  },
  {
    pattern: /^\/users\/([^/?]+)\/active$/,
    handler: () => ({ status: "updated" }),
  },
  {
    pattern: /^\/users/,
    handler: () => fixtures.getUsers(),
  },
  {
    pattern: /^\/auth\/register/,
    handler: () => ({ id: "new-user", status: "created" }),
  },

  // ── Settings (notification) ───────────────────────────────────────
  {
    pattern: /^\/notification-configs/,
    handler: () => fixtures.getNotificationConfigs(),
  },
  {
    pattern: /^\/notification-events/,
    handler: () => fixtures.getNotificationEvents(),
  },

  // ── Incidents ─────────────────────────────────────────────────────
  {
    pattern: /^\/incidents\/merge/,
    handler: () => ({ status: "merged" }),
  },
  {
    pattern: /^\/incidents\/([^/?]+)\/status$/,
    handler: () => ({ status: "updated" }),
  },
  {
    pattern: /^\/incidents/,
    handler: () => fixtures.getIncidents(),
  },

  // ── Predictions / Capacity ────────────────────────────────────────
  {
    pattern: /^\/predictions/,
    handler: () => fixtures.getPredictions(),
  },
  {
    pattern: /^\/capacity/,
    handler: () => fixtures.getCapacityRisks(),
  },

  // ── Agent Tasks ─────────────────────────────────────────────────
  {
    pattern: /^\/agent-tasks\/([^/?]+)\/steps\/([^/?]+)\/approve$/,
    handler: () => ({ approved: true, step_status: "running", task_status: "running" }),
  },
  {
    pattern: /^\/agent-tasks\/([^/?]+)\/cancel$/,
    handler: () => ({ task_id: "demo", status: "cancelled", cancelled: true }),
  },
  {
    pattern: /^\/agent-tasks\/([^/?]+)$/,
    handler: (p) => {
      const run = DEMO_PIPELINE_RUNS.find((r) => r.id === p[1]);
      return run ?? { task_id: p[1], status: "not_found" };
    },
  },
  {
    pattern: /^\/agent-tasks/,
    handler: (_p, body) => {
      if (body && typeof body === "object" && "prompt" in body) {
        return { task_id: `task-${Date.now()}`, status: "pending" };
      }
      return DEMO_PIPELINE_RUNS.map((r) => ({
        task_id: r.id,
        workflow_name: r.alert_name,
        status: r.status,
        created_at: r.started_at,
        step_count: r.timeline.length,
      }));
    },
  },

  // ── War Rooms ──────────────────────────────────────────────────
  {
    pattern: /^\/war-rooms\/([^/?]+)\/timeline$/,
    handler: () => ({ entry: { id: "demo", event_type: "human_note", content: "Added (demo)" } }),
  },
  {
    pattern: /^\/war-rooms\/([^/?]+)\/responders$/,
    handler: () => ({ responder: { user_id: "demo", name: "Demo User", role: "observer" } }),
  },
  {
    pattern: /^\/war-rooms\/([^/?]+)\/resolve$/,
    handler: () => ({ war_room: { status: "resolved" } }),
  },
  {
    pattern: /^\/war-rooms\/([^/?]+)$/,
    handler: () => ({ war_room: { id: "wr-demo-1", title: "Demo War Room", status: "active", timeline: [], responders: [] } }),
  },
  {
    pattern: /^\/war-rooms/,
    handler: (_p, body) => {
      if (body && typeof body === "object" && "title" in body) {
        return { war_room: { id: `wr-${Date.now()}`, status: "active", ...(body as Record<string, unknown>) } };
      }
      return { war_rooms: [], total: 0 };
    },
  },

  // ── Workflows ──────────────────────────────────────────────────
  {
    pattern: /^\/workflows/,
    handler: () => DEMO_WORKFLOW_RUNS,
  },

  // ── API Keys ───────────────────────────────────────────────────
  {
    pattern: /^\/api-keys\/([^/?]+)\/revoke$/,
    handler: () => ({ status: "revoked" }),
  },
  {
    pattern: /^\/api-keys/,
    handler: (_p, body) => {
      if (body && typeof body === "object" && "name" in body) {
        return { key_id: `key_${Date.now()}`, raw_key: `sk_demo_${Date.now()}`, status: "active" };
      }
      return DEMO_API_KEYS;
    },
  },

  // ── Scheduled Tasks ───────────────────────────────────────────────
  {
    pattern: /^\/scheduled-tasks\/([^/?]+)\/trigger$/,
    handler: () => ({ status: "triggered", task_id: "demo" }),
  },
  {
    pattern: /^\/scheduled-tasks\/([^/?]+)$/,
    handler: () => ({ id: "sched-demo", name: "Demo Schedule", enabled: true }),
  },
  {
    pattern: /^\/scheduled-tasks/,
    handler: (_p, body) => {
      if (body && typeof body === "object" && "name" in body) {
        return { id: `sched_${Date.now()}`, status: "created" };
      }
      return { items: [], total: 0 };
    },
  },

  // ── Chat ──────────────────────────────────────────────────────────
  {
    pattern: /^\/security\/chat/,
    handler: () => ({
      id: "msg-demo",
      role: "assistant",
      content: "I'm the ShieldOps security assistant. In demo mode, I can show you how I'd analyze threats and recommend actions. Try asking about your security posture!",
      timestamp: new Date().toISOString(),
    }),
  },
];

/**
 * Resolve an API path to demo fixture data.
 * Returns the fixture data or a safe fallback for unhandled routes.
 */
export function resolveRoute(path: string, body?: unknown): unknown {
  for (const route of routes) {
    const match = path.match(route.pattern);
    if (match) {
      const params: Record<string, string> = {};
      match.forEach((val, idx) => {
        if (idx > 0 && val) params[idx] = val;
      });
      return route.handler(params, body);
    }
  }
  // Safe fallback for unhandled routes
  return { items: [], total: 0 };
}
