import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, AlertTriangle, Clock, Loader2, RotateCcw, ShieldCheck, ShieldX } from "lucide-react";
import { format, parseISO } from "date-fns";
import clsx from "clsx";
import { get, post } from "../api/client";
import type { RemediationDetail as RemediationDetailType, TimelineEvent } from "../api/types";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

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

export default function RemediationDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [showRollbackConfirm, setShowRollbackConfirm] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);

  const rollbackMutation = useMutation({
    mutationFn: () =>
      post<Record<string, unknown>>(`/remediations/${id}/rollback`),
    onSuccess: () => {
      setShowRollbackConfirm(false);
      setRollbackError(null);
      queryClient.invalidateQueries({ queryKey: ["remediation", id] });
    },
    onError: (err: Error) => {
      setRollbackError(err.message);
    },
  });

  const { data: remediation, isLoading, isError, error } = useQuery({
    queryKey: ["remediation", id],
    queryFn: () => get<RemediationDetailType>(`/remediations/${id}`),
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
          Failed to load remediation: {(error as Error).message}
        </p>
      </div>
    );
  }

  if (!remediation) return null;

  const rem = remediation;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          to="/remediations"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 transition-colors hover:text-gray-100"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Remediations
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-100">
            {rem.action_type}
          </h1>
          <span className="font-mono text-sm text-gray-400">
            {rem.target_resource}
          </span>
          <StatusBadge status={rem.status} />
          <StatusBadge status={rem.risk_level} />
        </div>
      </div>

      {/* Info Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { label: "Action Type", value: rem.action_type },
          { label: "Target Resource", value: rem.target_resource, mono: true },
          { label: "Environment", value: rem.environment },
          { label: "Risk Level", value: rem.risk_level },
          {
            label: "Started At",
            value: format(parseISO(rem.started_at), "MMM d, yyyy HH:mm:ss"),
          },
          {
            label: "Completed At",
            value: rem.completed_at
              ? format(parseISO(rem.completed_at), "MMM d, yyyy HH:mm:ss")
              : "In progress",
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

      {/* Parameters */}
      {Object.keys(rem.parameters).length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
            Parameters
          </h2>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-gray-950 p-4 text-xs text-gray-300">
            {JSON.stringify(rem.parameters, null, 2)}
          </pre>
        </div>
      )}

      {/* Approval Card */}
      {rem.approval && (
        <div
          className={clsx(
            "rounded-xl border p-5",
            rem.approval.status === "approved"
              ? "border-green-500/20 bg-green-500/5"
              : rem.approval.status === "denied"
                ? "border-red-500/20 bg-red-500/5"
                : "border-gray-800 bg-gray-900",
          )}
        >
          <div className="flex items-center gap-2">
            {rem.approval.status === "approved" ? (
              <ShieldCheck className="h-5 w-5 text-green-400" />
            ) : rem.approval.status === "denied" ? (
              <ShieldX className="h-5 w-5 text-red-400" />
            ) : (
              <Clock className="h-5 w-5 text-gray-400" />
            )}
            <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
              Approval
            </h2>
            <StatusBadge status={rem.approval.status} />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <div>
              <p className="text-xs text-gray-500">Requested At</p>
              <p className="mt-0.5 text-sm text-gray-300">
                {format(parseISO(rem.approval.requested_at), "MMM d, yyyy HH:mm:ss")}
              </p>
            </div>
            {rem.approval.decided_at && (
              <div>
                <p className="text-xs text-gray-500">Decided At</p>
                <p className="mt-0.5 text-sm text-gray-300">
                  {format(parseISO(rem.approval.decided_at), "MMM d, yyyy HH:mm:ss")}
                </p>
              </div>
            )}
            {rem.approval.decided_by && (
              <div>
                <p className="text-xs text-gray-500">Decided By</p>
                <p className="mt-0.5 text-sm text-gray-300">
                  {rem.approval.decided_by}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Rollback Section */}
      {rem.rollback_snapshot_id && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-brand-400" />
            <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
              Rollback
            </h2>
            <span className="inline-flex items-center rounded-full bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-400 ring-1 ring-inset ring-brand-500/20">
              Rollback Available
            </span>
          </div>
          <div className="mt-3 flex items-end justify-between">
            <div>
              <p className="text-xs text-gray-500">Snapshot ID</p>
              <p className="mt-0.5 font-mono text-sm text-gray-300">
                {rem.rollback_snapshot_id}
              </p>
            </div>
            <button
              onClick={() => {
                setRollbackError(null);
                setShowRollbackConfirm(true);
              }}
              disabled={rollbackMutation.isPending}
              className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
            >
              Rollback
            </button>
          </div>
        </div>
      )}

      {/* Rollback Confirmation Modal */}
      {showRollbackConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-xl border border-gray-700 bg-gray-900 p-6">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-100">
              <AlertTriangle className="h-5 w-5 text-orange-400" />
              Confirm Rollback
            </h3>
            <p className="mt-2 text-sm text-gray-400">
              This will revert the remediation to snapshot{" "}
              <span className="font-mono text-gray-300">
                {rem.rollback_snapshot_id}
              </span>
              . This action may affect running services.
            </p>
            {rollbackError && (
              <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400">
                {rollbackError}
              </p>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowRollbackConfirm(false);
                  setRollbackError(null);
                }}
                disabled={rollbackMutation.isPending}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => rollbackMutation.mutate()}
                disabled={rollbackMutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
              >
                {rollbackMutation.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Confirm Rollback
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-gray-500">
          Timeline
        </h2>
        <Timeline events={rem.timeline} />
      </div>
    </div>
  );
}
