import type { AnalyticsSummary } from "../../api/types";
import { pastDate } from "../config";

export function getAnalyticsSummary(): AnalyticsSummary {
  return {
    total_investigations: 247,
    total_remediations: 189,
    auto_resolved_percent: 72.4,
    mean_time_to_resolve_seconds: 420,
    investigations_by_status: {
      completed: 198,
      in_progress: 12,
      pending: 8,
      failed: 29,
    },
    remediations_by_status: {
      completed: 142,
      pending_approval: 11,
      executing: 5,
      approved: 3,
      failed: 18,
      rolled_back: 10,
    },
  };
}

export function getMttrTrend() {
  const points = [];
  for (let i = 29; i >= 0; i--) {
    const baseMinutes = 30 - (i < 10 ? 0 : (30 - i) * 0.8);
    const jitter = (Math.sin(i * 1.3) * 3);
    points.push({
      date: pastDate(i),
      avg_duration_ms: Math.max(5, Math.round((baseMinutes + jitter) * 60_000)),
      count: Math.round(5 + Math.random() * 10),
    });
  }
  return {
    period: "30d",
    data_points: points,
    current_mttr_minutes: 7.0,
  };
}

export function getResolutionRate() {
  return {
    period: "30d",
    automated_rate: 0.724,
    manual_rate: 0.276,
    total_incidents: 247,
  };
}

export function getAgentAccuracy() {
  return {
    period: "30d",
    accuracy: 0.89,
    total_investigations: 247,
  };
}

export function getApiUsageSummary() {
  return {
    period_hours: 24,
    total_calls: 14_832,
    unique_endpoints: 47,
    org_id: null,
  };
}

export function getApiUsageEndpoints() {
  return [
    { endpoint: "GET /agents/", count: 3420, avg_latency_ms: 12.3 },
    { endpoint: "GET /investigations/", count: 2810, avg_latency_ms: 28.7 },
    { endpoint: "GET /analytics/summary", count: 1950, avg_latency_ms: 45.2 },
    { endpoint: "GET /security/posture", count: 1230, avg_latency_ms: 67.8 },
    { endpoint: "GET /remediations/", count: 1100, avg_latency_ms: 19.4 },
    { endpoint: "POST /investigations/", count: 890, avg_latency_ms: 152.3 },
    { endpoint: "GET /vulnerabilities", count: 780, avg_latency_ms: 34.1 },
    { endpoint: "GET /cost/summary", count: 650, avg_latency_ms: 89.6 },
    { endpoint: "GET /playbooks", count: 520, avg_latency_ms: 15.8 },
    { endpoint: "GET /audit-logs", count: 482, avg_latency_ms: 42.1 },
  ];
}

export function getApiUsageHourly() {
  const hours = [];
  for (let i = 23; i >= 0; i--) {
    const d = new Date(Date.now() - i * 3_600_000);
    const hour = d.getHours();
    const isBusinessHours = hour >= 9 && hour <= 18;
    hours.push({
      hour: d.toISOString(),
      count: isBusinessHours
        ? Math.round(400 + Math.random() * 300)
        : Math.round(100 + Math.random() * 150),
    });
  }
  return hours;
}

export function getApiUsageByOrg() {
  return [
    { org_id: "acme-corp", total_calls: 8420 },
    { org_id: "globex-inc", total_calls: 4210 },
    { org_id: "initech", total_calls: 2202 },
  ];
}
