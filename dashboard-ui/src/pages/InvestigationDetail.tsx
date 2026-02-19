import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Wrench, Clock } from "lucide-react";
import { format, parseISO } from "date-fns";
import clsx from "clsx";
import { get } from "../api/client";
import type { InvestigationDetail as InvestigationDetailType, TimelineEvent } from "../api/types";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function ConfidenceMeter({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color =
    confidence > 0.85
      ? "bg-green-500"
      : confidence > 0.5
        ? "bg-yellow-500"
        : "bg-red-500";
  const textColor =
    confidence > 0.85
      ? "text-green-400"
      : confidence > 0.5
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 rounded-full bg-gray-800">
        <div
          className={clsx("h-2 rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={clsx("text-sm font-medium", textColor)}>{pct}%</span>
    </div>
  );
}

function Timeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-gray-500">No timeline events recorded.</p>
    );
  }

  return (
    <div className="relative space-y-0">
      {/* Vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-gray-700" />
      {events.map((event, idx) => (
        <div key={idx} className="relative flex gap-4 pb-6 last:pb-0">
          {/* Dot */}
          <div className="relative z-10 mt-1.5 h-[15px] w-[15px] flex-shrink-0 rounded-full border-2 border-gray-700 bg-gray-900" />
          {/* Content */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-gray-500">
                {format(parseISO(event.timestamp), "HH:mm:ss")}
              </span>
              <StatusBadge status={event.event_type} />
            </div>
            <p className="mt-1 text-sm text-gray-300">{event.description}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function InvestigationDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: investigation, isLoading, isError, error } = useQuery({
    queryKey: ["investigation", id],
    queryFn: () => get<InvestigationDetailType>(`/investigations/${id}`),
    enabled: !!id,
  });

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
          Failed to load investigation: {(error as Error).message}
        </p>
      </div>
    );
  }

  if (!investigation) return null;

  const inv = investigation;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          to="/investigations"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 transition-colors hover:text-gray-100"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Investigations
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-100">{inv.alert_name}</h1>
          <StatusBadge status={inv.severity} />
          <StatusBadge status={inv.status} />
        </div>
      </div>

      {/* Info Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { label: "Alert ID", value: inv.alert_id },
          { label: "Resource ID", value: inv.resource_id, mono: true },
          {
            label: "Started At",
            value: format(parseISO(inv.started_at), "MMM d, yyyy HH:mm:ss"),
          },
          {
            label: "Completed At",
            value: inv.completed_at
              ? format(parseISO(inv.completed_at), "MMM d, yyyy HH:mm:ss")
              : "In progress",
          },
          {
            label: "Duration",
            value:
              inv.duration_seconds !== null && inv.duration_seconds !== undefined
                ? formatDuration(inv.duration_seconds)
                : "Ongoing",
          },
          {
            label: "Confidence",
            value:
              inv.confidence !== null && inv.confidence !== undefined
                ? `${Math.round(inv.confidence * 100)}%`
                : "N/A",
          },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-gray-800 bg-gray-900 p-5"
          >
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
              {item.label}
            </p>
            <p
              className={clsx(
                "mt-1 text-sm text-gray-100",
                item.mono && "font-mono",
              )}
            >
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {/* Root Cause Card */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
          Root Cause Analysis
        </h2>
        {inv.root_cause ? (
          <div className="mt-3 space-y-3">
            <p className="text-sm leading-relaxed text-gray-200">
              {inv.root_cause}
            </p>
            {inv.confidence !== null && inv.confidence !== undefined && (
              <div>
                <p className="mb-1 text-xs text-gray-500">Confidence</p>
                <ConfidenceMeter confidence={inv.confidence} />
              </div>
            )}
          </div>
        ) : (
          <div className="mt-3 flex items-center gap-2 text-sm text-gray-400">
            <Clock className="h-4 w-4 animate-pulse" />
            Analysis in progress...
          </div>
        )}
      </div>

      {/* Recommended Actions */}
      {inv.recommended_actions.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
            Recommended Actions
          </h2>
          <ul className="mt-3 space-y-2">
            {inv.recommended_actions.map((action, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-gray-300">
                <Wrench className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-400" />
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Timeline */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-gray-500">
          Timeline
        </h2>
        <Timeline events={inv.timeline} />
      </div>
    </div>
  );
}
