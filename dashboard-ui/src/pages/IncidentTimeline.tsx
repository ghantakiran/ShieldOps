import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, Filter } from "lucide-react";
import clsx from "clsx";
import { get } from "../api/client";
import type {
  IncidentTimelineResponse,
  IncidentTimelineEvent,
  IncidentTimelineEventType,
} from "../api/types";
import Timeline from "../components/Timeline";
import LoadingSpinner from "../components/LoadingSpinner";

// ── Filter bar types ────────────────────────────────────────────────

const EVENT_TYPES: {
  value: IncidentTimelineEventType;
  label: string;
  color: string;
}[] = [
  {
    value: "investigation",
    label: "Investigation",
    color: "accent-blue-500",
  },
  {
    value: "remediation",
    label: "Remediation",
    color: "accent-amber-500",
  },
  {
    value: "audit",
    label: "Audit",
    color: "accent-gray-400",
  },
  {
    value: "security",
    label: "Security",
    color: "accent-red-500",
  },
];

const SEVERITY_OPTIONS = ["critical", "high", "medium", "low", "warning"];

// ── Page component ──────────────────────────────────────────────────

export default function IncidentTimeline() {
  const { id } = useParams<{ id: string }>();

  // Filter state
  const [activeTypes, setActiveTypes] = useState<Set<IncidentTimelineEventType>>(
    new Set(["investigation", "remediation", "audit", "security"]),
  );
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const {
    data: timeline,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["investigation-timeline", id],
    queryFn: () =>
      get<IncidentTimelineResponse>(
        `/investigations/${id}/timeline`,
      ),
    enabled: !!id,
  });

  // Toggle an event type filter
  function toggleType(type: IncidentTimelineEventType) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        // Don't allow deselecting all types
        if (next.size > 1) next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }

  // Apply client-side filters
  const filteredEvents: IncidentTimelineEvent[] =
    timeline?.events.filter((e) => {
      if (!activeTypes.has(e.type)) return false;
      if (
        severityFilter &&
        e.severity !== severityFilter
      ) {
        return false;
      }
      return true;
    }) ?? [];

  // ── Render ──────────────────────────────────────────────────────

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
          Failed to load timeline:{" "}
          {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          to={`/investigations/${id}`}
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 transition-colors hover:text-gray-100"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Investigation
        </Link>
        <div className="mt-3 flex items-center gap-3">
          <Clock className="h-6 w-6 text-brand-400" />
          <h1 className="text-2xl font-bold text-gray-100">
            Incident Timeline
          </h1>
          <span className="rounded-full bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-gray-400">
            {filteredEvents.length} event
            {filteredEvents.length !== 1 ? "s" : ""}
          </span>
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Investigation{" "}
          <span className="font-mono text-gray-400">{id}</span>
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-gray-800 bg-gray-900 p-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Filter className="h-4 w-4" />
          <span className="font-medium">Filters</span>
        </div>

        {/* Event type toggles */}
        <div className="flex flex-wrap gap-2">
          {EVENT_TYPES.map((et) => (
            <button
              key={et.value}
              type="button"
              onClick={() => toggleType(et.value)}
              className={clsx(
                "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-all",
                activeTypes.has(et.value)
                  ? "bg-gray-700 text-gray-100 ring-gray-600"
                  : "bg-gray-900 text-gray-500 ring-gray-800 hover:text-gray-300",
              )}
            >
              {et.label}
            </button>
          ))}
        </div>

        {/* Severity dropdown */}
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-gray-300 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">All severities</option>
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Timeline */}
      <Timeline events={filteredEvents} loading={isLoading} />
    </div>
  );
}
