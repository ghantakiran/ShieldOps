import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield,
  CheckCircle,
  XCircle,
  AlertTriangle,
  MinusCircle,
  Filter,
  Download,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronRight,
  Lock,
  Eye,
  Server,
  FileCheck,
  ShieldCheck,
  RefreshCw,
} from "lucide-react";
import clsx from "clsx";
import { get } from "../api/client";
import LoadingSpinner from "../components/LoadingSpinner";

// -- Types -----------------------------------------------------------

interface ComplianceControl {
  id: string;
  name: string;
  description: string;
  category: string;
  status: string;
  details: string;
  evidence: Record<string, unknown>[];
  last_checked: string | null;
  override: Record<string, unknown> | null;
}

interface ComplianceReport {
  id: string;
  generated_at: string;
  overall_score: number;
  total_controls: number;
  passed: number;
  failed: number;
  warnings: number;
  not_applicable: number;
  category_scores: Record<string, number>;
  controls: ComplianceControl[];
}

interface ComplianceTrend {
  period_days: number;
  data_points: { date: string; score: number }[];
  current_score: number;
  previous_score: number;
  trend_direction: string;
}

interface EvidenceResponse {
  control_id: string;
  evidence: Record<string, unknown>[];
  total: number;
}

// -- Constants -------------------------------------------------------

const CATEGORY_CONFIG: Record<
  string,
  { label: string; color: string; icon: typeof Shield }
> = {
  security: {
    label: "Security",
    color: "bg-red-500/20 text-red-400 border-red-500/30",
    icon: Shield,
  },
  availability: {
    label: "Availability",
    color: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    icon: Server,
  },
  processing_integrity: {
    label: "Processing Integrity",
    color: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    icon: FileCheck,
  },
  confidentiality: {
    label: "Confidentiality",
    color: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    icon: Lock,
  },
  privacy: {
    label: "Privacy",
    color: "bg-green-500/20 text-green-400 border-green-500/30",
    icon: Eye,
  },
};

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; bgColor: string; icon: typeof CheckCircle }
> = {
  pass: {
    label: "Pass",
    color: "text-green-400",
    bgColor: "bg-green-500/20 border-green-500/30",
    icon: CheckCircle,
  },
  fail: {
    label: "Fail",
    color: "text-red-400",
    bgColor: "bg-red-500/20 border-red-500/30",
    icon: XCircle,
  },
  warning: {
    label: "Warning",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20 border-yellow-500/30",
    icon: AlertTriangle,
  },
  not_applicable: {
    label: "N/A",
    color: "text-gray-400",
    bgColor: "bg-gray-500/20 border-gray-500/30",
    icon: MinusCircle,
  },
};

// -- Score Gauge -----------------------------------------------------

function ScoreGauge({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 58;
  const offset = circumference - (score / 100) * circumference;
  const scoreColor =
    score >= 80
      ? "text-green-400"
      : score >= 60
        ? "text-yellow-400"
        : "text-red-400";
  const strokeColor =
    score >= 80 ? "stroke-green-400" : score >= 60 ? "stroke-yellow-400" : "stroke-red-400";

  return (
    <div className="relative flex items-center justify-center">
      <svg className="h-36 w-36 -rotate-90" viewBox="0 0 128 128">
        <circle
          cx="64"
          cy="64"
          r="58"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-gray-800"
        />
        <circle
          cx="64"
          cy="64"
          r="58"
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={strokeColor}
        />
      </svg>
      <div className="absolute text-center">
        <span className={clsx("text-3xl font-bold", scoreColor)}>
          {score}%
        </span>
        <p className="text-xs text-gray-500">Compliance</p>
      </div>
    </div>
  );
}

// -- Category Card ---------------------------------------------------

function CategoryCard({
  category,
  score,
}: {
  category: string;
  score: number;
}) {
  const cfg = CATEGORY_CONFIG[category] ?? {
    label: category,
    color: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    icon: Shield,
  };
  const Icon = cfg.icon;
  const scoreColor =
    score >= 80
      ? "text-green-400"
      : score >= 60
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-800 bg-gray-900 p-4">
      <div
        className={clsx(
          "flex h-10 w-10 items-center justify-center rounded-lg",
          cfg.color
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium text-gray-300">{cfg.label}</p>
        <div className="mt-1 h-2 w-full rounded-full bg-gray-800">
          <div
            className={clsx(
              "h-2 rounded-full transition-all",
              score >= 80
                ? "bg-green-500"
                : score >= 60
                  ? "bg-yellow-500"
                  : "bg-red-500"
            )}
            style={{ width: `${Math.min(score, 100)}%` }}
          />
        </div>
      </div>
      <span className={clsx("text-lg font-bold", scoreColor)}>
        {score}%
      </span>
    </div>
  );
}

// -- Status Badge ----------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.fail;
  const Icon = cfg.icon;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        cfg.bgColor,
        cfg.color
      )}
    >
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  );
}

// -- Evidence Viewer -------------------------------------------------

