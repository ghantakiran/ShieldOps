import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from "recharts";
import {
  Activity,
  CheckCircle,
  Clock,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import clsx from "clsx";
import { get } from "../api/client";
import type {
  AgentPerformanceResponse,
  AgentPerformanceAgent,
  HeatmapCell,
} from "../api/types";
import MetricCard from "../components/MetricCard";
import LoadingSpinner from "../components/LoadingSpinner";

// ── Constants ────────────────────────────────────────────────────

const PERIODS = [
  { label: "1h", value: "1h" },
  { label: "6h", value: "6h" },
  { label: "24h", value: "24h" },
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" },
] as const;

const AGENT_TYPES = [
  "investigation",
  "remediation",
  "security",
  "learning",
] as const;

const AGENT_TYPE_COLORS: Record<string, string> = {
  investigation: "#3b82f6",
  remediation: "#22c55e",
  security: "#f59e0b",
  learning: "#a855f7",
};

const HEATMAP_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type SortField =
  | "agent_type"
  | "total_executions"
  | "success_rate"
  | "avg_duration_seconds"
  | "p95_duration"
  | "error_count";
type SortDir = "asc" | "desc";

// ── Helpers ──────────────────────────────────────────────────────

function successRateColor(rate: number): string {
  if (rate >= 0.9) return "text-emerald-400";
  if (rate >= 0.7) return "text-yellow-400";
  return "text-red-400";
}

function successRateBarColor(rate: number): string {
  if (rate >= 0.9) return "bg-emerald-500";
  if (rate >= 0.7) return "bg-yellow-500";
  return "bg-red-500";
}

function heatmapCellColor(count: number, maxCount: number): string {
  if (maxCount === 0 || count === 0) return "bg-gray-800";
  const ratio = count / maxCount;
  if (ratio > 0.75) return "bg-blue-500";
  if (ratio > 0.5) return "bg-blue-600/70";
  if (ratio > 0.25) return "bg-blue-700/50";
  return "bg-blue-900/40";
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ── Execution Trend Chart ────────────────────────────────────────

function ExecutionTrendChart({
  agents,
}: {
  agents: AgentPerformanceAgent[];
}) {
  // Merge all agents' trend data by date
  const mergedData = useMemo(() => {
    const dateMap = new Map<string, Record<string, number>>();

    for (const agent of agents) {
      for (const point of agent.trend) {
        const existing = dateMap.get(point.date) ?? { date: 0 };
        existing[agent.agent_type] =
          (existing[agent.agent_type] ?? 0) + point.executions;
        dateMap.set(point.date, existing);
      }
    }

    return Array.from(dateMap.entries()).map(([date, values]) => ({
      date,
      ...values,
    }));
  }, [agents]);

  if (mergedData.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h2 className="mb-4 text-lg font-semibold text-gray-100">
          Execution Trends
        </h2>
        <p className="py-12 text-center text-sm text-gray-500">
          No trend data available for this period.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Activity className="h-5 w-5 text-blue-400" />
        <h2 className="text-lg font-semibold text-gray-100">
          Execution Trends
        </h2>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={mergedData}
          margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
        >
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
              value: "Executions",
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
          />
          <Legend wrapperStyle={{ fontSize: "12px", color: "#9ca3af" }} />
          {agents.map((agent) => (
            <Line
              key={agent.agent_type}
              type="monotone"
              dataKey={agent.agent_type}
              name={capitalize(agent.agent_type)}
              stroke={AGENT_TYPE_COLORS[agent.agent_type] ?? "#6b7280"}
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Success Rate Bar Chart ───────────────────────────────────────

function SuccessRateChart({
  agents,
}: {
  agents: AgentPerformanceAgent[];
}) {
  const chartData = agents.map((a) => ({
    name: capitalize(a.agent_type),
    rate: Math.round(a.success_rate * 100),
    agentType: a.agent_type,
  }));

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center gap-2">
        <CheckCircle className="h-5 w-5 text-emerald-400" />
        <h2 className="text-lg font-semibold text-gray-100">
          Success Rate by Agent Type
        </h2>
      </div>
      {chartData.length === 0 ? (
        <p className="py-12 text-center text-sm text-gray-500">
          No data available.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
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
              formatter={(value: number) => [`${value}%`, "Success Rate"]}
            />
            <Bar dataKey="rate" radius={[4, 4, 0, 0]} maxBarSize={60}>
              {chartData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={AGENT_TYPE_COLORS[entry.agentType] ?? "#6b7280"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ── Hourly Activity Heatmap ──────────────────────────────────────

function ActivityHeatmap({ heatmap }: { heatmap: HeatmapCell[] }) {
  const maxCount = useMemo(
    () => Math.max(1, ...heatmap.map((c) => c.count)),
    [heatmap],
  );

  // Build lookup: day -> hour -> count
  const lookup = useMemo(() => {
    const map = new Map<string, Map<number, number>>();
    for (const cell of heatmap) {
      if (!map.has(cell.day)) map.set(cell.day, new Map());
      map.get(cell.day)!.set(cell.hour, cell.count);
    }
    return map;
  }, [heatmap]);

  if (heatmap.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-violet-400" />
          <h2 className="text-lg font-semibold text-gray-100">
            Hourly Activity
          </h2>
        </div>
        <p className="py-12 text-center text-sm text-gray-500">
          No activity data available.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Clock className="h-5 w-5 text-violet-400" />
        <h2 className="text-lg font-semibold text-gray-100">
          Hourly Activity
        </h2>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[640px]">
          {/* Hour labels */}
          <div className="mb-1 flex pl-10">
            {Array.from({ length: 24 }, (_, h) => (
              <div
                key={h}
                className="flex-1 text-center text-[10px] text-gray-500"
              >
                {h % 3 === 0 ? `${h}` : ""}
              </div>
            ))}
          </div>
          {/* Grid rows */}
          {HEATMAP_DAYS.map((day) => (
            <div key={day} className="mb-0.5 flex items-center">
              <span className="w-10 text-xs text-gray-500">{day}</span>
              <div className="flex flex-1 gap-0.5">
                {Array.from({ length: 24 }, (_, h) => {
                  const count = lookup.get(day)?.get(h) ?? 0;
                  return (
                    <div
                      key={h}
                      className={clsx(
                        "flex-1 rounded-sm transition-colors",
                        heatmapCellColor(count, maxCount),
                      )}
                      style={{ aspectRatio: "1" }}
                      title={`${day} ${h}:00 - ${count} executions`}
                    />
                  );
                })}
              </div>
            </div>
          ))}
          {/* Legend */}
          <div className="mt-3 flex items-center justify-end gap-1 text-[10px] text-gray-500">
            <span>Less</span>
            <div className="h-3 w-3 rounded-sm bg-gray-800" />
            <div className="h-3 w-3 rounded-sm bg-blue-900/40" />
            <div className="h-3 w-3 rounded-sm bg-blue-700/50" />
            <div className="h-3 w-3 rounded-sm bg-blue-600/70" />
            <div className="h-3 w-3 rounded-sm bg-blue-500" />
            <span>More</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Agent Breakdown Table ────────────────────────────────────────

function AgentTable({ agents }: { agents: AgentPerformanceAgent[] }) {
  const [sortField, setSortField] = useState<SortField>("total_executions");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const copy = [...agents];
    copy.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }
      const diff = (aVal as number) - (bVal as number);
      return sortDir === "asc" ? diff : -diff;
    });
    return copy;
  }, [agents, sortField, sortDir]);

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return null;
    return sortDir === "asc" ? (
      <ChevronUp className="ml-1 inline h-3 w-3" />
    ) : (
      <ChevronDown className="ml-1 inline h-3 w-3" />
    );
  }

  const headerClass =
    "cursor-pointer select-none px-4 py-3 text-left text-xs " +
    "font-medium uppercase tracking-wider text-gray-400 " +
    "hover:text-gray-200 transition-colors";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th
                className={headerClass}
                onClick={() => handleSort("agent_type")}
              >
                Agent Type
                <SortIcon field="agent_type" />
              </th>
              <th
                className={headerClass}
                onClick={() => handleSort("total_executions")}
              >
                Executions
                <SortIcon field="total_executions" />
              </th>
              <th
                className={headerClass}
                onClick={() => handleSort("success_rate")}
              >
                Success Rate
                <SortIcon field="success_rate" />
              </th>
              <th
                className={headerClass}
                onClick={() => handleSort("avg_duration_seconds")}
              >
                Avg Duration
                <SortIcon field="avg_duration_seconds" />
              </th>
              <th
                className={headerClass}
                onClick={() => handleSort("p95_duration")}
              >
                P95 Duration
                <SortIcon field="p95_duration" />
              </th>
              <th
                className={headerClass}
                onClick={() => handleSort("error_count")}
              >
                Errors
                <SortIcon field="error_count" />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {sorted.map((agent) => {
              const pct = Math.round(agent.success_rate * 100);
              return (
                <tr
                  key={agent.agent_type}
                  className="transition-colors hover:bg-gray-800/40"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2.5 w-2.5 rounded-full"
                        style={{
                          backgroundColor:
                            AGENT_TYPE_COLORS[agent.agent_type] ?? "#6b7280",
                        }}
                      />
                      <span className="text-sm font-medium text-gray-100">
                        {capitalize(agent.agent_type)}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {agent.total_executions.toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-gray-700">
                        <div
                          className={clsx(
                            "h-full rounded-full transition-all",
                            successRateBarColor(agent.success_rate),
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span
                        className={clsx(
                          "text-sm font-medium",
                          successRateColor(agent.success_rate),
                        )}
                      >
                        {pct}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {agent.avg_duration_seconds.toFixed(1)}s
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {agent.p95_duration.toFixed(1)}s
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        "text-sm font-medium",
                        agent.error_count > 0
                          ? "text-red-400"
                          : "text-gray-500",
                      )}
                    >
                      {agent.error_count}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main Page Component ──────────────────────────────────────────

export default function AgentPerformance() {
  const [period, setPeriod] = useState("7d");
  const [agentTypeFilter, setAgentTypeFilter] = useState<string>("");

  const queryParams = new URLSearchParams({ period });
  if (agentTypeFilter) queryParams.set("agent_type", agentTypeFilter);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "agent-performance", period, agentTypeFilter],
    queryFn: () =>
      get<AgentPerformanceResponse>(
        `/analytics/agent-performance?${queryParams.toString()}`,
      ),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            Agent Performance
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Detailed execution metrics, success rates, and latency across all
            agent types
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Agent type filter */}
          <select
            value={agentTypeFilter}
            onChange={(e) => setAgentTypeFilter(e.target.value)}
            className={clsx(
              "rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5",
              "text-sm text-gray-300 outline-none",
              "focus:border-brand-500 focus:ring-1 focus:ring-brand-500",
            )}
          >
            <option value="">All Agents</option>
            {AGENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {capitalize(t)}
              </option>
            ))}
          </select>

          {/* Period pills */}
          <div className="flex rounded-lg border border-gray-700 bg-gray-800">
            {PERIODS.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => setPeriod(value)}
                className={clsx(
                  "px-3 py-1.5 text-xs font-medium transition-colors",
                  "first:rounded-l-lg last:rounded-r-lg",
                  period === value
                    ? "bg-brand-600 text-white"
                    : "text-gray-400 hover:bg-gray-700 hover:text-gray-200",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && <LoadingSpinner size="lg" className="mt-32" />}

      {/* Error state */}
      {isError && (
        <div className="mt-16 rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
          <p className="text-sm text-red-400">
            Failed to load agent performance data. Please try refreshing.
          </p>
        </div>
      )}

      {/* Data loaded */}
      {data && !isLoading && !isError && (
        <>
          {/* Metric cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total Executions"
              value={data.summary.total_executions.toLocaleString()}
              icon={<Activity className="h-5 w-5" />}
            />
            <MetricCard
              label="Avg Success Rate"
              value={`${Math.round(data.summary.avg_success_rate * 100)}%`}
              icon={<CheckCircle className="h-5 w-5" />}
            />
            <MetricCard
              label="Avg Duration"
              value={`${data.summary.avg_duration_seconds.toFixed(1)}s`}
              icon={<Clock className="h-5 w-5" />}
            />
            <MetricCard
              label="Total Errors"
              value={data.summary.total_errors}
              icon={<AlertTriangle className="h-5 w-5" />}
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ExecutionTrendChart agents={data.agents} />
            <SuccessRateChart agents={data.agents} />
          </div>

          {/* Heatmap */}
          <ActivityHeatmap heatmap={data.hourly_heatmap} />

          {/* Breakdown table */}
          <div>
            <h2 className="mb-3 text-lg font-semibold text-gray-100">
              Agent Breakdown
            </h2>
            <AgentTable agents={data.agents} />
          </div>
        </>
      )}
    </div>
  );
}
