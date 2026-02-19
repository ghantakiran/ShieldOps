import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, Scan, AlertTriangle, Clock, Loader2 } from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import { get, post } from "../api/client";
import type { SecurityScan, Vulnerability } from "../api/types";
import type { Column } from "../components/DataTable";
import MetricCard from "../components/MetricCard";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

export default function Security() {
  const queryClient = useQueryClient();
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null);

  // ── Scans list ─────────────────────────────────────────────────────
  const {
    data: scans = [],
    isLoading: scansLoading,
    error: scansError,
  } = useQuery({
    queryKey: ["security", "scans"],
    queryFn: () => get<SecurityScan[]>("/security/scans"),
  });

  // ── Vulnerabilities for selected scan ──────────────────────────────
  const activeScanId = selectedScanId ?? scans[0]?.id ?? null;

  const { data: vulnerabilities = [], isLoading: vulnsLoading } = useQuery({
    queryKey: ["security", "vulnerabilities", activeScanId],
    queryFn: () => get<Vulnerability[]>(`/security/scans/${activeScanId}/vulnerabilities`),
    enabled: activeScanId !== null,
  });

  // ── Run scan mutation ──────────────────────────────────────────────
  const runScan = useMutation({
    mutationFn: () => post<SecurityScan>("/security/scan", { environment: "production" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["security", "scans"] });
    },
  });

  // ── Derived metrics ────────────────────────────────────────────────
  const totalScans = scans.length;
  const criticalFindings = scans.reduce((sum, s) => sum + s.critical_count, 0);
  const lastScan = scans.length > 0 ? scans[0] : null;
  const lastScanTime = lastScan ? format(new Date(lastScan.started_at), "MMM d, HH:mm") : "Never";

  // ── Table columns ──────────────────────────────────────────────────
  const scanColumns: Column<SecurityScan>[] = [
    {
      key: "scan_type",
      header: "Scan Type",
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

  // ── CVSS color helper ──────────────────────────────────────────────
  function cvssColor(score: number): string {
    if (score >= 9) return "text-red-400";
    if (score >= 7) return "text-orange-400";
    if (score >= 4) return "text-yellow-400";
    return "text-green-400";
  }

  // ── Render ─────────────────────────────────────────────────────────
  if (scansLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Security</h1>
        <button
          onClick={() => runScan.mutate()}
          disabled={runScan.isPending}
          className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {runScan.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Scan className="h-4 w-4" />
          )}
          Run Scan
        </button>
      </div>

      {/* Error banner */}
      {scansError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to load security scans. Please try again later.
        </div>
      )}

      {/* Summary Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard
          label="Total Scans"
          value={totalScans}
          icon={<ShieldAlert className="h-5 w-5" />}
        />
        <MetricCard
          label="Critical Findings"
          value={criticalFindings}
          icon={<AlertTriangle className="h-5 w-5" />}
        />
        <MetricCard
          label="Last Scan Time"
          value={lastScanTime}
          icon={<Clock className="h-5 w-5" />}
        />
      </div>

      {/* Recent Scans */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-100">Recent Scans</h2>
        <DataTable
          columns={scanColumns}
          data={scans}
          keyExtractor={(row) => row.id}
          onRowClick={(row) => setSelectedScanId(row.id)}
          emptyMessage="No security scans yet. Run your first scan to get started."
        />
      </section>

      {/* Vulnerability Overview */}
      {activeScanId && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-100">Vulnerability Overview</h2>
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            {vulnsLoading ? (
              <LoadingSpinner size="sm" className="py-8" />
            ) : vulnerabilities.length === 0 ? (
              <p className="py-8 text-center text-sm text-gray-500">
                No vulnerabilities found for this scan.
              </p>
            ) : (
              <ul className="divide-y divide-gray-800">
                {vulnerabilities.map((vuln) => (
                  <li key={vuln.cve_id} className="flex items-start gap-4 py-3 first:pt-0 last:pb-0">
                    {/* CVE ID */}
                    <span className="w-36 shrink-0 font-mono text-sm font-bold text-gray-100">
                      {vuln.cve_id}
                    </span>

                    {/* Severity */}
                    <div className="w-24 shrink-0">
                      <StatusBadge status={vuln.severity} />
                    </div>

                    {/* Package + versions */}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-gray-300">{vuln.package_name}</p>
                      <p className="text-xs text-gray-500">
                        {vuln.installed_version}
                        {vuln.fixed_version && (
                          <>
                            {" "}
                            <span className="text-gray-600">&rarr;</span>{" "}
                            <span className="text-green-400">{vuln.fixed_version}</span>
                          </>
                        )}
                      </p>
                    </div>

                    {/* CVSS score */}
                    <span
                      className={clsx(
                        "shrink-0 text-sm font-semibold tabular-nums",
                        cvssColor(vuln.cvss_score),
                      )}
                    >
                      {vuln.cvss_score.toFixed(1)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
