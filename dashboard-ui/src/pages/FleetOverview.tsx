import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";
import {
  Search,
  Wrench,
  ShieldCheck,
  DollarSign,
  BookOpen,
  Eye,
  Activity,
  CheckCircle,
  Clock,
  Bot,
} from "lucide-react";
import { get } from "../api/client";
import type {
  AnalyticsSummary,
  Agent,
  AgentType,
  AgentStatus,
  Investigation,
  Remediation,
} from "../api/types";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import DataTable, { type Column } from "../components/DataTable";
import LoadingSpinner from "../components/LoadingSpinner";
import LiveIndicator from "../components/LiveIndicator";
import { useConnectionStatus } from "../hooks/useRealtimeUpdates";

// ── Helpers ──────────────────────────────────────────────────────────

function formatMTTR(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

const AGENT_TYPE_ICONS: Record<AgentType, React.ReactNode> = {
  investigation: <Search className="h-5 w-5" />,
  remediation: <Wrench className="h-5 w-5" />,
  security: <ShieldCheck className="h-5 w-5" />,
  cost: <DollarSign className="h-5 w-5" />,
  learning: <BookOpen className="h-5 w-5" />,
  supervisor: <Eye className="h-5 w-5" />,
};

const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  investigation: "Investigation",
  remediation: "Remediation",
  security: "Security",
  cost: "Cost",
  learning: "Learning",
  supervisor: "Supervisor",
};

function statusBorderColor(status: AgentStatus): string {
  switch (status) {
    case "idle":
    case "running":
      return "border-green-500/40";
    case "error":
      return "border-red-500/40";
    case "offline":
      return "border-gray-600";
    default:
      return "border-gray-800";
  }
}

// ── Investigation table columns ──────────────────────────────────────

