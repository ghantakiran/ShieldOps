import type { IncidentTimelineEvent } from "../../api/types";
import { recentTimestamp, pastDate } from "../config";

export function getAuditLogs(): IncidentTimelineEvent[] {
  return [
    {
      id: "audit-001",
      timestamp: recentTimestamp(600),
      type: "remediation",
      action: "rollback_deployment",
      actor: "remediation-agent",
      severity: "high",
      details: { target: "payment-service", from: "v2.3.1", to: "v2.3.0" },
    },
    {
      id: "audit-002",
      timestamp: recentTimestamp(2400),
      type: "investigation",
      action: "root_cause_identified",
      actor: "investigation-agent",
      severity: "critical",
      details: { investigation_id: "inv-001", confidence: 0.91 },
    },
    {
      id: "audit-003",
      timestamp: recentTimestamp(3600),
      type: "security",
      action: "scan_completed",
      actor: "security-agent",
      severity: "info",
      details: { scan_type: "vulnerability", findings: 23 },
    },
    {
      id: "audit-004",
      timestamp: pastDate(1),
      type: "remediation",
      action: "credential_rotated",
      actor: "security-agent",
      severity: "medium",
      details: { credential: "s3-archive-iam-role", environment: "production" },
    },
    {
      id: "audit-005",
      timestamp: pastDate(1),
      type: "audit",
      action: "policy_updated",
      actor: "admin@shieldops.io",
      severity: "info",
      details: { policy: "max_blast_radius", old_value: "5%", new_value: "3%" },
    },
    {
      id: "audit-006",
      timestamp: pastDate(2),
      type: "remediation",
      action: "service_scaled",
      actor: "remediation-agent",
      severity: "low",
      details: { service: "user-auth-service", replicas: { from: 3, to: 5 } },
    },
    {
      id: "audit-007",
      timestamp: pastDate(3),
      type: "security",
      action: "ip_blocked",
      actor: "security-agent",
      severity: "high",
      details: { ip_ranges: 3, reason: "credential_stuffing" },
    },
    {
      id: "audit-008",
      timestamp: pastDate(4),
      type: "investigation",
      action: "investigation_completed",
      actor: "investigation-agent",
      severity: "info",
      details: { investigation_id: "inv-006", duration: "30m" },
    },
  ];
}

export function getInvestigationTimeline(investigationId: string) {
  return {
    investigation_id: investigationId,
    events: getAuditLogs().filter((e) =>
      e.details.investigation_id === investigationId || e.type === "investigation"
    ).slice(0, 5),
    total: 5,
  };
}
