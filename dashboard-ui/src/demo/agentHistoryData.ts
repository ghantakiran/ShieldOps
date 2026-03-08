export interface AgentRun {
  id: string;
  title: string;
  prompt: string;
  status: "completed" | "running" | "failed" | "awaiting-approval";
  persona: string;
  startedAt: string;
  duration: string;
  stepsCompleted: number;
  totalSteps: number;
  icon: string;
  iconColor: string;
  trigger: "manual" | "scheduled" | "alert" | "slack";
  artifacts: number;
}

export interface RecentRun {
  id: string;
  title: string;
  status: "completed" | "running" | "failed" | "awaiting-approval";
  startedAt: string;
  duration: string;
  icon: string;
  iconColor: string;
}

export const DEMO_AGENT_RUNS: AgentRun[] = [
  {
    id: "run-001",
    title: "Investigated Splunk 500 errors in payment-service",
    prompt: "Investigate the recurring 500 errors in payment-service from Splunk",
    status: "completed",
    persona: "SRE Engineer",
    startedAt: "12 min ago",
    duration: "3m 22s",
    stepsCompleted: 5,
    totalSteps: 5,
    icon: "search",
    iconColor: "text-green-400",
    trigger: "alert",
    artifacts: 3,
  },
  {
    id: "run-002",
    title: "Auto-remediated high CPU on k8s-prod-cluster-03",
    prompt: "Fix the high CPU issue on k8s-prod-cluster-03",
    status: "completed",
    persona: "SRE Engineer",
    startedAt: "28 min ago",
    duration: "1m 47s",
    stepsCompleted: 4,
    totalSteps: 4,
    icon: "wrench",
    iconColor: "text-brand-400",
    trigger: "alert",
    artifacts: 2,
  },
  {
    id: "run-003",
    title: "Scanning CVEs in auth-service dependencies",
    prompt: "Run a full security scan on auth-service",
    status: "running",
    persona: "Security Analyst",
    startedAt: "2 min ago",
    duration: "2m 10s",
    stepsCompleted: 3,
    totalSteps: 5,
    icon: "shield-alert",
    iconColor: "text-amber-400",
    trigger: "manual",
    artifacts: 0,
  },
  {
    id: "run-004",
    title: "War room for payment gateway outage",
    prompt: "Create a war room for the current payment gateway outage",
    status: "awaiting-approval",
    persona: "SRE Engineer",
    startedAt: "5 min ago",
    duration: "4m 32s",
    stepsCompleted: 3,
    totalSteps: 5,
    icon: "users",
    iconColor: "text-red-400",
    trigger: "manual",
    artifacts: 1,
  },
  {
    id: "run-005",
    title: "Fixed bug #2341 reported in #eng-bugs",
    prompt: "Fix bug #2341 from Slack channel #eng-bugs",
    status: "completed",
    persona: "DevOps Engineer",
    startedAt: "1h ago",
    duration: "7m 15s",
    stepsCompleted: 6,
    totalSteps: 6,
    icon: "bug",
    iconColor: "text-brand-400",
    trigger: "slack",
    artifacts: 2,
  },
  {
    id: "run-006",
    title: "Created CI/CD pipeline for user-service",
    prompt: "Create a production-grade CI/CD pipeline for user-service repository",
    status: "completed",
    persona: "DevOps Engineer",
    startedAt: "2h ago",
    duration: "4m 50s",
    stepsCompleted: 5,
    totalSteps: 5,
    icon: "workflow",
    iconColor: "text-sky-400",
    trigger: "manual",
    artifacts: 4,
  },
  {
    id: "run-007",
    title: "Nightly security scan - all repositories",
    prompt: "Run nightly security scan across all repositories",
    status: "failed",
    persona: "Security Analyst",
    startedAt: "6h ago",
    duration: "12m 03s",
    stepsCompleted: 3,
    totalSteps: 5,
    icon: "shield-alert",
    iconColor: "text-red-400",
    trigger: "scheduled",
    artifacts: 1,
  },
  {
    id: "run-008",
    title: "Generated runbooks from Q4 incidents",
    prompt: "Analyze all Q4 incidents and generate runbooks for recurring patterns",
    status: "completed",
    persona: "SRE Engineer",
    startedAt: "1d ago",
    duration: "8m 40s",
    stepsCompleted: 4,
    totalSteps: 4,
    icon: "terminal",
    iconColor: "text-sky-400",
    trigger: "manual",
    artifacts: 8,
  },
];

export const DEMO_RECENT_RUNS: RecentRun[] = [
  {
    id: "run-001",
    title: "Investigated Splunk 500 errors in payment-service",
    status: "completed",
    startedAt: "12 min ago",
    duration: "3m 22s",
    icon: "search",
    iconColor: "text-green-400",
  },
  {
    id: "run-002",
    title: "Auto-remediated high CPU on k8s-prod-cluster-03",
    status: "completed",
    startedAt: "28 min ago",
    duration: "1m 47s",
    icon: "wrench",
    iconColor: "text-brand-400",
  },
  {
    id: "run-003",
    title: "Scanning CVEs in auth-service dependencies",
    status: "running",
    startedAt: "2 min ago",
    duration: "2m 10s",
    icon: "shield-alert",
    iconColor: "text-amber-400",
  },
  {
    id: "run-004",
    title: "War room for payment gateway outage",
    status: "awaiting-approval",
    startedAt: "5 min ago",
    duration: "\u2014",
    icon: "users",
    iconColor: "text-red-400",
  },
];
