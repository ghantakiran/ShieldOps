/**
 * Demo mock data for the Workflows page.
 *
 * Each workflow run represents a multi-step orchestration of agents
 * (investigation, security, remediation, learning). Timestamps are
 * computed relative to "now" so the data always looks fresh.
 */

// ── Types (mirrors Workflows.tsx interfaces) ─────────────────────────

export type WorkflowType = "incident_response" | "security_scan" | "proactive_check";
export type WorkflowStatus = "pending" | "running" | "paused" | "completed" | "failed" | "cancelled";
export type StepStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export interface WorkflowStep {
  id: string;
  agent_type: string;
  action: string;
  status: StepStatus;
  started_at: string | null;
  completed_at: string | null;
  result: string | null;
  error: string | null;
}

export interface WorkflowRun {
  id: string;
  workflow_type: WorkflowType;
  trigger_type: string;
  status: WorkflowStatus;
  started_at: string;
  completed_at: string | null;
  steps: WorkflowStep[];
}

// ── Helper ───────────────────────────────────────────────────────────

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60 * 1000).toISOString();
}

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

// ── Demo Workflow Runs ───────────────────────────────────────────────

export const DEMO_WORKFLOW_RUNS: WorkflowRun[] = [
  // 1. Running incident_response — alert-triggered, 3/5 steps complete
  {
    id: "wfr-demo-001",
    workflow_type: "incident_response",
    trigger_type: "alert",
    status: "running",
    started_at: minutesAgo(8),
    completed_at: null,
    steps: [
      {
        id: "s1",
        agent_type: "investigation",
        action: "analyze_alert",
        status: "completed",
        started_at: minutesAgo(8),
        completed_at: minutesAgo(6),
        result: "Root cause: connection pool exhaustion in order-service due to slow downstream DB queries",
        error: null,
      },
      {
        id: "s2",
        agent_type: "security",
        action: "check_policy",
        status: "completed",
        started_at: minutesAgo(6),
        completed_at: minutesAgo(5.5),
        result: "Policy check passed — auto-remediation allowed for connection pool scaling",
        error: null,
      },
      {
        id: "s3",
        agent_type: "remediation",
        action: "scale_connection_pool",
        status: "completed",
        started_at: minutesAgo(5.5),
        completed_at: minutesAgo(4),
        result: "Increased max pool size from 20 to 50 connections on order-service",
        error: null,
      },
      {
        id: "s4",
        agent_type: "investigation",
        action: "verify_fix",
        status: "running",
        started_at: minutesAgo(4),
        completed_at: null,
        result: null,
        error: null,
      },
      {
        id: "s5",
        agent_type: "learning",
        action: "update_playbook",
        status: "pending",
        started_at: null,
        completed_at: null,
        result: null,
        error: null,
      },
    ],
  },

  // 2. Completed security_scan — all 4 steps done
  {
    id: "wfr-demo-002",
    workflow_type: "security_scan",
    trigger_type: "scheduled",
    status: "completed",
    started_at: hoursAgo(2),
    completed_at: hoursAgo(1.5),
    steps: [
      {
        id: "s1",
        agent_type: "security",
        action: "scan_vulnerabilities",
        status: "completed",
        started_at: hoursAgo(2),
        completed_at: hoursAgo(1.85),
        result: "Scanned 47 images across 12 namespaces; found 5 CVEs (2 critical, 3 high)",
        error: null,
      },
      {
        id: "s2",
        agent_type: "security",
        action: "prioritize_findings",
        status: "completed",
        started_at: hoursAgo(1.85),
        completed_at: hoursAgo(1.75),
        result: "CVE-2025-31482 and CVE-2025-29103 prioritized for immediate patching",
        error: null,
      },
      {
        id: "s3",
        agent_type: "remediation",
        action: "apply_patches",
        status: "completed",
        started_at: hoursAgo(1.75),
        completed_at: hoursAgo(1.55),
        result: "Patched base images for auth-service and payment-api; rebuilt and deployed",
        error: null,
      },
      {
        id: "s4",
        agent_type: "security",
        action: "rescan_verify",
        status: "completed",
        started_at: hoursAgo(1.55),
        completed_at: hoursAgo(1.5),
        result: "Rescan clean — 0 critical, 0 high CVEs remaining",
        error: null,
      },
    ],
  },

  // 3. Completed proactive_check — all 3 steps done
  {
    id: "wfr-demo-003",
    workflow_type: "proactive_check",
    trigger_type: "scheduled",
    status: "completed",
    started_at: hoursAgo(4),
    completed_at: hoursAgo(3.7),
    steps: [
      {
        id: "s1",
        agent_type: "investigation",
        action: "collect_metrics",
        status: "completed",
        started_at: hoursAgo(4),
        completed_at: hoursAgo(3.9),
        result: "Collected metrics from 18 services across 3 clusters",
        error: null,
      },
      {
        id: "s2",
        agent_type: "investigation",
        action: "detect_anomalies",
        status: "completed",
        started_at: hoursAgo(3.9),
        completed_at: hoursAgo(3.8),
        result: "Minor CPU anomaly on cache-proxy (trending up 12% week-over-week); no action needed",
        error: null,
      },
      {
        id: "s3",
        agent_type: "learning",
        action: "update_baselines",
        status: "completed",
        started_at: hoursAgo(3.8),
        completed_at: hoursAgo(3.7),
        result: "Updated metric baselines for 18 services; adjusted cache-proxy CPU threshold to 78%",
        error: null,
      },
    ],
  },

  // 4. Failed incident_response — remediation step failed
  {
    id: "wfr-demo-004",
    workflow_type: "incident_response",
    trigger_type: "alert",
    status: "failed",
    started_at: hoursAgo(6),
    completed_at: hoursAgo(5.5),
    steps: [
      {
        id: "s1",
        agent_type: "investigation",
        action: "analyze_alert",
        status: "completed",
        started_at: hoursAgo(6),
        completed_at: hoursAgo(5.8),
        result: "Persistent volume claim stuck in Pending state for data-pipeline StatefulSet",
        error: null,
      },
      {
        id: "s2",
        agent_type: "security",
        action: "check_policy",
        status: "completed",
        started_at: hoursAgo(5.8),
        completed_at: hoursAgo(5.75),
        result: "Policy check passed — storage provisioning allowed",
        error: null,
      },
      {
        id: "s3",
        agent_type: "remediation",
        action: "provision_volume",
        status: "failed",
        started_at: hoursAgo(5.75),
        completed_at: hoursAgo(5.5),
        result: null,
        error:
          "Storage provisioner returned InsufficientCapacity: no available gp3 volumes in us-east-1c. Manual intervention required to expand storage pool or switch AZ.",
      },
      {
        id: "s4",
        agent_type: "learning",
        action: "update_playbook",
        status: "skipped",
        started_at: null,
        completed_at: null,
        result: null,
        error: null,
      },
    ],
  },

  // 5. Running security_scan — 2/4 steps complete
  {
    id: "wfr-demo-005",
    workflow_type: "security_scan",
    trigger_type: "manual",
    status: "running",
    started_at: minutesAgo(15),
    completed_at: null,
    steps: [
      {
        id: "s1",
        agent_type: "security",
        action: "scan_vulnerabilities",
        status: "completed",
        started_at: minutesAgo(15),
        completed_at: minutesAgo(10),
        result: "Found 8 findings across staging namespace (0 critical, 4 high, 4 medium)",
        error: null,
      },
      {
        id: "s2",
        agent_type: "security",
        action: "prioritize_findings",
        status: "completed",
        started_at: minutesAgo(10),
        completed_at: minutesAgo(8),
        result: "4 high-severity findings in ml-inference and data-processor images prioritized",
        error: null,
      },
      {
        id: "s3",
        agent_type: "remediation",
        action: "apply_patches",
        status: "running",
        started_at: minutesAgo(8),
        completed_at: null,
        result: null,
        error: null,
      },
      {
        id: "s4",
        agent_type: "security",
        action: "rescan_verify",
        status: "pending",
        started_at: null,
        completed_at: null,
        result: null,
        error: null,
      },
    ],
  },

  // 6. Cancelled proactive_check
  {
    id: "wfr-demo-006",
    workflow_type: "proactive_check",
    trigger_type: "scheduled",
    status: "cancelled",
    started_at: hoursAgo(8),
    completed_at: hoursAgo(7.5),
    steps: [
      {
        id: "s1",
        agent_type: "investigation",
        action: "collect_metrics",
        status: "completed",
        started_at: hoursAgo(8),
        completed_at: hoursAgo(7.8),
        result: "Metrics collected from 18 services",
        error: null,
      },
      {
        id: "s2",
        agent_type: "investigation",
        action: "detect_anomalies",
        status: "skipped",
        started_at: null,
        completed_at: null,
        result: null,
        error: null,
      },
      {
        id: "s3",
        agent_type: "learning",
        action: "update_baselines",
        status: "skipped",
        started_at: null,
        completed_at: null,
        result: null,
        error: null,
      },
    ],
  },
];
