import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { DollarSign, TrendingUp, AlertTriangle, Receipt, ServerCrash } from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import { get, ApiError } from "../api/client";
import type { CostSummary, CostAnomaly } from "../api/types";
import type { Column } from "../components/DataTable";
import MetricCard from "../components/MetricCard";
import DataTable from "../components/DataTable";
import LoadingSpinner from "../components/LoadingSpinner";

export default function Cost() {
  const {
    data: summary,
    isLoading,
    error,
  } = useQuery<CostSummary>({
    queryKey: ["cost", "summary"],
    queryFn: () => get<CostSummary>("/cost/summary"),
    retry: (failureCount, err) => {
      // Don't retry 404s — billing may not be configured
      if (err instanceof ApiError && err.status === 404) return false;
      return failureCount < 3;
    },
  });

  const isNotConfigured =
    error instanceof ApiError && (error.status === 404 || error.status === 501);

  // ── Anomaly table columns ──────────────────────────────────────────
  const anomalyColumns: Column<CostAnomaly>[] = [
    {
      key: "service",
      header: "Service",
      render: (row) => <span className="font-medium text-gray-200">{row.service}</span>,
    },
    {
      key: "expected",
      header: "Expected",
      render: (row) => `$${row.expected.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
    },
    {
      key: "actual",
      header: "Actual",
      render: (row) => `$${row.actual.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
    },
    {
      key: "deviation_percent",
      header: "Deviation %",
      render: (row) => (
        <span
          className={clsx(
            "font-semibold tabular-nums",
            row.deviation_percent > 50 ? "text-red-400" : "text-yellow-400",
          )}
        >
          +{row.deviation_percent.toFixed(1)}%
        </span>
      ),
    },
    {
      key: "detected_at",
      header: "Detected At",
      render: (row) => format(new Date(row.detected_at), "MMM d, HH:mm"),
    },
  ];

  // ── Custom recharts tooltip ────────────────────────────────────────
  function ChartTooltip({
    active,
    payload,
    label,
  }: {
    active?: boolean;
    payload?: Array<{ value: number }>;
    label?: string;
  }) {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-xs shadow-lg">
        <p className="font-medium text-gray-200">{label}</p>
        <p className="text-brand-400">
          ${payload[0].value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
        </p>
      </div>
    );
  }

  // ── Loading state ──────────────────────────────────────────────────
  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  // ── Not configured / error state ───────────────────────────────────
  if (isNotConfigured || (!summary && error)) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-100">Cost Analysis</h1>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center">
          <ServerCrash className="mx-auto h-12 w-12 text-gray-600" />
          <h2 className="mt-4 text-lg font-semibold text-gray-200">
            Cost analysis not configured
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
            To enable cost tracking, connect your cloud billing accounts in the Settings page.
            ShieldOps supports AWS Cost Explorer, GCP Billing Export, and Azure Cost Management.
          </p>
          <div className="mt-6 rounded-lg border border-gray-800 bg-gray-950 p-4 text-left">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
              Quick setup
            </p>
            <ol className="space-y-1 text-sm text-gray-400">
              <li>1. Navigate to <span className="text-brand-400">Settings &rarr; Integrations</span></li>
              <li>2. Add your cloud provider billing credentials</li>
              <li>3. Wait for the first cost sync (typically 5-10 minutes)</li>
            </ol>
          </div>
        </div>
      </div>
    );
  }

  // Guard for TypeScript — if we reach here, summary is defined
  if (!summary) return null;

  const chartData = [...summary.top_services]
    .sort((a, b) => b.monthly_cost - a.monthly_cost)
    .slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Header */}
      <h1 className="text-2xl font-bold text-gray-100">Cost Analysis</h1>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Daily Spend"
          value={`$${summary.total_daily.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          icon={<DollarSign className="h-5 w-5" />}
        />
        <MetricCard
          label="Monthly Spend"
          value={`$${summary.total_monthly.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          icon={<Receipt className="h-5 w-5" />}
        />
        <MetricCard
          label="Cost Change"
          value={`${summary.change_percent >= 0 ? "+" : ""}${summary.change_percent.toFixed(1)}%`}
          change={summary.change_percent}
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <MetricCard
          label="Anomalies Detected"
          value={summary.anomalies.length}
          icon={<AlertTriangle className="h-5 w-5" />}
        />
      </div>

      {/* Cost by Service bar chart */}
      {chartData.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-100">Cost by Service</h2>
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <ResponsiveContainer width="100%" height={Math.max(chartData.length * 40, 200)}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                <XAxis
                  type="number"
                  tick={{ fill: "#9ca3af", fontSize: 12 }}
                  axisLine={{ stroke: "#374151" }}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v.toLocaleString()}`}
                />
                <YAxis
                  type="category"
                  dataKey="service"
                  width={140}
                  tick={{ fill: "#d1d5db", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(99,102,241,0.08)" }} />
                <Bar dataKey="monthly_cost" radius={[0, 4, 4, 0]} barSize={24}>
                  {chartData.map((entry) => (
                    <Cell key={entry.service} fill="#6366f1" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Cost Anomalies */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-100">Cost Anomalies</h2>
        <DataTable
          columns={anomalyColumns}
          data={summary.anomalies}
          keyExtractor={(row) => `${row.service}-${row.detected_at}`}
          emptyMessage="No cost anomalies detected. Your spending is within normal ranges."
        />
      </section>
    </div>
  );
}
