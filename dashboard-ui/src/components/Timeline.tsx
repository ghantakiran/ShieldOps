import { useState } from "react";
import { format, parseISO } from "date-fns";
import {
  Search,
  Shield,
  Wrench,
  FileText,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import clsx from "clsx";
import type { IncidentTimelineEvent, IncidentTimelineEventType } from "../api/types";
import LoadingSpinner from "./LoadingSpinner";

// ── Type badge config ────────────────────────────────────────────────

const TYPE_CONFIG: Record<
  IncidentTimelineEventType,
  { label: string; color: string; icon: typeof Search }
> = {
  investigation: {
    label: "Investigation",
    color: "bg-blue-500/10 text-blue-400 ring-blue-500/20",
    icon: Search,
  },
  remediation: {
    label: "Remediation",
    color: "bg-amber-500/10 text-amber-400 ring-amber-500/20",
    icon: Wrench,
  },
  audit: {
    label: "Audit",
    color: "bg-gray-500/10 text-gray-400 ring-gray-500/20",
    icon: FileText,
  },
  security: {
    label: "Security",
    color: "bg-red-500/10 text-red-400 ring-red-500/20",
    icon: Shield,
  },
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
  warning: "text-yellow-400",
};

const DOT_COLORS: Record<IncidentTimelineEventType, string> = {
  investigation: "border-blue-500 bg-blue-500/20",
  remediation: "border-amber-500 bg-amber-500/20",
  audit: "border-gray-500 bg-gray-500/20",
  security: "border-red-500 bg-red-500/20",
};

// ── Sub-components ───────────────────────────────────────────────────

function TypeBadge({ type }: { type: IncidentTimelineEventType }) {
  const config = TYPE_CONFIG[type] ?? TYPE_CONFIG.audit;
  const Icon = config.icon;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        config.color,
      )}
    >
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  );
}

function EventCard({ event }: { event: IncidentTimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails =
    event.details && Object.keys(event.details).length > 0;

  return (
    <div className="min-w-0 flex-1 rounded-lg border border-gray-800 bg-gray-900/50 p-4 transition-colors hover:border-gray-700">
      {/* Header row */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-gray-500">
          {format(parseISO(event.timestamp), "MMM d, HH:mm:ss")}
        </span>
        <TypeBadge type={event.type} />
        {event.severity && (
          <span
            className={clsx(
              "text-xs font-medium",
              SEVERITY_COLORS[event.severity] ?? "text-gray-400",
            )}
          >
            {event.severity}
          </span>
        )}
      </div>

      {/* Action & actor */}
      <p className="mt-2 text-sm font-medium text-gray-200">
        {event.action.replace(/_/g, " ")}
      </p>
      <p className="mt-0.5 text-xs text-gray-500">
        by {event.actor}
      </p>

      {/* Expandable details */}
      {hasDetails && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center gap-1 text-xs text-gray-400 transition-colors hover:text-gray-200"
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            Details
          </button>
          {expanded && (
            <div className="mt-2 rounded-md bg-gray-800/50 p-3">
              <dl className="space-y-1">
                {Object.entries(event.details)
                  .filter(([, v]) => v != null)
                  .map(([key, value]) => (
                    <div
                      key={key}
                      className="flex gap-2 text-xs"
                    >
                      <dt className="font-medium text-gray-500">
                        {key.replace(/_/g, " ")}:
                      </dt>
                      <dd className="text-gray-300">
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value)}
                      </dd>
                    </div>
                  ))}
              </dl>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Timeline component ─────────────────────────────────────────

export interface TimelineProps {
  events: IncidentTimelineEvent[];
  loading?: boolean;
}

export default function Timeline({ events, loading }: TimelineProps) {
  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-xl border border-gray-800 bg-gray-900/50">
        <AlertTriangle className="h-8 w-8 text-gray-600" />
        <p className="text-sm text-gray-500">
          No timeline events recorded.
        </p>
      </div>
    );
  }

  return (
    <div className="relative space-y-0">
      {/* Vertical line */}
      <div className="absolute left-[9px] top-4 bottom-4 w-px bg-gray-700" />

      {events.map((event) => (
        <div
          key={event.id}
          className="relative flex gap-4 pb-6 last:pb-0"
        >
          {/* Dot on the line */}
          <div
            className={clsx(
              "relative z-10 mt-4 h-[19px] w-[19px] flex-shrink-0 rounded-full border-2",
              DOT_COLORS[event.type] ?? DOT_COLORS.audit,
            )}
          />
          {/* Event card */}
          <EventCard event={event} />
        </div>
      ))}
    </div>
  );
}