const investigationColumns: Column<Investigation>[] = [
  {
    key: "alert_name",
    header: "Alert Name",
    render: (row) => (
      <span className="font-medium text-gray-100">{row.alert_name}</span>
    ),
  },
  {
    key: "severity",
    header: "Severity",
    render: (row) => <StatusBadge status={row.severity} />,
  },
  {
    key: "resource_id",
    header: "Resource",
    render: (row) => (
      <span className="text-gray-400">{row.resource_id}</span>
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge status={row.status} />,
  },
  {
    key: "started_at",
    header: "Started",
    render: (row) => (
      <span className="text-gray-500">
        {formatDistanceToNow(new Date(row.started_at), { addSuffix: true })}
      </span>
    ),
  },
];

// ── Remediation table columns ────────────────────────────────────────

const remediationColumns: Column<Remediation>[] = [
  {
    key: "action_type",
    header: "Action Type",
    render: (row) => (
      <span className="font-medium text-gray-100">{row.action_type}</span>
    ),
  },
  {
    key: "target_resource",
    header: "Target",
    render: (row) => (
      <span className="text-gray-400">{row.target_resource}</span>
    ),
  },
  {
    key: "environment",
    header: "Environment",
    render: (row) => (
      <span className="text-gray-400">{row.environment}</span>
    ),
  },
  {
    key: "risk_level",
    header: "Risk",
    render: (row) => <StatusBadge status={row.risk_level} />,
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge status={row.status} />,
  },
  {
    key: "started_at",
    header: "Started",
    render: (row) => (
      <span className="text-gray-500">
        {formatDistanceToNow(new Date(row.started_at), { addSuffix: true })}
      </span>
    ),
  },
];

// ── Component ────────────────────────────────────────────────────────

export default function FleetOverview() {
  const navigate = useNavigate();
  const connectionStatus = useConnectionStatus();
  const isLive = connectionStatus === "connected";

  const analyticsQuery = useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: () => get<AnalyticsSummary>("/analytics/summary"),
  });

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: () => get<Agent[]>("/agents/"),
  });

  const investigationsQuery = useQuery({
    queryKey: ["investigations", "recent"],
    queryFn: () => get<Investigation[]>("/investigations/?limit=5"),
  });

  const remediationsQuery = useQuery({
    queryKey: ["remediations", "recent"],
    queryFn: () => get<Remediation[]>("/remediations/?limit=5"),
  });

  const isLoading =
    analyticsQuery.isLoading ||
    agentsQuery.isLoading ||
    investigationsQuery.isLoading ||
    remediationsQuery.isLoading;

  const hasError =
    analyticsQuery.isError ||
    agentsQuery.isError ||
    investigationsQuery.isError ||
    remediationsQuery.isError;

  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  if (hasError) {
    return (
      <div className="mt-32 rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
        <p className="text-sm text-red-400">
          Failed to load dashboard data. Please try refreshing the page.
        </p>
      </div>
    );
  }

  const analytics = analyticsQuery.data!;
  const agents = agentsQuery.data!;
  const investigations = investigationsQuery.data!;
  const remediations = remediationsQuery.data!;

  const activeAgents = agents.filter(
    (a) => a.status === "running" || a.status === "idle",
  ).length;

  // Build a map of one agent per type for the health grid.
  // If multiple agents exist for a type, pick the one that is running or
  // most recently active.
  const agentByType = new Map<AgentType, Agent>();
  for (const agent of agents) {
    const existing = agentByType.get(agent.agent_type);
    if (
      !existing ||
      agent.status === "running" ||
      (agent.last_heartbeat &&
        (!existing.last_heartbeat ||
          agent.last_heartbeat > existing.last_heartbeat))
    ) {
      agentByType.set(agent.agent_type, agent);
    }
  }

  const agentTypes: AgentType[] = [
    "investigation",
    "remediation",
    "security",
    "cost",
    "learning",
    "supervisor",
  ];

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-gray-100">Fleet Overview</h1>
          <LiveIndicator active={isLive} />
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Real-time status of agents, investigations, and remediations
        </p>
      </div>

      {/* Section 1 — Key Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Investigations"
          value={analytics.total_investigations}
          icon={<Activity className="h-5 w-5" />}
        />
        <MetricCard
          label="Auto-Resolved"
          value={`${analytics.auto_resolved_percent.toFixed(1)}%`}
          icon={<CheckCircle className="h-5 w-5" />}
        />
        <MetricCard
          label="MTTR"
          value={formatMTTR(analytics.mean_time_to_resolve_seconds)}
          icon={<Clock className="h-5 w-5" />}
        />
        <MetricCard
          label="Active Agents"
          value={activeAgents}
          icon={<Bot className="h-5 w-5" />}
        />
      </div>

      {/* Section 2 — Agent Health Grid */}
      <div>
        <div className="mb-4 flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-100">
            Agent Health
          </h2>
          <LiveIndicator active={isLive} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agentTypes.map((type) => {
            const agent = agentByType.get(type);
            const status: AgentStatus = agent?.status ?? "offline";
            return (
              <div
                key={type}
                className={clsx(
                  "rounded-xl border bg-gray-900 p-5 transition-colors",
                  statusBorderColor(status),
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-gray-400">
                      {AGENT_TYPE_ICONS[type]}
                    </div>
                    <span className="font-medium text-gray-100">
                      {AGENT_TYPE_LABELS[type]}
                    </span>
                    {status === "running" && <LiveIndicator active={isLive} />}
                  </div>
                  <StatusBadge status={status} />
                </div>
                <p className="mt-3 text-xs text-gray-500">
                  {agent?.last_heartbeat
                    ? `Last heartbeat ${formatDistanceToNow(new Date(agent.last_heartbeat), { addSuffix: true })}`
                    : "No heartbeat recorded"}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3 — Recent Investigations */}
      <div>
        <div className="mb-4 flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-100">
            Recent Investigations
          </h2>
          <LiveIndicator active={isLive} />
        </div>
        <DataTable<Investigation>
          columns={investigationColumns}
          data={investigations}
          keyExtractor={(row) => row.id}
          onRowClick={(row) => navigate(`/investigations/${row.id}`)}
          emptyMessage="No recent investigations"
        />
      </div>

      {/* Section 4 — Recent Remediations */}
      <div>
        <div className="mb-4 flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-100">
            Recent Remediations
          </h2>
          <LiveIndicator active={isLive} />
        </div>
        <DataTable<Remediation>
          columns={remediationColumns}
          data={remediations}
          keyExtractor={(row) => row.id}
          onRowClick={(row) => navigate(`/remediations/${row.id}`)}
          emptyMessage="No recent remediations"
        />
      </div>
    </div>
  );
}
