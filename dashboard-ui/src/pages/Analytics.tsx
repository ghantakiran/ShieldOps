import { useQuery } from "@tanstack/react-query";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import { Activity, CheckCircle, Clock, Bot } from "lucide-react";
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

// ── Analytics endpoint response types ────────────────────────────────

interface MttrDataPoint {
  date: string | null;
  avg_duration_ms: number;
  count: number;
}

interface MttrTrendResponse {
  period: string;
  data_points: MttrDataPoint[];
  current_mttr_minutes: number;
}

interface ResolutionRateResponse {
  period: string;
  automated_rate: number;
  manual_rate: number;
  total_incidents: number;
}

interface AgentAccuracyResponse {
  period: string;
  accuracy: number;
  total_investigations: number;
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

// ── Trend chart sub-components ────────────────────────────────────────

/** MTTR Trend — line chart showing daily average resolution time. */
function MttrTrendChart() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "mttr"],
    queryFn: () => get<MttrTrendResponse>("/analytics/mttr"),
  });

  const chartData =
    data?.data_points.map((dp) => ({
      date: dp.date ? new Date(dp.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "",
      mttr: Math.round(dp.avg_duration_ms / 60_000), // convert ms to minutes
      count: dp.count,
    })) ?? [];

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-100">MTTR Trend</h2>
        </div>
        {data && data.current_mttr_minutes > 0 && (
          <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
            Current: {data.current_mttr_minutes.toFixed(1)}m
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner size="sm" />
        </div>
      )}

      {isError && (
        <p className="py-12 text-center text-sm text-red-400">
          Failed to load MTTR trend data.
        </p>
      )}

      {!isLoading && !isError && chartData.length === 0 && (
        <p className="py-12 text-center text-sm text-gray-500">
          No MTTR data available yet. Trends will appear once remediations complete.
        </p>
      )}

      {!isLoading && !isError && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              stroke="#4b5563"
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              stroke="#4b5563"
              label={{
                value: "Minutes",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 11, fill: "#9ca3af" },
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                borderRadius: "0.5rem",
                fontSize: "12px",
              }}
              labelStyle={{ color: "#9ca3af" }}
              itemStyle={{ color: "#e5e7eb" }}
              formatter={(value: number) => [`${value}m`, "MTTR"]}
            />
            <Line
              type="monotone"
              dataKey="mttr"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: "#3b82f6", r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

/** Resolution Rate — bar chart showing automated vs manual resolution. */
function ResolutionRateChart() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "resolution-rate"],
    queryFn: () => get<ResolutionRateResponse>("/analytics/resolution-rate"),
  });

  const chartData = data
    ? [
        { name: "Automated", rate: Math.round(data.automated_rate * 100) },
        { name: "Manual", rate: Math.round(data.manual_rate * 100) },
      ]
    : [];

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CheckCircle className="h-5 w-5 text-emerald-400" />
          <h2 className="text-lg font-semibold text-gray-100">Resolution Rate</h2>
        </div>
        {data && data.total_incidents > 0 && (
          <span className="rounded-full bg-gray-800 px-3 py-1 text-xs font-medium text-gray-400">
            {data.total_incidents} incidents
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner size="sm" />
        </div>
      )}

      {isError && (
        <p className="py-12 text-center text-sm text-red-400">
          Failed to load resolution rate data.
        </p>
      )}

      {!isLoading && !isError && data?.total_incidents === 0 && (
        <p className="py-12 text-center text-sm text-gray-500">
          No resolution data available yet.
        </p>
      )}

      {!isLoading && !isError && data && data.total_incidents > 0 && (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12, fill: "#9ca3af" }}
              stroke="#4b5563"
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              stroke="#4b5563"
              domain={[0, 100]}
              label={{
                value: "%",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 11, fill: "#9ca3af" },
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                borderRadius: "0.5rem",
                fontSize: "12px",
              }}
              labelStyle={{ color: "#9ca3af" }}
              itemStyle={{ color: "#e5e7eb" }}
              formatter={(value: number) => [`${value}%`, "Rate"]}
            />
            <Bar dataKey="rate" radius={[4, 4, 0, 0]} maxBarSize={80}>
              {chartData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.name === "Automated" ? "#22c55e" : "#6b7280"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

/** Agent Accuracy — gauge-like radial display. */
function AgentAccuracyGauge() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "agent-accuracy"],
    queryFn: () => get<AgentAccuracyResponse>("/analytics/agent-accuracy"),
  });

  const pct = data ? Math.round(data.accuracy * 100) : 0;

  // Determine color based on accuracy threshold
  const color =
    pct >= 90 ? "text-emerald-400" : pct >= 70 ? "text-yellow-400" : "text-red-400";
  const ringColor =
    pct >= 90 ? "stroke-emerald-400" : pct >= 70 ? "stroke-yellow-400" : "stroke-red-400";
  const trackColor = "stroke-gray-700";

  // SVG arc for the gauge ring
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Bot className="h-5 w-5 text-violet-400" />
        <h2 className="text-lg font-semibold text-gray-100">Agent Accuracy</h2>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner size="sm" />
        </div>
      )}

      {isError && (
        <p className="py-12 text-center text-sm text-red-400">
          Failed to load agent accuracy data.
        </p>
      )}

      {!isLoading && !isError && data?.total_investigations === 0 && (
        <p className="py-12 text-center text-sm text-gray-500">
          No accuracy data available yet.
        </p>
      )}

      {!isLoading && !isError && data && data.total_investigations > 0 && (
        <div className="flex flex-col items-center justify-center py-4">
          <svg width="180" height="180" viewBox="0 0 180 180" className="-rotate-90">
            <circle
              cx="90"
              cy="90"
              r={radius}
              fill="none"
              className={trackColor}
              strokeWidth="12"
            />
            <circle
              cx="90"
              cy="90"
              r={radius}
              fill="none"
              className={ringColor}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className={`text-4xl font-bold ${color}`}>{pct}%</span>
            <span className="text-xs text-gray-500">
              {data.total_investigations} investigation{data.total_investigations !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
      )}
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

      {/* Section 4 — MTTR Trend (full width) */}
      <MttrTrendChart />

      {/* Section 5 — Resolution Rate + Agent Accuracy (side by side) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ResolutionRateChart />
        <div className="relative">
          <AgentAccuracyGauge />
        </div>
      </div>
    </div>
  );
}
