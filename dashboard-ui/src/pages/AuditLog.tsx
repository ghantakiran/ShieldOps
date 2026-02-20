import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import clsx from "clsx";
import { get } from "../api/client";
import LoadingSpinner from "../components/LoadingSpinner";

const ENVIRONMENTS = ["production", "staging", "development"];
const AGENT_TYPES = [
  "investigation",
  "remediation",
  "security",
  "cost",
  "learning",
  "supervisor",
];
const PAGE_SIZE = 50;

interface AuditEntry {
  id: string;
  timestamp: string | null;
  agent_type: string;
  action: string;
  target_resource: string;
  environment: string;
  risk_level: string;
  policy_evaluation: string;
  approval_status: string | null;
  outcome: string;
  reasoning: string;
  actor: string;
}

interface AuditResponse {
  items: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

function riskColor(level: string): string {
  const colors: Record<string, string> = {
    critical: "text-red-400",
    high: "text-orange-400",
    medium: "text-yellow-400",
    low: "text-green-400",
  };
  return colors[level] ?? "text-gray-400";
}

function outcomeColor(outcome: string): string {
  const colors: Record<string, string> = {
    success: "bg-green-500/20 text-green-400",
    failure: "bg-red-500/20 text-red-400",
    skipped: "bg-gray-500/20 text-gray-400",
    blocked: "bg-yellow-500/20 text-yellow-400",
    rolled_back: "bg-orange-500/20 text-orange-400",
  };
  return colors[outcome] ?? "bg-gray-500/20 text-gray-400";
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return "--";
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AuditLog() {
  const [environment, setEnvironment] = useState<string>("");
  const [agentType, setAgentType] = useState<string>("");
  const [action, setAction] = useState<string>("");
  const [page, setPage] = useState(0);

  // Build query params
  const params = new URLSearchParams();
  if (environment) params.set("environment", environment);
  if (agentType) params.set("agent_type", agentType);
  if (action) params.set("action", action);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(page * PAGE_SIZE));

  const { data, isLoading, isError } = useQuery({
    queryKey: ["audit-logs", environment, agentType, action, page],
    queryFn: () =>
      get<AuditResponse>(`/audit-logs?${params.toString()}`),
  });

  const entries = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Audit Log</h1>
        <p className="mt-1 text-sm text-gray-500">
          Immutable record of every agent action, policy evaluation, and
          infrastructure change.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={environment}
          onChange={(e) => {
            setEnvironment(e.target.value);
            setPage(0);
          }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-200"
        >
          <option value="">All Environments</option>
          {ENVIRONMENTS.map((env) => (
            <option key={env} value={env}>
              {env.charAt(0).toUpperCase() + env.slice(1)}
            </option>
          ))}
        </select>

        <select
          value={agentType}
          onChange={(e) => {
            setAgentType(e.target.value);
            setPage(0);
          }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-200"
        >
          <option value="">All Agent Types</option>
          {AGENT_TYPES.map((at) => (
            <option key={at} value={at}>
              {at.charAt(0).toUpperCase() + at.slice(1)}
            </option>
          ))}
        </select>

        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            placeholder="Filter by action..."
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(0);
            }}
            className="rounded-lg border border-gray-700 bg-gray-800 py-1.5 pl-8 pr-3 text-sm text-gray-200 placeholder-gray-500"
          />
        </div>
      </div>

      {/* Loading / Error */}
      {isLoading && <LoadingSpinner size="lg" className="mt-16" />}

      {isError && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
          <p className="text-sm text-red-400">
            Failed to load audit logs. You may need admin privileges.
          </p>
        </div>
      )}

      {/* Table */}
      {!isLoading && !isError && (
        <div className="overflow-hidden rounded-xl border border-gray-800 bg-gray-900">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs uppercase tracking-wider text-gray-500">
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Agent</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Env</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Outcome</th>
                <th className="px-4 py-3">Actor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  className="transition-colors hover:bg-gray-800/50"
                >
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-400">
                    {formatTimestamp(entry.timestamp)}
                  </td>
                  <td className="px-4 py-3 capitalize text-gray-300">
                    {entry.agent_type}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-200">
                    {entry.action}
                  </td>
                  <td className="max-w-[200px] truncate px-4 py-3 text-gray-400">
                    {entry.target_resource}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {entry.environment}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        "font-semibold capitalize",
                        riskColor(entry.risk_level),
                      )}
                    >
                      {entry.risk_level}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        outcomeColor(entry.outcome),
                      )}
                    >
                      {entry.outcome.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {entry.actor}
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-4 py-12 text-center text-gray-500"
                  >
                    <FileText className="mx-auto mb-2 h-8 w-8 text-gray-600" />
                    No audit log entries found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {!isLoading && !isError && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>
            Showing {page * PAGE_SIZE + 1}
            &ndash;
            {Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="rounded-lg border border-gray-700 p-1.5 hover:bg-gray-800 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() =>
                setPage(Math.min(totalPages - 1, page + 1))
              }
              disabled={page >= totalPages - 1}
              className="rounded-lg border border-gray-700 p-1.5 hover:bg-gray-800 disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