function EvidenceViewer({ controlId }: { controlId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["compliance-evidence", controlId],
    queryFn: () => get<EvidenceResponse>(`/compliance/evidence/${controlId}`),
  });

  if (isLoading) {
    return (
      <div className="py-2 text-sm text-gray-500">Loading evidence...</div>
    );
  }

  if (!data || data.total === 0) {
    return (
      <div className="py-2 text-sm text-gray-500">No evidence collected.</div>
    );
  }

  return (
    <div className="mt-2 space-y-2">
      {data.evidence.map((item, idx) => (
        <div
          key={idx}
          className="rounded-lg border border-gray-800 bg-gray-800/50 p-3"
        >
          <pre className="overflow-x-auto text-xs text-gray-400">
            {JSON.stringify(item, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

// -- Control Row -----------------------------------------------------

function ControlRow({ control }: { control: ComplianceControl }) {
  const [expanded, setExpanded] = useState(false);
  const catCfg = CATEGORY_CONFIG[control.category] ?? {
    label: control.category,
    color: "bg-gray-500/20 text-gray-400",
    icon: Shield,
  };

  return (
    <div className="border-b border-gray-800 last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-gray-800/50"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-gray-500" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-gray-500" />
        )}
        <div className="w-20 shrink-0">
          <code className="text-xs font-medium text-brand-400">
            {control.id}
          </code>
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-200">{control.name}</p>
        </div>
        <span
          className={clsx(
            "rounded-full border px-2 py-0.5 text-xs font-medium",
            catCfg.color
          )}
        >
          {catCfg.label}
        </span>
        <StatusBadge status={control.status} />
        {control.override && (
          <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-xs text-indigo-400">
            Override
          </span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-gray-800 bg-gray-900/50 px-12 py-4">
          <p className="text-sm text-gray-400">{control.description}</p>
          {control.details && (
            <p className="mt-2 text-sm text-gray-300">
              <span className="font-medium">Details:</span> {control.details}
            </p>
          )}
          {control.override && (
            <div className="mt-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3">
              <p className="text-xs font-medium text-indigo-400">
                Admin Override
              </p>
              <p className="mt-1 text-xs text-gray-400">
                Justification:{" "}
                {String(
                  (control.override as Record<string, unknown>).justification ??
                    "N/A"
                )}
              </p>
              <p className="text-xs text-gray-500">
                By:{" "}
                {String(
                  (control.override as Record<string, unknown>).overridden_by ??
                    "Unknown"
                )}
              </p>
            </div>
          )}
          <div className="mt-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Evidence
            </p>
            <EvidenceViewer controlId={control.id} />
          </div>
        </div>
      )}
    </div>
  );
}

// -- Trend Chart (simple SVG) ----------------------------------------

function TrendChart({ trend }: { trend: ComplianceTrend }) {
  const points = trend.data_points;
  if (points.length === 0) return null;

  const width = 600;
  const height = 120;
  const padding = 20;
  const innerW = width - padding * 2;
  const innerH = height - padding * 2;

  const minScore = Math.min(...points.map((p) => p.score)) - 5;
  const maxScore = Math.max(...points.map((p) => p.score)) + 5;
  const range = maxScore - minScore || 1;

  const pathData = points
    .map((p, i) => {
      const x = padding + (i / (points.length - 1)) * innerW;
      const y = padding + innerH - ((p.score - minScore) / range) * innerH;
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const TrendIcon =
    trend.trend_direction === "up"
      ? TrendingUp
      : trend.trend_direction === "down"
        ? TrendingDown
        : Minus;
  const trendColor =
    trend.trend_direction === "up"
      ? "text-green-400"
      : trend.trend_direction === "down"
        ? "text-red-400"
        : "text-gray-400";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">
          Compliance Trend ({trend.period_days} days)
        </h3>
        <div className={clsx("flex items-center gap-1 text-sm", trendColor)}>
          <TrendIcon className="h-4 w-4" />
          {trend.current_score}%
          <span className="text-xs text-gray-500">
            (prev: {trend.previous_score}%)
          </span>
        </div>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        preserveAspectRatio="none"
      >
        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map((pct) => {
          const val = minScore + (pct / 100) * range;
          const y = padding + innerH - (pct / 100) * innerH;
          return (
            <g key={pct}>
              <line
                x1={padding}
                y1={y}
                x2={width - padding}
                y2={y}
                stroke="currentColor"
                strokeWidth="0.5"
                className="text-gray-800"
              />
              <text
                x={padding - 4}
                y={y + 3}
                textAnchor="end"
                className="fill-gray-600 text-[8px]"
              >
                {Math.round(val)}
              </text>
            </g>
          );
        })}
        {/* Trend line */}
        <path
          d={pathData}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-brand-400"
        />
      </svg>
    </div>
  );
}

// -- Main Page -------------------------------------------------------

export default function ComplianceDashboard() {
  const queryClient = useQueryClient();
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  // Fetch report
  const {
    data: report,
    isLoading: reportLoading,
    isFetching: reportFetching,
  } = useQuery({
    queryKey: ["compliance-report"],
    queryFn: () => get<ComplianceReport>("/compliance/report"),
  });

  // Fetch trends
  const { data: trend } = useQuery({
    queryKey: ["compliance-trends"],
    queryFn: () => get<ComplianceTrend>("/compliance/trends?days=30"),
  });

  // Refresh mutation
  const refreshMutation = useMutation({
    mutationFn: () => get<ComplianceReport>("/compliance/report"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance-report"] });
      queryClient.invalidateQueries({ queryKey: ["compliance-trends"] });
    },
  });

  // Filter controls client-side
  const filteredControls = useMemo(() => {
    if (!report) return [];
    let controls = report.controls;
    if (categoryFilter) {
      controls = controls.filter((c) => c.category === categoryFilter);
    }
    if (statusFilter) {
      controls = controls.filter((c) => c.status === statusFilter);
    }
    return controls;
  }, [report, categoryFilter, statusFilter]);

  // Export report as JSON download
  const handleExport = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `soc2-report-${report.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (reportLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  if (!report) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-gray-400">
        <Shield className="h-12 w-12 text-gray-600" />
        <p className="mt-3">Unable to load compliance report.</p>
      </div>
    );
  }

  const categories = Object.entries(report.category_scores);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-8 w-8 text-brand-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-100">
              SOC2 Compliance
            </h1>
            <p className="text-sm text-gray-500">
              Trust Service Criteria Assessment
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={reportFetching || refreshMutation.isPending}
            className={clsx(
              "flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2",
              "text-sm font-medium text-gray-400 transition-colors",
              "hover:border-gray-600 hover:text-gray-300",
              "disabled:opacity-50"
            )}
          >
            <RefreshCw
              className={clsx(
                "h-4 w-4",
                (reportFetching || refreshMutation.isPending) && "animate-spin"
              )}
            />
            Re-audit
          </button>
          <button
            onClick={handleExport}
            className={clsx(
              "flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2",
              "text-sm font-medium text-white transition-colors",
              "hover:bg-brand-700"
            )}
          >
            <Download className="h-4 w-4" />
            Export Report
          </button>
        </div>
      </div>

      {/* Score + Summary Cards */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Overall Score */}
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-800 bg-gray-900 p-6">
          <ScoreGauge score={report.overall_score} />
          <div className="mt-4 flex items-center gap-6 text-center">
            <div>
              <p className="text-lg font-bold text-green-400">
                {report.passed}
              </p>
              <p className="text-xs text-gray-500">Passed</p>
            </div>
            <div>
              <p className="text-lg font-bold text-red-400">{report.failed}</p>
              <p className="text-xs text-gray-500">Failed</p>
            </div>
            <div>
              <p className="text-lg font-bold text-yellow-400">
                {report.warnings}
              </p>
              <p className="text-xs text-gray-500">Warnings</p>
            </div>
            <div>
              <p className="text-lg font-bold text-gray-400">
                {report.not_applicable}
              </p>
              <p className="text-xs text-gray-500">N/A</p>
            </div>
          </div>
          <p className="mt-3 text-xs text-gray-600">
            Report ID: {report.id}
          </p>
        </div>

        {/* Category Breakdown */}
        <div className="col-span-2 space-y-3">
          <h3 className="text-sm font-semibold text-gray-300">
            Trust Service Categories
          </h3>
          {categories.map(([cat, score]) => (
            <CategoryCard key={cat} category={cat} score={score} />
          ))}
        </div>
      </div>

      {/* Trend Chart */}
      {trend && <TrendChart trend={trend} />}

      {/* Controls Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-300">
            <Filter className="h-4 w-4" />
            Controls ({filteredControls.length} of {report.total_controls})
          </h3>
          <div className="flex items-center gap-3">
            {/* Category filter */}
            <select
              value={categoryFilter ?? ""}
              onChange={(e) =>
                setCategoryFilter(e.target.value || null)
              }
              className={clsx(
                "rounded-lg border border-gray-700 bg-gray-800",
                "px-3 py-1.5 text-xs text-gray-300",
                "focus:border-brand-500 focus:outline-none"
              )}
            >
              <option value="">All Categories</option>
              {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => (
                <option key={key} value={key}>
                  {cfg.label}
                </option>
              ))}
            </select>

            {/* Status filter */}
            <select
              value={statusFilter ?? ""}
              onChange={(e) =>
                setStatusFilter(e.target.value || null)
              }
              className={clsx(
                "rounded-lg border border-gray-700 bg-gray-800",
                "px-3 py-1.5 text-xs text-gray-300",
                "focus:border-brand-500 focus:outline-none"
              )}
            >
              <option value="">All Statuses</option>
              {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                <option key={key} value={key}>
                  {cfg.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Control rows */}
        <div>
          {filteredControls.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <Shield className="h-8 w-8 text-gray-600" />
              <p className="mt-2 text-sm">
                No controls match the selected filters.
              </p>
            </div>
          ) : (
            filteredControls.map((control) => (
              <ControlRow key={control.id} control={control} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
