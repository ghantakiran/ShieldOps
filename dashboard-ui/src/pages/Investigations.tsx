import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { get } from "../api/client";
import type { Investigation, InvestigationStatus } from "../api/types";
import DataTable, { type Column } from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

const SEVERITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All Severities" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "warning", label: "Warning" },
  { value: "info", label: "Info" },
];

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

export default function Investigations() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  const { data: investigations, isLoading, isError, error } = useQuery({
    queryKey: ["investigations"],
    queryFn: () => get<Investigation[]>("/investigations/"),
  });

  const filtered = useMemo(() => {
    if (!investigations) return [];
    return investigations.filter((inv) => {
      if (statusFilter !== "all" && inv.status !== statusFilter) return false;
      if (severityFilter !== "all" && inv.severity !== severityFilter) return false;
      return true;
    });
  }, [investigations, statusFilter, severityFilter]);

  const columns: Column<Investigation>[] = [
    {
      key: "alert_name",
      header: "Alert Name",
      render: (row) => (
        <span className="font-medium text-gray-100 truncate block max-w-[220px]" title={row.alert_name}>
          {row.alert_name}
        </span>
      ),
    },
    {
      key: "severity",
      header: "Severity",
      render: (row) => <StatusBadge status={row.severity} />,
    },
    {
      key: "resource_id",
      header: "Resource ID",
      render: (row) => (
        <span className="font-mono text-xs text-gray-400">{row.resource_id}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (row) => {
        if (row.confidence === null || row.confidence === undefined) {
          return <span className="text-gray-500">&mdash;</span>;
        }
        const pct = Math.round(row.confidence * 100);
        return (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-16 rounded-full bg-gray-800">
              <div
                className="h-1.5 rounded-full bg-brand-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">{pct}%</span>
          </div>
        );
      },
    },
    {
      key: "started_at",
      header: "Started",
      render: (row) => (
        <span className="text-xs text-gray-400">
          {formatDistanceToNow(parseISO(row.started_at), { addSuffix: true })}
        </span>
      ),
    },
    {
      key: "duration",
      header: "Duration",
      render: (row) =>
        row.duration_seconds !== null && row.duration_seconds !== undefined ? (
          <span className="text-xs text-gray-400">
            {formatDuration(row.duration_seconds)}
          </span>
        ) : (
          <span className="text-gray-500">&mdash;</span>
        ),
    },
  ];

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
        <p className="text-sm text-red-400">
          Failed to load investigations: {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-gray-100">Investigations</h1>
        <span className="inline-flex items-center rounded-full bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-400 ring-1 ring-inset ring-brand-500/20">
          {filtered.length}
        </span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-gray-500" />
          <span className="text-sm text-gray-500">Filter:</span>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        >
          {SEVERITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <DataTable<Investigation>
        columns={columns}
        data={filtered}
        keyExtractor={(row) => row.id}
        onRowClick={(row) => navigate(`/investigations/${row.id}`)}
        emptyMessage="No investigations match your filters."
      />
    </div>
  );
}
