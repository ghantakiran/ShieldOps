import { useState, useMemo } from "react";
import { Play, ChevronDown, ChevronRight, CheckCircle, XCircle, Clock, Activity } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";

// --- Types ---

interface TimelineEntry {
  timestamp: string;
  event: string;
  details?: string;
}

interface Recommendation {
  id: string;
  action: string;
  target: string;
  risk_level: string;
  description: string;
}

interface PipelineRun {
  id: string;
  alert_name: string;
  namespace: string;
  service: string;
  status: string;
  started_at: string;
  duration_seconds: number | null;
  timeline: TimelineEntry[];
  recommendations: Recommendation[];
}

// --- Mock Data ---

const MOCK_RUNS: PipelineRun[] = [
  {
    id: "run-001",
    alert_name: "HighErrorRate",
    namespace: "production",
    service: "api-gateway",
    status: "completed",
    started_at: "2026-03-07T09:12:00Z",
    duration_seconds: 342,
    timeline: [
      { timestamp: "2026-03-07T09:12:00Z", event: "Pipeline started", details: "Triggered by alert HighErrorRate" },
      { timestamp: "2026-03-07T09:12:15Z", event: "Investigation started" },
      { timestamp: "2026-03-07T09:14:30Z", event: "Root cause identified", details: "Upstream dependency timeout causing 503s" },
      { timestamp: "2026-03-07T09:15:00Z", event: "Recommendations generated" },
      { timestamp: "2026-03-07T09:15:45Z", event: "Auto-approved (low risk)" },
      { timestamp: "2026-03-07T09:16:10Z", event: "Remediation executed" },
      { timestamp: "2026-03-07T09:17:42Z", event: "Verification passed", details: "Error rate returned to baseline" },
    ],
    recommendations: [
      { id: "rec-001a", action: "restart", target: "api-gateway-pod-3", risk_level: "low", description: "Restart unhealthy pod to clear stale connections" },
      { id: "rec-001b", action: "scale", target: "api-gateway", risk_level: "low", description: "Scale replicas from 3 to 5 to absorb traffic" },
    ],
  },
  {
    id: "run-002",
    alert_name: "MemoryPressure",
    namespace: "production",
    service: "order-processor",
    status: "awaiting_approval",
    started_at: "2026-03-07T10:45:00Z",
    duration_seconds: null,
    timeline: [
      { timestamp: "2026-03-07T10:45:00Z", event: "Pipeline started", details: "Triggered by alert MemoryPressure" },
      { timestamp: "2026-03-07T10:45:20Z", event: "Investigation started" },
      { timestamp: "2026-03-07T10:48:10Z", event: "Root cause identified", details: "Memory leak in order-processor v2.3.1" },
      { timestamp: "2026-03-07T10:48:30Z", event: "Recommendations generated" },
      { timestamp: "2026-03-07T10:48:31Z", event: "Awaiting human approval", details: "High-risk action requires manual approval" },
    ],
    recommendations: [
      { id: "rec-002a", action: "rollback", target: "order-processor", risk_level: "high", description: "Rollback to v2.3.0 (last stable release)" },
      { id: "rec-002b", action: "restart", target: "order-processor-pod-*", risk_level: "medium", description: "Rolling restart all pods to reclaim memory" },
    ],
  },
  {
    id: "run-003",
    alert_name: "CertificateExpiring",
    namespace: "staging",
    service: "ingress-controller",
    status: "investigating",
    started_at: "2026-03-07T11:30:00Z",
    duration_seconds: null,
    timeline: [
      { timestamp: "2026-03-07T11:30:00Z", event: "Pipeline started", details: "Triggered by alert CertificateExpiring" },
      { timestamp: "2026-03-07T11:30:12Z", event: "Investigation started", details: "Analyzing certificate chain and renewal status" },
    ],
    recommendations: [],
  },
  {
    id: "run-004",
    alert_name: "DiskSpaceLow",
    namespace: "production",
    service: "postgres-primary",
    status: "failed",
    started_at: "2026-03-07T08:00:00Z",
    duration_seconds: 120,
    timeline: [
      { timestamp: "2026-03-07T08:00:00Z", event: "Pipeline started", details: "Triggered by alert DiskSpaceLow" },
      { timestamp: "2026-03-07T08:00:15Z", event: "Investigation started" },
      { timestamp: "2026-03-07T08:01:30Z", event: "Root cause identified", details: "WAL logs consuming 89% of disk" },
      { timestamp: "2026-03-07T08:01:45Z", event: "Recommendations generated" },
      { timestamp: "2026-03-07T08:02:00Z", event: "Pipeline failed", details: "Policy violation: cannot modify database storage without DBA approval" },
    ],
    recommendations: [
      { id: "rec-004a", action: "cleanup", target: "postgres-primary:/var/lib/postgresql/wal", risk_level: "critical", description: "Archive and remove old WAL segments" },
    ],
  },
  {
    id: "run-005",
    alert_name: "LatencySpike",
    namespace: "production",
    service: "search-service",
    status: "pending",
    started_at: "2026-03-07T11:55:00Z",
    duration_seconds: null,
    timeline: [
      { timestamp: "2026-03-07T11:55:00Z", event: "Pipeline queued", details: "Waiting for available agent capacity" },
    ],
    recommendations: [],
  },
  {
    id: "run-006",
    alert_name: "PodCrashLoop",
    namespace: "staging",
    service: "notification-worker",
    status: "remediating",
    started_at: "2026-03-07T11:20:00Z",
    duration_seconds: null,
    timeline: [
      { timestamp: "2026-03-07T11:20:00Z", event: "Pipeline started" },
      { timestamp: "2026-03-07T11:20:10Z", event: "Investigation started" },
      { timestamp: "2026-03-07T11:22:00Z", event: "Root cause identified", details: "Missing config map after recent deploy" },
      { timestamp: "2026-03-07T11:22:15Z", event: "Recommendations generated" },
      { timestamp: "2026-03-07T11:22:30Z", event: "Auto-approved (staging environment)" },
      { timestamp: "2026-03-07T11:22:45Z", event: "Remediation in progress", details: "Restoring config map from last known good state" },
    ],
    recommendations: [
      { id: "rec-006a", action: "restore", target: "notification-worker-config", risk_level: "low", description: "Restore config map from backup" },
    ],
  },
];

