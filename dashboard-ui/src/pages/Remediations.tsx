import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { get } from "../api/client";
import type { Remediation } from "../api/types";
import DataTable, { type Column } from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All Statuses" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "approved", label: "Approved" },
  { value: "executing", label: "Executing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "rolled_back", label: "Rolled Back" },
];

const RISK_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All Risk Levels" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const ENV_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All Environments" },
  { value: "production", label: "Production" },
  { value: "staging", label: "Staging" },
  { value: "development", label: "Development" },
];

export default function Remediations() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [envFilter, setEnvFilter] = useState("all");

  const { data: remediations, isLoading, isError, error } = useQuery({
    queryKey: ["remediations"],
    queryFn: () => get<Remediation[]>("/remediations/"),
  });

  const filtered = useMemo(() => {
    if (!remediations) return [];
    return remediations.filter((rem) => {
      if (statusFilter !== "all" && rem.status !== statusFilter) return false;
      if (riskFilter !== "all" && rem.risk_level !== riskFilter) return false;
      if (envFilter !== "all" && rem.environment !== envFilter) return false;
      return true;
    });
  }, [remediations, statusFilter, riskFilter, envFilter]);

  const columns: Column<Remediation>[] = [
    {
      key: "action_type",
      header: "Action Type",
      render: (row) => (
        <span className="font-medium text-gray-100">{row.action_type}</span>
      ),
    },
    {
      key: "target_resource",
      header: "Target Resource",
      render: (row) => (
        <span className="font-mono text-xs text-gray-400">
          {row.target_resource}
        </span>
      ),
    },
    {
      key: "environment",
      header: "Environment",
      render: (row) => <StatusBadge status={row.environment} />,
    },
    {
      key: "risk_level",
      header: "Risk Level",
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
        <span className="text-xs text-gray-400">
          {formatDistanceToNow(parseISO(row.started_at), { addSuffix: true })}
        </span>
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
          Failed to load remediations: {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-gray-100">Remediations</h1>
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
          value={riskFilter}
          onChange={(e) => setRiskFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        >
          {RISK_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={envFilter}
          onChange={(e) => setEnvFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        >
          {ENV_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <DataTable<Remediation>
        columns={columns}
        data={filtered}
        keyExtractor={(row) => row.id}
        onRowClick={(row) => navigate(`/remediations/${row.id}`)}
        emptyMessage="No remediations match your filters."
      />
    </div>
  );
}
