import { useState, useMemo } from "react";
import {
  Play,
  Square,
  ChevronDown,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Pause,
  Loader2,
  Search,
  Shield,
  Wrench,
  Eye,
  Bot,
  AlertTriangle,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";
import StatusBadge from "../components/StatusBadge";

import {
  DEMO_WORKFLOW_RUNS,
  type WorkflowRun,
  type WorkflowType,
  type WorkflowStatus,
  type StepStatus,
  type WorkflowStep,
} from "../demo/workflowData";

interface EscalationPolicy {
  severity: string;
  auto_remediate: boolean;
  notify_channels: string[];
  page_oncall: boolean;
}

const ESCALATION_POLICIES: EscalationPolicy[] = [
  {
    severity: "critical",
    auto_remediate: true,
    notify_channels: ["#incidents", "#sre-oncall", "PagerDuty"],
    page_oncall: true,
  },
  {
    severity: "high",
    auto_remediate: true,
    notify_channels: ["#incidents", "#sre-oncall"],
    page_oncall: true,
  },
  {
    severity: "warning",
    auto_remediate: false,
    notify_channels: ["#incidents"],
    page_oncall: false,
  },
  {
    severity: "info",
    auto_remediate: false,
    notify_channels: ["#observability"],
    page_oncall: false,
  },
];

// ── Helpers ──────────────────────────────────────────────────────────

const WORKFLOW_LABELS: Record<WorkflowType, string> = {
  incident_response: "Incident Response",
  security_scan: "Security Scan",
  proactive_check: "Proactive Check",
};

const AGENT_ICONS: Record<string, typeof Search> = {
  investigation: Eye,
  security: Shield,
  remediation: Wrench,
  learning: Bot,
};

const STEP_STATUS_ICON: Record<StepStatus, typeof CheckCircle2> = {
  completed: CheckCircle2,
  running: Loader2,
  pending: Clock,
  failed: XCircle,
  skipped: Pause,
};

const STEP_STATUS_COLOR: Record<StepStatus, string> = {
  completed: "text-green-400",
  running: "text-blue-400",
  pending: "text-gray-500",
  failed: "text-red-400",
  skipped: "text-gray-600",
};

function formatDuration(startIso: string, endIso: string | null): string {
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const seconds = Math.floor((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return `${mins}m ${secs}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

function stepsProgress(steps: WorkflowStep[]): string {
  const done = steps.filter((s) => s.status === "completed").length;
  return `${done}/${steps.length} completed`;
}

// ── Sub-components ───────────────────────────────────────────────────

function RunWorkflowButton({ onRun }: { onRun: (type: WorkflowType) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
      >
        <Play className="h-4 w-4" />
        Run Workflow
        <ChevronDown className={clsx("h-4 w-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-gray-700 bg-gray-800 py-1 shadow-lg">
          {(Object.keys(WORKFLOW_LABELS) as WorkflowType[]).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => {
                onRun(type);
                setOpen(false);
              }}
              className="block w-full px-4 py-2 text-left text-sm text-gray-200 hover:bg-gray-700"
            >
              {WORKFLOW_LABELS[type]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StepIndicator({ steps }: { steps: WorkflowStep[] }) {
  return (
    <div className="flex items-center gap-1">
      {steps.map((step, i) => {
        const Icon = STEP_STATUS_ICON[step.status];
        const AgentIcon = AGENT_ICONS[step.agent_type] ?? Bot;
        return (
          <div key={step.id} className="flex items-center gap-1">
            <div
              className={clsx(
                "flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs",
                step.status === "running"
                  ? "border-blue-500/30 bg-blue-500/10"
                  : step.status === "completed"
                    ? "border-green-500/20 bg-green-500/5"
                    : step.status === "failed"
                      ? "border-red-500/20 bg-red-500/5"
                      : "border-gray-700 bg-gray-800/50",
              )}
              title={`${step.agent_type}: ${step.action.replace(/_/g, " ")}`}
            >
              <AgentIcon className={clsx("h-3 w-3", STEP_STATUS_COLOR[step.status])} />
              <Icon
                className={clsx(
                  "h-3 w-3",
                  STEP_STATUS_COLOR[step.status],
                  step.status === "running" && "animate-spin",
                )}
              />
            </div>
            {i < steps.length - 1 && (
              <div
                className={clsx(
                  "h-px w-3",
                  step.status === "completed" ? "bg-green-500/40" : "bg-gray-700",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ActiveRunCard({
  run,
  onCancel,
}: {
  run: WorkflowRun;
  onCancel: (id: string) => void;
}) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-100">
              {WORKFLOW_LABELS[run.workflow_type]}
            </span>
            <StatusBadge status={run.status} />
            <span className="text-xs text-gray-500">
              Trigger: {run.trigger_type}
            </span>
          </div>
          <p className="text-xs text-gray-500">
            Started {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
            {" \u00b7 "}
            {formatDuration(run.started_at, run.completed_at)} elapsed
          </p>
        </div>
        {(run.status === "running" || run.status === "paused") && (
          <button
            type="button"
            onClick={() => onCancel(run.id)}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-red-500/50 hover:text-red-400"
          >
            <Square className="h-3 w-3" />
            Cancel
          </button>
        )}
      </div>
      <div className="mt-3">
        <StepIndicator steps={run.steps} />
      </div>
    </div>
  );
}

function ExpandableRunRow({ run }: { run: WorkflowRun }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        onClick={() => setExpanded(!expanded)}
        className="cursor-pointer border-b border-gray-800 transition-colors hover:bg-gray-900"
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-1.5">
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-gray-500" />
            )}
            <span className="text-sm font-medium text-gray-100">
              {WORKFLOW_LABELS[run.workflow_type]}
            </span>
          </div>
        </td>
        <td className="px-4 py-3 text-xs text-gray-400">{run.trigger_type}</td>
        <td className="px-4 py-3">
          <StatusBadge status={run.status} />
        </td>
        <td className="px-4 py-3 text-xs text-gray-400">{stepsProgress(run.steps)}</td>
        <td className="px-4 py-3 text-xs text-gray-400">
          {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
        </td>
        <td className="px-4 py-3 text-xs text-gray-400">
          {formatDuration(run.started_at, run.completed_at)}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-gray-800">
          <td colSpan={6} className="bg-gray-900/50 px-4 py-3">
            <div className="space-y-2">
              {run.steps.map((step) => {
                const AgentIcon = AGENT_ICONS[step.agent_type] ?? Bot;
                const StatusIcon = STEP_STATUS_ICON[step.status];
                return (
                  <div
                    key={step.id}
                    className="flex items-start gap-3 rounded-md border border-gray-800 bg-gray-950 px-3 py-2"
                  >
                    <AgentIcon
                      className={clsx("mt-0.5 h-4 w-4 shrink-0", STEP_STATUS_COLOR[step.status])}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-gray-200">
                          {step.action.replace(/_/g, " ")}
                        </span>
                        <StatusIcon
                          className={clsx(
                            "h-3.5 w-3.5",
                            STEP_STATUS_COLOR[step.status],
                            step.status === "running" && "animate-spin",
                          )}
                        />
                        <span className="text-xs text-gray-500">{step.agent_type} agent</span>
                      </div>
                      {step.result && (
                        <p className="mt-1 text-xs text-gray-400">{step.result}</p>
                      )}
                      {step.error && (
                        <p className="mt-1 text-xs text-red-400">{step.error}</p>
                      )}
                      {step.started_at && (
                        <p className="mt-1 text-xs text-gray-600">
                          {step.completed_at
                            ? `Duration: ${formatDuration(step.started_at, step.completed_at)}`
                            : `Running for ${formatDuration(step.started_at, null)}`}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export default function Workflows() {
  const [runs, setRuns] = useState<WorkflowRun[]>(DEMO_WORKFLOW_RUNS);
  const [statusFilter, setStatusFilter] = useState("all");

  const activeRuns = useMemo(
    () => runs.filter((r) => r.status === "running" || r.status === "paused" || r.status === "pending"),
    [runs],
  );

  const recentRuns = useMemo(() => {
    const filtered = statusFilter === "all"
      ? runs
      : runs.filter((r) => r.status === statusFilter);
    return [...filtered].sort(
      (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
    );
  }, [runs, statusFilter]);

  function handleRunWorkflow(type: WorkflowType) {
    const newRun: WorkflowRun = {
      id: `wfr-${Date.now()}`,
      workflow_type: type,
      trigger_type: "manual",
      status: "pending",
      started_at: new Date().toISOString(),
      completed_at: null,
      steps: [
        {
          id: `s-${Date.now()}-1`,
          agent_type: "investigation",
          action: "initialize",
          status: "pending",
          started_at: null,
          completed_at: null,
          result: null,
          error: null,
        },
      ],
    };
    setRuns((prev) => [newRun, ...prev]);
  }

  function handleCancel(runId: string) {
    setRuns((prev) =>
      prev.map((r) =>
        r.id === runId
          ? { ...r, status: "cancelled" as WorkflowStatus, completed_at: new Date().toISOString() }
          : r,
      ),
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-100">Workflows</h1>
          <span className="inline-flex items-center rounded-full bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-400 ring-1 ring-inset ring-brand-500/20">
            {activeRuns.length} active
          </span>
        </div>
        <RunWorkflowButton onRun={handleRunWorkflow} />
      </div>

      {/* Active Runs */}
      {activeRuns.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-500">
            Active Runs
          </h2>
          <div className="space-y-3">
            {activeRuns.map((run) => (
              <ActiveRunCard key={run.id} run={run} onCancel={handleCancel} />
            ))}
          </div>
        </section>
      )}

      {activeRuns.length === 0 && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-8 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-gray-600" />
          <p className="mt-2 text-sm text-gray-500">No active workflow runs.</p>
        </div>
      )}

      {/* Recent Runs Table */}
      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
            Recent Runs
          </h2>
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-gray-500" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            >
              <option value="all">All Statuses</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
              <option value="paused">Paused</option>
              <option value="pending">Pending</option>
            </select>
          </div>
        </div>

        {recentRuns.length === 0 ? (
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center">
            <p className="text-sm text-gray-500">No runs match this filter.</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Workflow
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Trigger
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Steps
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Started
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Duration
                  </th>
                </tr>
              </thead>
              <tbody className="bg-gray-950">
                {recentRuns.map((run) => (
                  <ExpandableRunRow key={run.id} run={run} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Escalation Policies */}
      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-500">
          Escalation Policies
        </h2>
        <div className="overflow-hidden rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Severity
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Auto-Remediate
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Notify Channels
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Page On-Call
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 bg-gray-950">
              {ESCALATION_POLICIES.map((policy) => (
                <tr key={policy.severity}>
                  <td className="px-4 py-3">
                    <StatusBadge status={policy.severity} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {policy.auto_remediate ? (
                      <span className="text-green-400">Yes</span>
                    ) : (
                      <span className="text-gray-500">No</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {policy.notify_channels.map((ch) => (
                        <span
                          key={ch}
                          className="inline-flex rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-300"
                        >
                          {ch}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {policy.page_oncall ? (
                      <span className="text-yellow-400">Yes</span>
                    ) : (
                      <span className="text-gray-500">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