// --- Helpers ---

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "--";
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

const STATUS_SORT_ORDER: Record<string, number> = {
  awaiting_approval: 0,
  investigating: 1,
  recommending: 2,
  remediating: 3,
  verifying: 4,
  pending: 5,
  completed: 6,
  failed: 7,
};

// --- Component ---

export default function PipelineRuns() {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortField, setSortField] = useState<"status" | "started_at">("started_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const runs = MOCK_RUNS;

  // Stats
  const stats = useMemo(() => {
    const total = runs.length;
    const active = runs.filter((r) =>
      ["investigating", "recommending", "awaiting_approval", "remediating", "verifying", "pending"].includes(r.status)
    ).length;
    const completed = runs.filter((r) => r.status === "completed").length;
    const failed = runs.filter((r) => r.status === "failed").length;
    return { total, active, completed, failed };
  }, [runs]);

  // Filter + sort
  const filtered = useMemo(() => {
    let result = runs;
    if (statusFilter !== "all") {
      result = result.filter((r) => r.status === statusFilter);
    }
    result = [...result].sort((a, b) => {
      if (sortField === "status") {
        const aOrder = STATUS_SORT_ORDER[a.status] ?? 99;
        const bOrder = STATUS_SORT_ORDER[b.status] ?? 99;
        return sortDir === "asc" ? aOrder - bOrder : bOrder - aOrder;
      }
      const aTime = new Date(a.started_at).getTime();
      const bTime = new Date(b.started_at).getTime();
      return sortDir === "asc" ? aTime - bTime : bTime - aTime;
    });
    return result;
  }, [runs, statusFilter, sortField, sortDir]);

  function handleSort(field: "status" | "started_at") {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  function handleApprove(runId: string) {
    // In a real implementation this would call POST /api/v1/pipeline/runs/{run_id}/approve
    alert(`Approval sent for run ${runId}. (Mock — no API call made.)`);
  }

  function toggleExpand(runId: string) {
    setExpandedRunId((prev) => (prev === runId ? null : runId));
  }

  const sortIndicator = (field: string) => {
    if (sortField !== field) return null;
    return <span className="ml-1 text-gray-400">{sortDir === "asc" ? "\u2191" : "\u2193"}</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Pipeline Runs</h1>
        <button
          onClick={() => alert("New Pipeline Run dialog would open here. (Mock)")}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 transition-colors"
        >
          <Play className="h-4 w-4" />
          New Pipeline Run
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Total Runs" value={stats.total} icon={<Activity className="h-5 w-5" />} />
        <MetricCard label="Active" value={stats.active} icon={<Clock className="h-5 w-5" />} />
        <MetricCard label="Completed" value={stats.completed} icon={<CheckCircle className="h-5 w-5" />} />
        <MetricCard label="Failed" value={stats.failed} icon={<XCircle className="h-5 w-5" />} />
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500">Filter:</span>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="investigating">Investigating</option>
          <option value="recommending">Recommending</option>
          <option value="awaiting_approval">Awaiting Approval</option>
          <option value="remediating">Remediating</option>
          <option value="verifying">Verifying</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center">
          <p className="text-sm text-gray-500">No pipeline runs match your filters.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900">
                <th className="w-8 px-4 py-3" />
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 select-none"
                  onClick={() => handleSort("status")}
                >
                  Status{sortIndicator("status")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Alert Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Namespace
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 select-none"
                  onClick={() => handleSort("started_at")}
                >
                  Started{sortIndicator("started_at")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Duration
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 bg-gray-950">
              {filtered.map((run) => {
                const isExpanded = expandedRunId === run.id;
                return (
                  <RunRow
                    key={run.id}
                    run={run}
                    isExpanded={isExpanded}
                    onToggle={() => toggleExpand(run.id)}
                    onApprove={() => handleApprove(run.id)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Row sub-component ---

function RunRow({
  run,
  isExpanded,
  onToggle,
  onApprove,
}: {
  run: PipelineRun;
  isExpanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
}) {
  const colCount = 7;

  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer transition-colors hover:bg-gray-900"
      >
        <td className="px-4 py-3 text-gray-500">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={run.status} />
        </td>
        <td className="px-4 py-3 font-medium text-gray-100">{run.alert_name}</td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs text-gray-400">{run.namespace}/{run.service}</span>
        </td>
        <td className="px-4 py-3 text-xs text-gray-400">
          {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
        </td>
        <td className="px-4 py-3 text-xs text-gray-400">
          {formatDuration(run.duration_seconds)}
        </td>
        <td className="px-4 py-3">
          {run.status === "awaiting_approval" && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onApprove();
              }}
              className="rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-500 transition-colors"
            >
              Approve
            </button>
          )}
        </td>
      </tr>

      {/* Expanded detail row */}
      {isExpanded && (
        <tr>
          <td colSpan={colCount} className="bg-gray-900 px-6 py-4">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Timeline */}
              <div>
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-gray-500">
                  Timeline
                </h3>
                <ol className="space-y-2 border-l border-gray-700 pl-4">
                  {run.timeline.map((entry, i) => (
                    <li key={i} className="relative">
                      <div className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-gray-600" />
                      <p className="text-sm text-gray-200">{entry.event}</p>
                      {entry.details && (
                        <p className="text-xs text-gray-500">{entry.details}</p>
                      )}
                      <p className="text-xs text-gray-600">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </p>
                    </li>
                  ))}
                </ol>
              </div>

              {/* Recommendations */}
              <div>
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-gray-500">
                  Recommendations
                </h3>
                {run.recommendations.length === 0 ? (
                  <p className="text-sm text-gray-500">No recommendations yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {run.recommendations.map((rec) => (
                      <li
                        key={rec.id}
                        className="rounded-lg border border-gray-800 bg-gray-950 p-3"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-medium text-gray-200">
                            {rec.action}
                          </span>
                          <StatusBadge status={rec.risk_level} />
                        </div>
                        <p className="mt-1 text-xs text-gray-400">
                          Target: <span className="font-mono">{rec.target}</span>
                        </p>
                        <p className="mt-1 text-xs text-gray-500">{rec.description}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
