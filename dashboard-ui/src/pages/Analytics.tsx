import { useQuery } from "@tanstack/react-query";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Activity, CheckCircle, Clock, Bot, TrendingUp } from "lucide-react";
import { get } from "../api/client";
import type { AnalyticsSummary, Agent } from "../api/types";
import MetricCard from "../components/MetricCard";
import LoadingSpinner from "../components/LoadingSpinner";

// ── Helpers ──────────────────────────────────────────────────────────

function formatMTTR(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

// Consistent status colors across both pie charts
const STATUS_COLORS: Record<string, string> = {
  completed: "#22c55e",
  in_progress: "#eab308",
  failed: "#ef4444",
  pending: "#3b82f6",
  pending_approval: "#6366f1",
  approved: "#10b981",
  executing: "#f59e0b",
  rolled_back: "#f87171",
};

const FALLBACK_COLOR = "#6b7280";

interface PieEntry {
  name: string;
  value: number;
}

function recordToPieData(record: Record<string, number>): PieEntry[] {
  return Object.entries(record)
    .filter(([, count]) => count > 0)
    .map(([status, count]) => ({
      name: status.replace(/_/g, " "),
      value: count,
    }));
}

function colorForStatus(name: string): string {
  // The name displayed in the chart has spaces; convert back to underscore for lookup
  const key = name.replace(/ /g, "_");
  return STATUS_COLORS[key] ?? FALLBACK_COLOR;
}

// Custom tooltip for the dark theme
function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number }>;
}) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0];
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-xs shadow-lg">
      <span className="text-gray-300">{name}: </span>
      <span className="font-semibold text-gray-100">{value}</span>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────

export default function Analytics() {
  const analyticsQuery = useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: () => get<AnalyticsSummary>("/analytics/summary"),
  });

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: () => get<Agent[]>("/agents/"),
  });

  if (analyticsQuery.isLoading || agentsQuery.isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  if (analyticsQuery.isError || agentsQuery.isError) {
    return (
      <div className="mt-32 rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
        <p className="text-sm text-red-400">
          Failed to load analytics data. Please try refreshing the page.
        </p>
      </div>
    );
  }

  const analytics = analyticsQuery.data!;
  const agents = agentsQuery.data!;

  const activeAgents = agents.filter(
    (a) => a.status === "running" || a.status === "idle",
  ).length;

  const investigationPieData = recordToPieData(
    analytics.investigations_by_status,
  );
  const remediationPieData = recordToPieData(
    analytics.remediations_by_status,
  );

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Analytics</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform performance and resolution metrics
        </p>
      </div>

      {/* Section 1 — Summary Metrics */}
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

      {/* Section 2 + 3 — Pie Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Investigations by Status */}
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="mb-4 text-lg font-semibold text-gray-100">
            Investigations by Status
          </h2>
          {investigationPieData.length === 0 ? (
            <p className="py-12 text-center text-sm text-gray-500">
              No investigation data yet
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={investigationPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  nameKey="name"
                  stroke="none"
                >
                  {investigationPieData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={colorForStatus(entry.name)}
                    />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: "12px", color: "#9ca3af" }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Remediations by Status */}
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="mb-4 text-lg font-semibold text-gray-100">
            Remediations by Status
          </h2>
          {remediationPieData.length === 0 ? (
            <p className="py-12 text-center text-sm text-gray-500">
              No remediation data yet
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={remediationPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  nameKey="name"
                  stroke="none"
                >
                  {remediationPieData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={colorForStatus(entry.name)}
                    />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: "12px", color: "#9ca3af" }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Section 4 — Resolution Timeline (Placeholder) */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-100">
            Resolution Trend
          </h2>
        </div>
        <p className="mt-6 py-12 text-center text-sm text-gray-500">
          Coming soon &mdash; time series data will be displayed here once
          sufficient historical data has been collected.
        </p>
      </div>
    </div>
  );
}
