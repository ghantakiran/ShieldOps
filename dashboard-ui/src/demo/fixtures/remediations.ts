import type { Remediation, RemediationDetail } from "../../api/types";
import { recentTimestamp, pastDate } from "../config";

export function getRemediations(): Remediation[] {
  return [
    {
      id: "rem-001",
      investigation_id: "inv-001",
      action_type: "rollback_deployment",
      target_resource: "payment-service",
      environment: "production",
      risk_level: "high",
      status: "pending_approval",
      started_at: recentTimestamp(2400),
      completed_at: null,
    },
    {
      id: "rem-002",
      investigation_id: "inv-003",
      action_type: "rotate_credentials",
      target_resource: "s3-archive-iam-role",
      environment: "production",
      risk_level: "medium",
      status: "completed",
      started_at: pastDate(1),
      completed_at: recentTimestamp(72000),
    },
    {
      id: "rem-003",
      investigation_id: "inv-004",
      action_type: "scale_service",
      target_resource: "user-auth-service",
      environment: "production",
      risk_level: "low",
      status: "completed",
      started_at: pastDate(2),
      completed_at: pastDate(2),
    },
    {
      id: "rem-004",
      investigation_id: "inv-005",
      action_type: "block_ip_ranges",
      target_resource: "waf-prod-us-east-1",
      environment: "production",
      risk_level: "medium",
      status: "completed",
      started_at: pastDate(3),
      completed_at: pastDate(3),
    },
    {
      id: "rem-005",
      investigation_id: null,
      action_type: "patch_cve",
      target_resource: "nginx-ingress-controller",
      environment: "staging",
      risk_level: "critical",
      status: "executing",
      started_at: recentTimestamp(300),
      completed_at: null,
    },
    {
      id: "rem-006",
      investigation_id: null,
      action_type: "restart_service",
      target_resource: "cache-cluster-prod",
      environment: "production",
      risk_level: "low",
      status: "rolled_back",
      started_at: pastDate(5),
      completed_at: pastDate(5),
    },
  ];
}

export function getRemediationDetail(id: string): RemediationDetail | null {
  const remediations = getRemediations();
  const base = remediations.find((r) => r.id === id);
  if (!base) return null;

  if (id === "rem-001") {
    return {
      ...base,
      parameters: {
        service: "payment-service",
        from_version: "v2.3.1",
        to_version: "v2.3.0",
        strategy: "rolling",
        max_surge: "25%",
        max_unavailable: 0,
      },
      approval: {
        request_id: "apr-001",
        status: "pending",
        requested_at: recentTimestamp(2400),
        decided_at: null,
        decided_by: null,
      },
      rollback_snapshot_id: "snap-payment-v231-20240315",
      timeline: [
        { timestamp: recentTimestamp(2400), event_type: "remediation_created", description: "Rollback remediation created from investigation inv-001" },
        { timestamp: recentTimestamp(2380), event_type: "policy_check", description: "OPA policy evaluation: PASS — rollback_deployment allowed in production" },
        { timestamp: recentTimestamp(2370), event_type: "snapshot_created", description: "Pre-rollback snapshot created: snap-payment-v231-20240315" },
        { timestamp: recentTimestamp(2360), event_type: "approval_requested", description: "Approval requested — high risk action requires human approval" },
      ],
    };
  }

  return {
    ...base,
    parameters: { target: base.target_resource, action: base.action_type },
    approval: base.status === "completed" ? {
      request_id: `apr-${id}`,
      status: "approved",
      requested_at: base.started_at,
      decided_at: base.started_at,
      decided_by: "ops-team@shieldops.io",
    } : null,
    rollback_snapshot_id: null,
    timeline: [
      { timestamp: base.started_at, event_type: "remediation_created", description: `Remediation ${base.action_type} initiated` },
    ],
  };
}
