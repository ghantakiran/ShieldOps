import type { LearningCycle, Playbook } from "../../api/types";
import { pastDate } from "../config";

export function getLearningCycles(): LearningCycle[] {
  return [
    {
      id: "lc-001",
      cycle_type: "pattern_extraction",
      status: "completed",
      started_at: pastDate(1),
      completed_at: pastDate(1),
      patterns_found: 5,
      playbooks_updated: 2,
    },
    {
      id: "lc-002",
      cycle_type: "threshold_tuning",
      status: "completed",
      started_at: pastDate(3),
      completed_at: pastDate(3),
      patterns_found: 3,
      playbooks_updated: 1,
    },
    {
      id: "lc-003",
      cycle_type: "outcome_analysis",
      status: "completed",
      started_at: pastDate(7),
      completed_at: pastDate(7),
      patterns_found: 8,
      playbooks_updated: 4,
    },
    {
      id: "lc-004",
      cycle_type: "pattern_extraction",
      status: "in_progress",
      started_at: pastDate(0),
      completed_at: null,
      patterns_found: 2,
      playbooks_updated: 0,
    },
  ];
}

export function getPlaybooks(): Playbook[] {
  return [
    {
      id: "pb-001",
      name: "OOMKill Auto-Remediation",
      description: "Detects OOM kill patterns and automatically increases memory limits or rolls back recent deployments",
      trigger_conditions: ["container.oom_killed == true", "restart_count > 3"],
      actions: ["analyze_memory_usage", "check_recent_deployments", "rollback_or_scale"],
      success_rate: 0.94,
      last_used: pastDate(1),
    },
    {
      id: "pb-002",
      name: "High Error Rate Response",
      description: "Investigates 5xx error spikes, checks upstream dependencies, and applies circuit breakers",
      trigger_conditions: ["error_rate_5xx > 5%", "duration > 5m"],
      actions: ["analyze_error_logs", "check_dependencies", "apply_circuit_breaker"],
      success_rate: 0.87,
      last_used: pastDate(2),
    },
    {
      id: "pb-003",
      name: "Credential Rotation",
      description: "Automatically rotates expiring credentials and updates dependent services",
      trigger_conditions: ["credential.expires_in < 7d", "credential.type in [api_key, service_account]"],
      actions: ["generate_new_credential", "update_secrets_manager", "rolling_restart_consumers"],
      success_rate: 0.98,
      last_used: pastDate(5),
    },
    {
      id: "pb-004",
      name: "Disk Pressure Remediation",
      description: "Cleans up old logs, archives data, and expands volumes when disk usage exceeds threshold",
      trigger_conditions: ["disk_usage_percent > 85%"],
      actions: ["clean_old_logs", "archive_cold_data", "expand_volume"],
      success_rate: 0.91,
      last_used: pastDate(3),
    },
    {
      id: "pb-005",
      name: "DDoS Mitigation",
      description: "Detects DDoS patterns and enables rate limiting, WAF rules, and CDN caching",
      trigger_conditions: ["request_rate > 10x_baseline", "unique_ips > 1000"],
      actions: ["enable_rate_limiting", "update_waf_rules", "enable_cdn_caching"],
      success_rate: 0.82,
      last_used: pastDate(14),
    },
  ];
}
