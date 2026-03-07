/** Miscellaneous fixture data for pages that need specific API responses. */

import { pastDate, recentTimestamp } from "../config";

export function getHealthDetailed() {
  return {
    status: "healthy",
    version: "0.1.0",
    uptime_seconds: 864000,
    checks: {
      database: "healthy",
      redis: "healthy",
      kafka: "healthy",
      opa: "healthy",
      langsmith: "healthy",
    },
    agents_online: 6,
    memory_usage_mb: 512,
    cpu_percent: 23.4,
  };
}

export function getComplianceReport() {
  return {
    generated_at: recentTimestamp(3600),
    overall_score: 84,
    frameworks: [
      { name: "SOC2", score: 92, controls_passed: 46, controls_total: 50, controls_failed: 4 },
      { name: "HIPAA", score: 85, controls_passed: 34, controls_total: 40, controls_failed: 6 },
      { name: "PCI-DSS", score: 78, controls_passed: 31, controls_total: 40, controls_failed: 9 },
      { name: "GDPR", score: 88, controls_passed: 22, controls_total: 25, controls_failed: 3 },
      { name: "ISO27001", score: 81, controls_passed: 65, controls_total: 80, controls_failed: 15 },
    ],
    recent_findings: [
      { control: "AC-2", framework: "SOC2", status: "failed", description: "Service accounts without expiration dates" },
      { control: "SC-13", framework: "PCI-DSS", status: "failed", description: "TLS 1.0 still enabled on legacy endpoint" },
    ],
  };
}

export function getComplianceTrends() {
  const trends = [];
  for (let i = 29; i >= 0; i--) {
    trends.push({
      date: pastDate(i),
      score: Math.round(78 + (29 - i) * 0.2 + Math.sin(i) * 2),
    });
  }
  return trends;
}

export function getMarketplaceTemplates() {
  return [
    { id: "tpl-001", name: "AWS EKS Monitoring Pack", category: "observability", description: "Pre-configured dashboards and alerts for EKS clusters", provider: "ShieldOps", rating: 4.8, installs: 1240, status: "available" },
    { id: "tpl-002", name: "PCI-DSS Compliance Bundle", category: "compliance", description: "Automated PCI-DSS compliance checks and evidence collection", provider: "ShieldOps", rating: 4.6, installs: 890, status: "available" },
    { id: "tpl-003", name: "Incident Response Playbooks", category: "security", description: "Pre-built playbooks for common incident response scenarios", provider: "Community", rating: 4.4, installs: 2100, status: "installed" },
    { id: "tpl-004", name: "Cost Optimization Pack", category: "finops", description: "Right-sizing recommendations and waste detection rules", provider: "ShieldOps", rating: 4.7, installs: 1560, status: "available" },
    { id: "tpl-005", name: "GCP Security Posture", category: "security", description: "Security posture management for Google Cloud", provider: "Community", rating: 4.2, installs: 670, status: "available" },
    { id: "tpl-006", name: "SLO Management Kit", category: "sre", description: "SLO definitions, burn rate alerts, and error budget tracking", provider: "ShieldOps", rating: 4.9, installs: 980, status: "available" },
  ];
}

export function getMarketplaceCategories() {
  return [
    { key: "observability", name: "Observability", count: 12 },
    { key: "security", name: "Security", count: 18 },
    { key: "compliance", name: "Compliance", count: 8 },
    { key: "finops", name: "FinOps", count: 6 },
    { key: "sre", name: "SRE", count: 10 },
  ];
}

export function getOnboardingStatus() {
  return {
    completed_steps: ["welcome", "cloud_connect"],
    current_step: "deploy_agent",
    total_steps: 5,
    steps: [
      { name: "welcome", label: "Welcome", status: "completed" },
      { name: "cloud_connect", label: "Connect Cloud", status: "completed" },
      { name: "deploy_agent", label: "Deploy Agent", status: "in_progress" },
      { name: "configure_alerts", label: "Configure Alerts", status: "pending" },
      { name: "first_investigation", label: "First Investigation", status: "pending" },
    ],
  };
}

