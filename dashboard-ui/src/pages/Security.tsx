import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Scan,
  AlertTriangle,
  Clock,
  Loader2,
  Shield,
  Bug,
} from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import { get, post } from "../api/client";
import type { SecurityScan, VulnerabilityStats } from "../api/types";
import type { Column } from "../components/DataTable";
import MetricCard from "../components/MetricCard";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

const TABS = ["Overview", "Vulnerabilities", "Compliance", "Scans"] as const;
type TabName = (typeof TABS)[number];

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
};

export default function Security() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabName>("Overview");

  // ── Queries ────────────────────────────────────────────────────────
  const { data: scans = [], isLoading: scansLoading } = useQuery({
    queryKey: ["security", "scans"],
    queryFn: () => get<SecurityScan[]>("/security/scans"),
  });

  const { data: stats } = useQuery({
    queryKey: ["vulnerability-stats"],
    queryFn: () => get<VulnerabilityStats>("/vulnerabilities/stats"),
  });

  const { data: posture } = useQuery({
    queryKey: ["security", "posture"],
    queryFn: () => get<Record<string, unknown>>("/security/posture"),
  });

  const runScan = useMutation({
    mutationFn: () =>
      post<SecurityScan>("/security/scans", { environment: "production" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["security"] });
    },
  });

  // ── Derived metrics ────────────────────────────────────────────────
  const postureScore = (posture?.overall_score as number) ?? 0;
  const criticalCount = stats?.by_severity?.critical ?? 0;
  const totalVulns = stats?.total ?? 0;
  const slaBreaches = stats?.sla_breaches ?? 0;

  // Severity pie data
  const severityData = stats
    ? Object.entries(stats.by_severity).map(([name, value]) => ({
        name,
        value,
        fill: SEVERITY_COLORS[name] ?? "#6b7280",
      }))
    : [];

  // Status bar data
  const statusData = stats
    ? Object.entries(stats.by_status).map(([name, value]) => ({
        name: name.replace(/_/g, " "),
        count: value,
      }))
    : [];

  // ── Table columns ──────────────────────────────────────────────────
  const scanColumns: Column<SecurityScan>[] = [
    {
      key: "scan_type",
      header: "Type",
      render: (row) => <span className="capitalize">{row.scan_type}</span>,
    },
    {
      key: "environment",
      header: "Environment",
      render: (row) => <span className="text-gray-300">{row.environment}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "findings_count",
      header: "Findings",
      render: (row) => row.findings_count,
    },
    {
      key: "critical_count",
      header: "Critical",
      render: (row) => (
        <span className={clsx(row.critical_count > 0 && "font-semibold text-red-400")}>
          {row.critical_count}
        </span>
      ),
    },
    {
      key: "started_at",
      header: "Started",
      render: (row) => format(new Date(row.started_at), "MMM d, HH:mm"),
    },
  ];

  // ── Render ─────────────────────────────────────────────────────────
  if (scansLoading) return <LoadingSpinner size="lg" className="mt-32" />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Security</h1>
        <button
          onClick={() => runScan.mutate()}
          disabled={runScan.isPending}
          className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60"
        >
          {runScan.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Scan className="h-4 w-4" />
          )}
          Run Scan
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-800/50 p-1">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
              activeTab === tab
                ? "bg-gray-700 text-gray-100"
                : "text-gray-400 hover:text-gray-200"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* ── Overview tab ─────────────────────────────────────────────── */}
      {activeTab === "Overview" && (
        <div className="space-y-6">
          {/* Metric cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
            <MetricCard
              label="Security Score"
              value={`${postureScore.toFixed(0)}/100`}
              icon={<Shield className="h-5 w-5" />}
            />
            <MetricCard
              label="Total Vulnerabilities"
              value={totalVulns}
              icon={<Bug className="h-5 w-5" />}
            />
            <MetricCard
              label="Critical"
              value={criticalCount}
              icon={<AlertTriangle className="h-5 w-5" />}
            />
            <MetricCard
              label="SLA Breaches"
              value={slaBreaches}
              icon={<Clock className="h-5 w-5" />}
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Severity Distribution */}
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500">
                Severity Distribution
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={severityData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    innerRadius={55}
                    paddingAngle={2}
                  >
                    {severityData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1f2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-4">
                {severityData.map((d) => (
                  <div key={d.name} className="flex items-center gap-1.5 text-xs">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: d.fill }}
                    />
                    <span className="capitalize text-gray-400">{d.name}</span>
                    <span className="font-medium text-gray-200">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Status Distribution */}
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500">
                Status Distribution
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={statusData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis type="number" stroke="#6b7280" fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#6b7280"
                    fontSize={11}
                    width={85}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1f2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                    }}
                  />
                  <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Quick link to full vulnerability list */}
          <button
            onClick={() => navigate("/vulnerabilities")}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-700 py-3 text-sm text-gray-300 hover:bg-gray-800"
          >
            <Bug className="h-4 w-4" />
            View All Vulnerabilities
          </button>
        </div>
      )}

      {/* ── Vulnerabilities tab ───────────────────────────────────────── */}
      {activeTab === "Vulnerabilities" && (
        <div className="space-y-4">
          <button
            onClick={() => navigate("/vulnerabilities")}
            className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm text-white hover:bg-brand-600"
          >
            <Bug className="h-4 w-4" />
            Open Vulnerability Manager
          </button>
          <p className="text-sm text-gray-400">
            Use the full vulnerability management interface for filtering, assignment, and
            lifecycle tracking.
          </p>
        </div>
      )}

      {/* ── Compliance tab ────────────────────────────────────────────── */}
      {activeTab === "Compliance" && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h3 className="mb-4 text-sm font-semibold uppercase text-gray-500">
            Compliance Frameworks
          </h3>
          <p className="text-sm text-gray-400">
            Compliance data from the most recent full security scan.
          </p>
          {(() => {
            const complianceScores =
              posture && typeof posture === "object" && posture.compliance_scores
                ? (posture.compliance_scores as Record<string, number>)
                : null;
            if (!complianceScores) return null;
            return (
              <div className="mt-4 space-y-3">
                {Object.entries(complianceScores).map(([framework, score]) => (
                  <div key={framework} className="flex items-center gap-4">
                    <span className="w-20 text-sm font-medium uppercase text-gray-300">
                      {framework}
                    </span>
                    <div className="h-3 flex-1 rounded-full bg-gray-800">
                      <div
                        className={clsx(
                          "h-3 rounded-full",
                          score >= 80
                            ? "bg-green-500"
                            : score >= 60
                              ? "bg-yellow-500"
                              : "bg-red-500"
                        )}
                        style={{ width: `${Math.min(100, score)}%` }}
                      />
                    </div>
                    <span className="w-12 text-right text-sm font-medium text-gray-200">
                      {score.toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      )}

      {/* ── Scans tab ─────────────────────────────────────────────────── */}
      {activeTab === "Scans" && (
        <DataTable
          columns={scanColumns}
          data={scans}
          keyExtractor={(row) => row.id}
          emptyMessage="No security scans yet."
        />
      )}
    </div>
  );
}
