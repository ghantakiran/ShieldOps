import type { SecurityScan, SecurityPostureSummary, VulnerabilityStats } from "../../api/types";
import { recentTimestamp, pastDate } from "../config";

export function getSecurityScans(): SecurityScan[] {
  return [
    {
      id: "scan-001",
      scan_type: "vulnerability",
      environment: "production",
      status: "completed",
      findings_count: 23,
      critical_count: 3,
      started_at: recentTimestamp(7200),
      completed_at: recentTimestamp(6800),
    },
    {
      id: "scan-002",
      scan_type: "compliance",
      environment: "production",
      status: "completed",
      findings_count: 8,
      critical_count: 0,
      started_at: pastDate(1),
      completed_at: pastDate(1),
    },
    {
      id: "scan-003",
      scan_type: "credential",
      environment: "staging",
      status: "completed",
      findings_count: 2,
      critical_count: 1,
      started_at: pastDate(2),
      completed_at: pastDate(2),
    },
    {
      id: "scan-004",
      scan_type: "posture",
      environment: "production",
      status: "running",
      findings_count: 0,
      critical_count: 0,
      started_at: recentTimestamp(120),
      completed_at: null,
    },
  ];
}

export function getSecurityPosture(): SecurityPostureSummary {
  return {
    overall_score: 78,
    critical_cves: 3,
    high_cves: 12,
    pending_patches: 7,
    credentials_expiring_soon: 4,
    compliance_scores: {
      SOC2: 92,
      HIPAA: 85,
      PCI: 78,
      GDPR: 88,
      ISO27001: 81,
    },
    top_risks: [
      "CVE-2024-21762 — FortiOS RCE (CVSS 9.8)",
      "3 IAM roles with overly permissive policies",
      "S3 bucket logging disabled on 2 production buckets",
      "TLS 1.0/1.1 still enabled on legacy load balancer",
    ],
  };
}

export function getVulnerabilityStats(): VulnerabilityStats {
  return {
    total: 48,
    by_severity: {
      critical: 3,
      high: 12,
      medium: 21,
      low: 12,
    },
    by_status: {
      new: 5,
      triaged: 8,
      in_progress: 12,
      remediated: 15,
      verified: 6,
      closed: 2,
    },
    sla_breaches: 2,
  };
}
