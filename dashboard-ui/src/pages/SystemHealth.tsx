import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Activity,
  Database,
  Server,
  Shield,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import clsx from "clsx";
import { get } from "../api/client";
import LoadingSpinner from "../components/LoadingSpinner";

// -- Types ------------------------------------------------------------------

interface DependencyCheck {
  status: "healthy" | "unhealthy";
  latency_ms: number | null;
  details?: string;
  error?: string;
}

interface DetailedHealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  timestamp: string;
  checks: {
    database: DependencyCheck;
    redis: DependencyCheck;
    kafka: DependencyCheck;
    opa: DependencyCheck;
  };
  uptime_seconds: number;
}

// -- Helpers ----------------------------------------------------------------

const SERVICE_META: Record<
  string,
  { label: string; icon: React.ElementType; description: string }
> = {
  database: {
    label: "PostgreSQL",
    icon: Database,
    description: "Primary data store for agent state and audit logs",
  },
  redis: {
    label: "Redis",
    icon: Server,
    description: "Real-time coordination, caching, and rate limiting",
  },
  kafka: {
    label: "Kafka",
    icon: Activity,
    description: "Event streaming and alert ingestion bus",
  },
  opa: {
    label: "OPA",
    icon: Shield,
    description: "Open Policy Agent for policy evaluation",
  },
};

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  if (h < 24) return `${h}h ${rm}m`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return `${d}d ${rh}h ${rm}m`;
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// -- Sub-components ---------------------------------------------------------

function OverallStatusBadge({
  status,
}: {
  status: "healthy" | "degraded" | "unhealthy";
}) {
  const config = {
    healthy: {
      label: "All Systems Operational",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/30",
      text: "text-emerald-400",
      icon: CheckCircle,
    },
    degraded: {
      label: "Degraded Performance",
      bg: "bg-yellow-500/10",
      border: "border-yellow-500/30",
      text: "text-yellow-400",
      icon: AlertTriangle,
    },
    unhealthy: {
      label: "System Outage",
      bg: "bg-red-500/10",
      border: "border-red-500/30",
      text: "text-red-400",
      icon: XCircle,
    },
  }[status];

  const Icon = config.icon;

  return (
    <div
      className={clsx(
        "flex items-center gap-3 rounded-xl border px-6 py-4",
        config.bg,
        config.border,
      )}
    >
      <Icon className={clsx("h-8 w-8", config.text)} />
      <div>
        <p className={clsx("text-lg font-semibold", config.text)}>
          {config.label}
        </p>
        <p className="text-xs text-gray-500">
          Status: {status}
        </p>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "inline-block h-2.5 w-2.5 rounded-full",
        status === "healthy" && "bg-emerald-400",
        status === "unhealthy" && "bg-red-400",
      )}
    />
  );
}

function DependencyCard({
  name,
  check,
  lastChecked,
}: {
  name: string;
  check: DependencyCheck;
  lastChecked: string;
}) {
  const meta = SERVICE_META[name];
  if (!meta) return null;
  const Icon = meta.icon;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-gray-800 p-2">
            <Icon className="h-5 w-5 text-gray-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-100">
              {meta.label}
            </p>
            <p className="text-xs text-gray-500">{meta.description}</p>
          </div>
        </div>
        <StatusDot status={check.status} />
      </div>

      <div className="mt-4 space-y-2">
        {/* Latency */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Latency</span>
          <span className="font-mono text-gray-300">
            {check.latency_ms != null ? `${check.latency_ms}ms` : "--"}
          </span>
        </div>

        {/* Details or Error */}
        {check.details && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-500">Info</span>
            <span className="truncate pl-4 text-right text-gray-400">
              {check.details}
            </span>
          </div>
        )}

        {check.error && (
          <div className="mt-2 rounded-lg bg-red-500/10 px-3 py-2">
            <p className="text-xs text-red-400">{check.error}</p>
          </div>
        )}

        {/* Last checked */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Last checked</span>
          <span className="text-gray-400">
            {formatTimestamp(lastChecked)}
          </span>
        </div>
      </div>
    </div>
  );
}

// -- Page -------------------------------------------------------------------

export default function SystemHealth() {
  const [autoRefresh, setAutoRefresh] = useState(true);

  const {
    data,
    isLoading,
    isError,
    error,
    dataUpdatedAt,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["health", "detailed"],
    queryFn: () => get<DetailedHealthResponse>("/health/detailed"),
    refetchInterval: autoRefresh ? 30_000 : false,
    retry: 1,
  });

  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  if (isError) {
    return (
      <div className="mt-32 rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
        <p className="text-sm text-red-400">
          Failed to load health status.{" "}
          {error instanceof Error ? error.message : "Unknown error."}
        </p>
        <button
          onClick={() => refetch()}
          className="mt-3 rounded-lg bg-red-500/20 px-4 py-2 text-xs text-red-400 hover:bg-red-500/30"
        >
          Retry
        </button>
      </div>
    );
  }

  const health = data!;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            System Health
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Real-time status of platform dependencies
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh((prev) => !prev)}
            className={clsx(
              "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors",
              autoRefresh
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-gray-700 bg-gray-800 text-gray-400 hover:text-gray-300",
            )}
          >
            <RefreshCw
              className={clsx(
                "h-3.5 w-3.5",
                autoRefresh && isFetching && "animate-spin",
              )}
            />
            Auto-refresh {autoRefresh ? "ON" : "OFF"}
          </button>

          {/* Manual refresh */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-xs font-medium text-gray-400 transition-colors hover:text-gray-300 disabled:opacity-50"
          >
            <RefreshCw
              className={clsx("h-3.5 w-3.5", isFetching && "animate-spin")}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Overall status banner */}
      <OverallStatusBadge status={health.status} />

      {/* Last checked + uptime bar */}
      <div className="flex flex-wrap items-center gap-6 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          Last checked: {formatTimestamp(health.timestamp)}
        </div>
        <div className="flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5" />
          Server uptime: {formatUptime(health.uptime_seconds)}
        </div>
        {dataUpdatedAt > 0 && (
          <div className="flex items-center gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" />
            Client fetched:{" "}
            {new Date(dataUpdatedAt).toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* Dependency cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {(
          Object.entries(health.checks) as [
            string,
            DependencyCheck,
          ][]
        ).map(([name, check]) => (
          <DependencyCard
            key={name}
            name={name}
            check={check}
            lastChecked={health.timestamp}
          />
        ))}
      </div>

      {/* Uptime section */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-100">
            Server Uptime
          </h2>
        </div>
        <div className="mt-4 flex items-baseline gap-3">
          <span className="text-3xl font-bold text-gray-100">
            {formatUptime(health.uptime_seconds)}
          </span>
          <span className="text-sm text-gray-500">
            ({Math.round(health.uptime_seconds).toLocaleString()}{" "}
            seconds)
          </span>
        </div>
      </div>
    </div>
  );
}
