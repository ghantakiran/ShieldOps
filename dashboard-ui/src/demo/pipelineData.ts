/**
 * Demo mock data for the PipelineRuns page.
 *
 * Each pipeline run represents an end-to-end investigation-to-remediation
 * cycle triggered by an alert. Timestamps use Date math relative to "now"
 * so values always look fresh.
 */

import { recentTimestamp } from "./config";

// ── Types (mirrors PipelineRuns.tsx interfaces) ──────────────────────

export interface TimelineEntry {
  timestamp: string;
  event: string;
  details?: string;
}

export interface Recommendation {
  id: string;
  action: string;
  target: string;
  risk_level: string;
  description: string;
}

export interface PipelineRun {
  id: string;
  alert_name: string;
  namespace: string;
  service: string;
  status: string;
  started_at: string;
  duration_seconds: number | null;
  timeline: TimelineEntry[];
  recommendations: Recommendation[];
}

// ── Helper ───────────────────────────────────────────────────────────

/** Returns an ISO timestamp offset from now by the given number of seconds. */
function ts(secondsAgo: number): string {
  return recentTimestamp(secondsAgo);
}

// ── Demo Pipeline Runs ───────────────────────────────────────────────

export const DEMO_PIPELINE_RUNS: PipelineRun[] = [
  // 1. Completed — KubePodCrashLooping: deployment regression, auto-approved rollback
  {
    id: "run-demo-001",
    alert_name: "KubePodCrashLooping",
    namespace: "production",
    service: "api-gateway",
    status: "completed",
    started_at: ts(2400),
    duration_seconds: 378,
    timeline: [
      {
        timestamp: ts(2400),
        event: "Pipeline started",
        details: "Triggered by alert KubePodCrashLooping on production/api-gateway",
      },
      {
        timestamp: ts(2385),
        event: "Investigation started",
        details: "Collecting pod logs, events, and recent deployment history",
      },
      {
        timestamp: ts(2220),
        event: "Root cause identified",
        details:
          "Deployment regression in api-gateway v3.8.1 — nil pointer in request middleware introduced by commit abc1234",
      },
      {
        timestamp: ts(2190),
        event: "Recommendations generated",
        details: "Rollback to v3.8.0 recommended with confidence 0.94",
      },
      {
        timestamp: ts(2180),
        event: "Auto-approved (confidence >= 0.80, production blast-radius low)",
      },
      {
        timestamp: ts(2100),
        event: "Remediation executed",
        details: "Rolled back Deployment api-gateway from v3.8.1 to v3.8.0",
      },
      {
        timestamp: ts(2022),
        event: "Verification passed",
        details: "All pods healthy, 0 crash loops for 60s, p99 latency back to 42ms",
      },
    ],
    recommendations: [
      {
        id: "rec-001a",
        action: "rollback",
        target: "deploy/api-gateway",
        risk_level: "low",
        description: "Rollback Deployment to v3.8.0 (last known stable release)",
      },
      {
        id: "rec-001b",
        action: "notify",
        target: "#platform-eng",
        risk_level: "low",
        description: "Notify platform-eng channel about the regression in v3.8.1",
      },
    ],
  },

  // 2. Completed — HighMemoryUsage: memory leak, increased limits
  {
    id: "run-demo-002",
    alert_name: "HighMemoryUsage",
    namespace: "production",
    service: "redis-cache",
    status: "completed",
    started_at: ts(5400),
    duration_seconds: 245,
    timeline: [
      {
        timestamp: ts(5400),
        event: "Pipeline started",
        details: "Triggered by alert HighMemoryUsage — redis-cache at 93% memory utilization",
      },
      {
        timestamp: ts(5385),
        event: "Investigation started",
        details: "Analyzing memory usage patterns and key distribution",
      },
      {
        timestamp: ts(5250),
        event: "Root cause identified",
        details:
          "Memory leak from session keys with no TTL set by checkout-service v2.4.0; 12M orphaned keys consuming 1.8 GiB",
      },
      {
        timestamp: ts(5220),
        event: "Recommendations generated",
      },
      {
        timestamp: ts(5210),
        event: "Auto-approved (staging-safe & low risk)",
      },
      {
        timestamp: ts(5180),
        event: "Remediation executed",
        details: "Increased redis-cache memory limit from 4Gi to 6Gi; scheduled key cleanup job",
      },
      {
        timestamp: ts(5155),
        event: "Verification passed",
        details: "Memory utilization dropped to 62%, no evictions",
      },
    ],
    recommendations: [
      {
        id: "rec-002a",
        action: "scale_resources",
        target: "statefulset/redis-cache",
        risk_level: "low",
        description: "Increase memory limit from 4Gi to 6Gi to provide headroom",
      },
      {
        id: "rec-002b",
        action: "run_job",
        target: "cronjob/redis-key-cleanup",
        risk_level: "low",
        description: "Run one-time cleanup of orphaned session keys without TTL",
      },
    ],
  },

  // 3. Awaiting approval — HighErrorRate: DNS issue, confidence below auto-approve
  {
    id: "run-demo-003",
    alert_name: "HighErrorRate",
    namespace: "staging",
    service: "checkout-service",
    status: "awaiting_approval",
    started_at: ts(420),
    duration_seconds: null,
    timeline: [
      {
        timestamp: ts(420),
        event: "Pipeline started",
        details: "Triggered by alert HighErrorRate — checkout-service 5xx rate at 34%",
      },
      {
        timestamp: ts(405),
        event: "Investigation started",
        details: "Analyzing error logs and upstream dependency health",
      },
      {
        timestamp: ts(300),
        event: "Root cause identified",
        details:
          "DNS resolution failures for payment-gateway.internal — CoreDNS pod on node-07 is OOMKilled",
      },
      {
        timestamp: ts(285),
        event: "Recommendations generated",
        details: "Restart CoreDNS pod recommended; confidence 0.65 (below auto-approve threshold 0.80)",
      },
      {
        timestamp: ts(284),
        event: "Awaiting human approval",
        details:
          "Confidence 0.65 is below the auto-approve threshold. Manual review required before restarting CoreDNS.",
      },
    ],
    recommendations: [
      {
        id: "rec-003a",
        action: "restart",
        target: "pod/coredns-7f89b4c6-xkq2p",
        risk_level: "medium",
        description: "Restart the OOMKilled CoreDNS pod on node-07 to restore DNS resolution",
      },
      {
        id: "rec-003b",
        action: "scale_resources",
        target: "deploy/coredns",
        risk_level: "medium",
        description: "Increase CoreDNS memory limit from 128Mi to 256Mi to prevent recurrence",
      },
    ],
  },

  // 4. Investigating — CertificateExpiringSoon
  {
    id: "run-demo-004",
    alert_name: "CertificateExpiringSoon",
    namespace: "production",
    service: "payment-api",
    status: "investigating",
    started_at: ts(180),
    duration_seconds: null,
    timeline: [
      {
        timestamp: ts(180),
        event: "Pipeline started",
        details:
          "Triggered by alert CertificateExpiringSoon — TLS certificate for payment-api.shieldops.io expires in 7 days",
      },
      {
        timestamp: ts(165),
        event: "Investigation started",
        details:
          "Checking cert-manager CertificateRequest status, ACME challenge logs, and DNS records",
      },
    ],
    recommendations: [],
  },

  // 5. Failed — NodeNotReady: investigation timed out
  {
    id: "run-demo-005",
    alert_name: "NodeNotReady",
    namespace: "production",
    service: "worker-pool",
    status: "failed",
    started_at: ts(7200),
    duration_seconds: 600,
    timeline: [
      {
        timestamp: ts(7200),
        event: "Pipeline started",
        details: "Triggered by alert NodeNotReady — node worker-pool-node-03 is NotReady",
      },
      {
        timestamp: ts(7185),
        event: "Investigation started",
        details: "Querying kubelet status, node conditions, and cloud provider instance health",
      },
      {
        timestamp: ts(6900),
        event: "Partial findings",
        details: "Node unreachable via SSH; cloud provider API returning 503 for instance metadata",
      },
      {
        timestamp: ts(6600),
        event: "Pipeline failed",
        details:
          "Investigation timed out after 600s — unable to reach node or cloud provider API. Manual intervention required.",
      },
    ],
    recommendations: [
      {
        id: "rec-005a",
        action: "cordon_drain",
        target: "node/worker-pool-node-03",
        risk_level: "high",
        description:
          "Cordon and drain the unreachable node to reschedule workloads on healthy nodes",
      },
    ],
  },

  // 6. Completed — DiskPressure: cleaned evicted pods
  {
    id: "run-demo-006",
    alert_name: "DiskPressure",
    namespace: "production",
    service: "logging-stack",
    status: "completed",
    started_at: ts(10800),
    duration_seconds: 192,
    timeline: [
      {
        timestamp: ts(10800),
        event: "Pipeline started",
        details: "Triggered by alert DiskPressure — node logging-node-01 at 91% disk usage",
      },
      {
        timestamp: ts(10785),
        event: "Investigation started",
        details: "Analyzing disk usage breakdown by path and container logs",
      },
      {
        timestamp: ts(10700),
        event: "Root cause identified",
        details:
          "148 evicted pods left behind 12Gi of orphaned container logs in /var/log/pods/",
      },
      {
        timestamp: ts(10680),
        event: "Recommendations generated",
      },
      {
        timestamp: ts(10670),
        event: "Auto-approved (low risk, non-destructive cleanup)",
      },
      {
        timestamp: ts(10630),
        event: "Remediation executed",
        details: "Cleaned up orphaned logs from 148 evicted pods, reclaimed 12Gi disk space",
      },
      {
        timestamp: ts(10608),
        event: "Verification passed",
        details: "Disk usage dropped to 67%, DiskPressure condition cleared",
      },
    ],
    recommendations: [
      {
        id: "rec-006a",
        action: "cleanup",
        target: "node/logging-node-01:/var/log/pods",
        risk_level: "low",
        description: "Remove orphaned container logs from evicted pods",
      },
      {
        id: "rec-006b",
        action: "configure",
        target: "kubelet/logging-node-01",
        risk_level: "low",
        description: "Enable containerLogMaxSize=50Mi to prevent recurrence",
      },
    ],
  },

  // 7. Remediating — OOMKilled: scaling up resources
  {
    id: "run-demo-007",
    alert_name: "OOMKilled",
    namespace: "staging",
    service: "ml-inference",
    status: "remediating",
    started_at: ts(360),
    duration_seconds: null,
    timeline: [
      {
        timestamp: ts(360),
        event: "Pipeline started",
        details: "Triggered by alert OOMKilled — ml-inference pod killed 3 times in 10 minutes",
      },
      {
        timestamp: ts(345),
        event: "Investigation started",
        details: "Analyzing container memory usage, model sizes, and request patterns",
      },
      {
        timestamp: ts(240),
        event: "Root cause identified",
        details:
          "New model v2.1 requires 3.2Gi peak memory but container limit is set to 2Gi",
      },
      {
        timestamp: ts(225),
        event: "Recommendations generated",
        details: "Scale memory limit to 4Gi with confidence 0.91",
      },
      {
        timestamp: ts(215),
        event: "Auto-approved (staging environment, confidence 0.91)",
      },
      {
        timestamp: ts(200),
        event: "Remediation in progress",
        details: "Patching Deployment ml-inference memory limit from 2Gi to 4Gi; rolling restart in progress",
      },
    ],
    recommendations: [
      {
        id: "rec-007a",
        action: "scale_resources",
        target: "deploy/ml-inference",
        risk_level: "low",
        description: "Increase container memory limit from 2Gi to 4Gi to accommodate model v2.1",
      },
      {
        id: "rec-007b",
        action: "notify",
        target: "#ml-team",
        risk_level: "low",
        description: "Notify ML team about increased resource requirements for model v2.1",
      },
    ],
  },

  // 8. Pending — LatencySpike: queued, waiting for capacity
  {
    id: "run-demo-008",
    alert_name: "LatencySpike",
    namespace: "production",
    service: "search-service",
    status: "pending",
    started_at: ts(45),
    duration_seconds: null,
    timeline: [
      {
        timestamp: ts(45),
        event: "Pipeline queued",
        details:
          "Waiting for available agent capacity — 2 investigations already in progress",
      },
    ],
    recommendations: [],
  },
];
