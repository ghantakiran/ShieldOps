/** Shared API response types matching the FastAPI backend. */

export interface HealthCheck {
  status: string;
  version: string;
}

export interface ReadinessCheck {
  status: "ready" | "degraded";
  version: string;
  checks: Record<string, string>;
}

// ── Auth ──────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
}

// ── Agents ────────────────────────────────────────────────────────────

export type AgentType =
  | "investigation"
  | "remediation"
  | "security"
  | "cost"
  | "learning"
  | "supervisor";

export type AgentStatus = "idle" | "running" | "error" | "offline";

export interface Agent {
  id: string;
  agent_type: AgentType;
  environment: string;
  status: AgentStatus;
  last_heartbeat: string | null;
  registered_at: string;
}

// ── Investigations ────────────────────────────────────────────────────

export type InvestigationStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed";

export interface Investigation {
  id: string;
  alert_id: string;
  alert_name: string;
  severity: string;
  resource_id: string;
  status: InvestigationStatus;
  root_cause: string | null;
  confidence: number | null;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface InvestigationDetail extends Investigation {
  findings: Record<string, unknown>[];
  recommended_actions: string[];
  timeline: TimelineEvent[];
}

// ── Remediations ──────────────────────────────────────────────────────

export type RemediationStatus =
  | "pending_approval"
  | "approved"
  | "executing"
  | "completed"
  | "failed"
  | "rolled_back";

export interface Remediation {
  id: string;
  investigation_id: string | null;
  action_type: string;
  target_resource: string;
  environment: string;
  risk_level: "low" | "medium" | "high" | "critical";
  status: RemediationStatus;
  started_at: string;
  completed_at: string | null;
}

export interface RemediationDetail extends Remediation {
  parameters: Record<string, unknown>;
  approval: ApprovalInfo | null;
  rollback_snapshot_id: string | null;
  timeline: TimelineEvent[];
}

export interface ApprovalInfo {
  request_id: string;
  status: "pending" | "approved" | "denied" | "expired";
  requested_at: string;
  decided_at: string | null;
  decided_by: string | null;
}

// ── Security ──────────────────────────────────────────────────────────

export interface SecurityScan {
  id: string;
  scan_type: "vulnerability" | "credential" | "compliance" | "posture";
  environment: string;
  status: "running" | "completed" | "failed";
  findings_count: number;
  critical_count: number;
  started_at: string;
  completed_at: string | null;
}

export interface Vulnerability {
  cve_id: string;
  severity: string;
  cvss_score: number;
  package_name: string;
  installed_version: string;
  fixed_version: string | null;
  affected_resource: string;
}

// ── Cost ──────────────────────────────────────────────────────────────

export interface CostSummary {
  total_daily: number;
  total_monthly: number;
  change_percent: number;
  top_services: CostByService[];
  anomalies: CostAnomaly[];
}

export interface CostByService {
  service: string;
  daily_cost: number;
  monthly_cost: number;
  change_percent: number;
}

export interface CostAnomaly {
  service: string;
  expected: number;
  actual: number;
  deviation_percent: number;
  detected_at: string;
}

// ── Learning ──────────────────────────────────────────────────────────

export interface LearningCycle {
  id: string;
  cycle_type: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  patterns_found: number;
  playbooks_updated: number;
}

export interface Playbook {
  id: string;
  name: string;
  description: string;
  trigger_conditions: string[];
  actions: string[];
  success_rate: number;
  last_used: string | null;
}

// ── Analytics ─────────────────────────────────────────────────────────

export interface AnalyticsSummary {
  total_investigations: number;
  total_remediations: number;
  auto_resolved_percent: number;
  mean_time_to_resolve_seconds: number;
  investigations_by_status: Record<string, number>;
  remediations_by_status: Record<string, number>;
}

// ── Shared ────────────────────────────────────────────────────────────

export interface TimelineEvent {
  timestamp: string;
  event_type: string;
  description: string;
  metadata?: Record<string, unknown>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface WebSocketMessage {
  type: "agent_status" | "investigation_update" | "remediation_update" | "alert";
  payload: Record<string, unknown>;
  timestamp: string;
}
