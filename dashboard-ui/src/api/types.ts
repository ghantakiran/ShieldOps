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

// ── Vulnerability Management ─────────────────────────────────────

export type VulnerabilityStatus =
  | "new"
  | "triaged"
  | "in_progress"
  | "remediated"
  | "verified"
  | "closed"
  | "accepted_risk";

export interface VulnerabilityDetail {
  id: string;
  cve_id: string | null;
  scan_id: string | null;
  source: string;
  scanner_type: string;
  severity: string;
  cvss_score: number;
  title: string;
  description: string;
  package_name: string;
  affected_resource: string;
  status: VulnerabilityStatus;
  assigned_team_id: string | null;
  assigned_user_id: string | null;
  sla_due_at: string | null;
  sla_breached: boolean;
  first_seen_at: string;
  last_seen_at: string;
  remediated_at: string | null;
  closed_at: string | null;
  remediation_steps: Array<{ step: string }>;
  scan_metadata: Record<string, unknown>;
  comments?: VulnerabilityComment[];
  created_at: string;
  updated_at: string;
}

export interface VulnerabilityListItem {
  id: string;
  cve_id: string | null;
  source: string;
  scanner_type: string;
  severity: string;
  cvss_score: number;
  title: string;
  affected_resource: string;
  status: VulnerabilityStatus;
  assigned_team_id: string | null;
  sla_breached: boolean;
  first_seen_at: string;
  created_at: string;
}

export interface VulnerabilityFilter {
  status?: VulnerabilityStatus;
  severity?: string;
  scanner_type?: string;
  team_id?: string;
  sla_breached?: boolean;
}

export interface VulnerabilityStats {
  total: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  sla_breaches: number;
}

export interface VulnerabilityComment {
  id: string;
  vulnerability_id: string;
  user_id: string | null;
  content: string;
  comment_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface RiskAcceptance {
  id: string;
  vulnerability_id: string;
  accepted_by: string;
  reason: string;
  expires_at: string | null;
  created_at: string;
}

export interface Team {
  id: string;
  name: string;
  description: string;
  slack_channel: string;
  pagerduty_service_id: string;
  email: string;
  members?: TeamMember[];
  vulnerability_count?: number;
  created_at: string;
}

export interface TeamMember {
  id: string;
  team_id: string;
  user_id: string;
  role: string;
  created_at: string;
}

export interface SecurityPostureSummary {
  overall_score: number;
  critical_cves: number;
  high_cves: number;
  pending_patches: number;
  credentials_expiring_soon: number;
  compliance_scores: Record<string, number>;
  top_risks: string[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  actions?: ChatAction[];
}

export interface ChatAction {
  type: string;
  label: string;
  data: Record<string, unknown>;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
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

// ── Billing ──────────────────────────────────────────────────────────

export interface BillingPlan {
  key: string;
  name: string;
  agent_limit: number;
  api_calls_limit: number;
  features: string[];
  has_price: boolean;
}

export interface BillingSubscription {
  org_id: string;
  plan: string;
  plan_name: string;
  agent_limit: number;
  api_calls_limit: number;
  status: string;
  stripe_subscription_id: string | null;
  current_period_end: number | null;
  cancel_at_period_end: boolean;
}

export interface BillingUsage {
  org_id: string;
  plan: string;
  agents_used: number;
  agents_limit: number;
  agents_percent: number;
  api_calls_used: number;
  api_calls_limit: number;
  api_calls_percent: number;
}

export interface CheckoutResponse {
  session_id: string;
  url: string;
}

// ── Incident Timeline ─────────────────────────────────────────────────

export type IncidentTimelineEventType =
  | "investigation"
  | "remediation"
  | "audit"
  | "security";

export interface IncidentTimelineEvent {
  id: string;
  timestamp: string;
  type: IncidentTimelineEventType;
  action: string;
  actor: string;
  severity?: string;
  details: Record<string, unknown>;
}

export interface IncidentTimelineResponse {
  investigation_id: string;
  events: IncidentTimelineEvent[];
  total: number;
}

// ── Agent Performance ─────────────────────────────────────────────────

export interface AgentPerformanceTrend {
  date: string;
  executions: number;
  success_rate: number;
}

export interface AgentPerformanceAgent {
  agent_type: string;
  total_executions: number;
  success_rate: number;
  avg_duration_seconds: number;
  error_count: number;
  p50_duration: number;
  p95_duration: number;
  p99_duration: number;
  trend: AgentPerformanceTrend[];
}

export interface HeatmapCell {
  hour: number;
  day: string;
  count: number;
}

// ── Global Search ─────────────────────────────────────────────────

export type SearchEntityType =
  | "investigation"
  | "remediation"
  | "vulnerability"
  | "agent";

export interface SearchResult {
  entity_type: SearchEntityType;
  id: string;
  title: string;
  description: string;
  status: string;
  relevance: number;
  url: string;
  created_at: string | null;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResult[];
}

export interface AgentPerformanceSummary {
  total_executions: number;
  avg_success_rate: number;
  avg_duration_seconds: number;
  total_errors: number;
}

export interface AgentPerformanceResponse {
  period: string;
  summary: AgentPerformanceSummary;
  agents: AgentPerformanceAgent[];
  hourly_heatmap: HeatmapCell[];
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
