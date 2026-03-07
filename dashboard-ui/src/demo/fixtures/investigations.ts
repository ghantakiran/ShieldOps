import type { Investigation, InvestigationDetail } from "../../api/types";
import { recentTimestamp, pastDate } from "../config";

export function getInvestigations(): Investigation[] {
  return [
    {
      id: "inv-001",
      alert_id: "alert-k8s-001",
      alert_name: "KubePodCrashLooping",
      severity: "critical",
      resource_id: "payment-service-7b4d9f-xk2nq",
      status: "completed",
      root_cause: "OOM kill due to memory leak in payment-service v2.3.1 — connection pool not releasing Redis connections",
      confidence: 0.91,
      started_at: recentTimestamp(3600),
      completed_at: recentTimestamp(2400),
      duration_seconds: 1200,
    },
    {
      id: "inv-002",
      alert_id: "alert-prom-002",
      alert_name: "HighErrorRate5xx",
      severity: "high",
      resource_id: "api-gateway-prod",
      status: "in_progress",
      root_cause: null,
      confidence: 0.45,
      started_at: recentTimestamp(900),
      completed_at: null,
      duration_seconds: null,
    },
    {
      id: "inv-003",
      alert_id: "alert-dd-003",
      alert_name: "DiskUsageAbove90Percent",
      severity: "warning",
      resource_id: "postgres-primary-01",
      status: "completed",
      root_cause: "WAL archive backlog — archive_command failing due to expired S3 credentials",
      confidence: 0.88,
      started_at: pastDate(1),
      completed_at: recentTimestamp(72000),
      duration_seconds: 480,
    },
    {
      id: "inv-004",
      alert_id: "alert-cw-004",
      alert_name: "ECSServiceUnhealthy",
      severity: "high",
      resource_id: "user-auth-service",
      status: "completed",
      root_cause: "Health check endpoint returning 503 — downstream OIDC provider rate-limiting",
      confidence: 0.82,
      started_at: pastDate(2),
      completed_at: pastDate(2),
      duration_seconds: 900,
    },
    {
      id: "inv-005",
      alert_id: "alert-splunk-005",
      alert_name: "SuspiciousLoginPattern",
      severity: "critical",
      resource_id: "iam-prod-us-east-1",
      status: "completed",
      root_cause: "Credential stuffing attack from 3 IP ranges — 2,400 failed attempts in 10 minutes",
      confidence: 0.95,
      started_at: pastDate(3),
      completed_at: pastDate(3),
      duration_seconds: 360,
    },
    {
      id: "inv-006",
      alert_id: "alert-prom-006",
      alert_name: "LatencyP99Above500ms",
      severity: "warning",
      resource_id: "search-service-prod",
      status: "completed",
      root_cause: "Elasticsearch index not optimized — force merge reduced p99 from 520ms to 45ms",
      confidence: 0.76,
      started_at: pastDate(4),
      completed_at: pastDate(4),
      duration_seconds: 1800,
    },
    {
      id: "inv-007",
      alert_id: "alert-gcp-007",
      alert_name: "CloudSQLHighCPU",
      severity: "high",
      resource_id: "analytics-db-prod",
      status: "pending",
      root_cause: null,
      confidence: null,
      started_at: recentTimestamp(120),
      completed_at: null,
      duration_seconds: null,
    },
    {
      id: "inv-008",
      alert_id: "alert-k8s-008",
      alert_name: "NodeNotReady",
      severity: "critical",
      resource_id: "gke-prod-pool-1-node-03",
      status: "failed",
      root_cause: null,
      confidence: null,
      started_at: pastDate(1),
      completed_at: pastDate(1),
      duration_seconds: 300,
    },
  ];
}

export function getInvestigationDetail(id: string): InvestigationDetail | null {
  const investigations = getInvestigations();
  const base = investigations.find((i) => i.id === id);
  if (!base) return null;

  if (id === "inv-001") {
    return {
      ...base,
      findings: [
        { type: "log_pattern", source: "payment-service", message: "java.lang.OutOfMemoryError: Java heap space", count: 47, timespan: "last 2 hours" },
        { type: "metric_anomaly", source: "prometheus", metric: "container_memory_usage_bytes", value: "2.1Gi", threshold: "1.5Gi" },
        { type: "correlation", source: "redis-exporter", message: "Active connections: 847 (normal: ~120)", related_to: "connection pool leak" },
      ],
      recommended_actions: [
        "Rollback payment-service to v2.3.0 (last known good)",
        "Apply Redis connection pool fix from PR #1247",
        "Increase memory limit to 2Gi as interim measure",
        "Add connection pool monitoring alert",
      ],
      timeline: [
        { timestamp: recentTimestamp(3600), event_type: "alert_received", description: "PagerDuty alert: KubePodCrashLooping on payment-service-7b4d9f-xk2nq" },
        { timestamp: recentTimestamp(3540), event_type: "investigation_started", description: "Investigation agent assigned — analyzing pod logs, metrics, and events" },
        { timestamp: recentTimestamp(3300), event_type: "log_analysis", description: "Found 47 OOMKilled events in last 2 hours — memory leak pattern detected" },
        { timestamp: recentTimestamp(3100), event_type: "metric_correlation", description: "Redis active connections anomaly: 847 vs baseline 120 — correlates with memory growth" },
        { timestamp: recentTimestamp(2900), event_type: "root_cause_identified", description: "Root cause: Connection pool not releasing Redis connections in v2.3.1 (introduced in commit abc123)" },
        { timestamp: recentTimestamp(2700), event_type: "recommendation", description: "Recommended: Rollback to v2.3.0, apply fix from PR #1247" },
        { timestamp: recentTimestamp(2400), event_type: "investigation_completed", description: "Investigation completed — 91% confidence in root cause" },
      ],
    };
  }

  return {
    ...base,
    findings: [
      { type: "log_pattern", source: base.resource_id, message: "Anomalous pattern detected", count: 12, timespan: "last 30 minutes" },
    ],
    recommended_actions: base.root_cause ? ["Review and apply recommended remediation"] : ["Investigation in progress — awaiting additional data"],
    timeline: [
      { timestamp: base.started_at, event_type: "alert_received", description: `Alert triggered: ${base.alert_name}` },
      { timestamp: recentTimestamp(600), event_type: "investigation_started", description: "Investigation agent analyzing telemetry data" },
    ],
  };
}