export function getUsers() {
  return [
    { id: "user-001", email: "admin@shieldops.io", name: "Sarah Chen", role: "admin", is_active: true },
    { id: "user-002", email: "ops@shieldops.io", name: "Mike Johnson", role: "operator", is_active: true },
    { id: "user-003", email: "viewer@shieldops.io", name: "Alex Kumar", role: "viewer", is_active: true },
    { id: "demo-user-001", email: "demo@shieldops.io", name: "Demo User", role: "admin", is_active: true },
  ];
}

export function getNotificationConfigs() {
  return [
    { id: "nc-001", channel: "slack", name: "#sre-alerts", enabled: true },
    { id: "nc-002", channel: "pagerduty", name: "Production On-Call", enabled: true },
    { id: "nc-003", channel: "email", name: "ops-team@shieldops.io", enabled: false },
  ];
}

export function getNotificationPreferences() {
  return {
    investigation_started: true,
    investigation_completed: true,
    remediation_pending: true,
    remediation_completed: true,
    security_scan_completed: true,
    critical_vulnerability: true,
    cost_anomaly: true,
  };
}

export function getNotificationEvents() {
  return [
    "investigation_started",
    "investigation_completed",
    "remediation_pending",
    "remediation_completed",
    "security_scan_completed",
    "critical_vulnerability",
    "cost_anomaly",
  ];
}

export function getPredictions() {
  return {
    predictions: [
      { id: "pred-001", service: "eks-prod-us-east-1", predicted_issue: "EKS cluster will exceed 80% CPU", severity: "high", confidence: 0.87, predicted_at: pastDate(1), predicted_time: "in 5 days", status: "active" },
      { id: "pred-002", service: "postgres-primary-01", predicted_issue: "High probability of disk pressure", severity: "high", confidence: 0.74, predicted_at: pastDate(2), predicted_time: "in 3 days", status: "active" },
      { id: "pred-003", service: "aws-account-prod", predicted_issue: "Monthly spend projected to exceed budget by 12%", severity: "medium", confidence: 0.82, predicted_at: pastDate(0), predicted_time: "end of month", status: "active" },
    ],
  };
}

export function getCapacityRisks() {
  return {
    risks: [
      { resource: "eks-prod-us-east-1", current_usage_pct: 72, projected_usage_pct: 88, days_until_breach: 5, confidence: 0.87 },
      { resource: "rds-primary", current_usage_pct: 78, projected_usage_pct: 94, days_until_breach: 14, confidence: 0.74 },
      { resource: "elasticache-prod", current_usage_pct: 65, projected_usage_pct: 82, days_until_breach: 21, confidence: 0.68 },
    ],
  };
}

export function getIncidents() {
  return {
    incidents: [
      {
        id: "inc-001",
        title: "Payment Service Outage",
        severity: "critical",
        status: "resolved",
        investigation_ids: ["inv-001"],
        correlation_score: 0.94,
        correlation_reasons: ["same service", "time proximity", "shared root cause"],
        service: "payment-service",
        environment: "production",
        first_seen: pastDate(1),
        last_seen: recentTimestamp(3600),
        merged_into: null,
        metadata: {},
      },
      {
        id: "inc-002",
        title: "API Gateway Degradation",
        severity: "high",
        status: "investigating",
        investigation_ids: ["inv-002", "inv-005"],
        correlation_score: 0.82,
        correlation_reasons: ["upstream dependency", "error rate spike"],
        service: "api-gateway",
        environment: "production",
        first_seen: recentTimestamp(900),
        last_seen: recentTimestamp(300),
        merged_into: null,
        metadata: {},
      },
      {
        id: "inc-003",
        title: "Auth Service Health Check Failures",
        severity: "high",
        status: "open",
        investigation_ids: ["inv-004"],
        correlation_score: 0.71,
        correlation_reasons: ["health check pattern", "certificate expiry"],
        service: "auth-service",
        environment: "production",
        first_seen: pastDate(2),
        last_seen: pastDate(1),
        merged_into: null,
        metadata: {},
      },
    ],
    total: 3,
  };
}

export function getCustomPlaybooks() {
  return [
    { id: "cpb-001", name: "Custom Memory Alert", description: "Custom playbook for memory alerts", yaml: "name: custom-memory\ntrigger:\n  condition: memory > 85%\nactions:\n  - restart_pod", created_at: pastDate(5), updated_at: pastDate(1) },
  ];
}
