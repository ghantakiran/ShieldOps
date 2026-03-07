import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Search,
  ShieldAlert,
  Wrench,
  Bug,
  Users,
  Workflow,
  Terminal,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  Filter,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ───────────────────────────────────────────────────────────────
interface AgentRun {
  id: string;
  title: string;
  prompt: string;
  status: "completed" | "running" | "failed" | "awaiting-approval";
  persona: string;
  startedAt: string;
  duration: string;
  stepsCompleted: number;
  totalSteps: number;
  icon: LucideIcon;
  iconColor: string;
  trigger: "manual" | "scheduled" | "alert" | "slack";
  artifacts: number;
}

// ── Mock Data ───────────────────────────────────────────────────────────
const RUNS: AgentRun[] = [
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
    icon: Search,
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
    icon: Wrench,
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
    icon: ShieldAlert,
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
    icon: Users,
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
    icon: Bug,
    iconColor: "text-purple-400",
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
    icon: Workflow,
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
    icon: ShieldAlert,
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
    icon: Terminal,
    iconColor: "text-violet-400",
    trigger: "manual",
    artifacts: 8,
  },
];

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string; icon: LucideIcon }> = {
  completed: { bg: "bg-emerald-500/10", text: "text-emerald-400", label: "Completed", icon: CheckCircle2 },
  running: { bg: "bg-brand-500/10", text: "text-brand-400", label: "Running", icon: Loader2 },
  failed: { bg: "bg-red-500/10", text: "text-red-400", label: "Failed", icon: XCircle },
  "awaiting-approval": { bg: "bg-amber-500/10", text: "text-amber-400", label: "Needs Approval", icon: AlertTriangle },
};

const TRIGGER_STYLES: Record<string, { label: string; color: string }> = {
  manual: { label: "Manual", color: "text-gray-400" },
  scheduled: { label: "Scheduled", color: "text-blue-400" },
  alert: { label: "Alert", color: "text-red-400" },
  slack: { label: "Slack", color: "text-purple-400" },
};

// ── Component ───────────────────────────────────────────────────────────
export default function AgentHistory() {
  const navigate = useNavigate();
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredRuns = RUNS.filter((run) => {
    if (filterStatus !== "all" && run.status !== filterStatus) return false;
    if (searchQuery && !run.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: RUNS.length,
    completed: RUNS.filter((r) => r.status === "completed").length,
    running: RUNS.filter((r) => r.status === "running").length,
    failed: RUNS.filter((r) => r.status === "failed").length,
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="h-5 w-5 text-brand-400" />
            Agent History
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Track all agent runs, their outcomes, and artifacts
          </p>
        </div>

        {/* Stats pills */}
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-gray-800/60 px-3 py-1.5 text-xs text-gray-300">
            <span className="font-bold text-white">{stats.total}</span> total
          </span>
          <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
            <span className="font-bold">{stats.completed}</span> completed
          </span>
          <span className="rounded-lg bg-brand-500/10 px-3 py-1.5 text-xs text-brand-400">
            <span className="font-bold">{stats.running}</span> running
          </span>
          <span className="rounded-lg bg-red-500/10 px-3 py-1.5 text-xs text-red-400">
            <span className="font-bold">{stats.failed}</span> failed
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search agent runs..."
            className="w-full rounded-xl border border-gray-700 bg-gray-800/50 pl-10 pr-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 focus:border-brand-500/50 focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-500" />
          {["all", "completed", "running", "failed", "awaiting-approval"].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                filterStatus === status
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-500 hover:bg-gray-800 hover:text-gray-300",
              )}
            >
              {status === "all" ? "All" : status === "awaiting-approval" ? "Pending" : status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Runs list */}
      <div className="space-y-2">
        {filteredRuns.map((run) => {
          const status = STATUS_STYLES[run.status];
          const trigger = TRIGGER_STYLES[run.trigger];
          const StatusIcon = status.icon;

          return (
            <button
              key={run.id}
              onClick={() =>
                navigate(`/app/agent-task?prompt=${encodeURIComponent(run.prompt)}&run=${run.id}`)
              }
              className="flex w-full items-center gap-4 rounded-xl border border-gray-800/50 bg-gray-900/40 px-5 py-4 text-left transition-all hover:border-gray-700 hover:bg-gray-800/40"
            >
              {/* Icon */}
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-800/60">
                <run.icon className={clsx("h-5 w-5", run.iconColor)} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-200 truncate">{run.title}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-gray-600">{run.startedAt}</span>
                  <span className="text-xs text-gray-600 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {run.duration}
                  </span>
                  <span className="text-xs text-gray-600">
                    {run.stepsCompleted}/{run.totalSteps} steps
                  </span>
                  <span className={clsx("text-xs", trigger.color)}>{trigger.label}</span>
                  <span className="text-xs text-gray-600">{run.persona}</span>
                </div>
              </div>

              {/* Progress / status */}
              <div className="flex items-center gap-3 shrink-0">
                {run.artifacts > 0 && (
                  <span className="text-xs text-gray-600">{run.artifacts} artifacts</span>
                )}
                <span
                  className={clsx(
                    "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
                    status.bg,
                    status.text,
                  )}
                >
                  <StatusIcon
                    className={clsx(
                      "h-3.5 w-3.5",
                      run.status === "running" && "animate-spin",
                    )}
                  />
                  {status.label}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {filteredRuns.length === 0 && (
        <div className="py-16 text-center">
          <Activity className="h-10 w-10 text-gray-700 mx-auto mb-3" />
          <p className="text-sm text-gray-500">No agent runs match your filters.</p>
        </div>
      )}
    </div>
  );
}
