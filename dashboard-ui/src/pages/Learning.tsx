import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Brain, Play, BookOpen, Loader2 } from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import clsx from "clsx";
import { get, post } from "../api/client";
import type { LearningCycle, Playbook } from "../api/types";
import type { Column } from "../components/DataTable";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

export default function Learning() {
  const queryClient = useQueryClient();

  // ── Learning cycles ────────────────────────────────────────────────
  const {
    data: cycles = [],
    isLoading: cyclesLoading,
    error: cyclesError,
  } = useQuery({
    queryKey: ["learning", "cycles"],
    queryFn: () => get<LearningCycle[]>("/learning/cycles"),
  });

  // ── Playbooks ──────────────────────────────────────────────────────
  const {
    data: playbooks = [],
    isLoading: playbooksLoading,
    error: playbooksError,
  } = useQuery({
    queryKey: ["learning", "playbooks"],
    queryFn: () => get<Playbook[]>("/playbooks"),
  });

  // ── Trigger learning cycle ─────────────────────────────────────────
  const triggerCycle = useMutation({
    mutationFn: () => post<LearningCycle>("/learning/cycles"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["learning", "cycles"] });
    },
  });

  // ── Cycle table columns ────────────────────────────────────────────
  const cycleColumns: Column<LearningCycle>[] = [
    {
      key: "cycle_type",
      header: "Cycle Type",
      render: (row) => <span className="capitalize text-gray-200">{row.cycle_type}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "patterns_found",
      header: "Patterns Found",
      render: (row) => row.patterns_found,
    },
    {
      key: "playbooks_updated",
      header: "Playbooks Updated",
      render: (row) => row.playbooks_updated,
    },
    {
      key: "started_at",
      header: "Started",
      render: (row) => format(new Date(row.started_at), "MMM d, HH:mm"),
    },
    {
      key: "duration",
      header: "Duration",
      render: (row) => {
        if (!row.completed_at) return <span className="text-gray-500">In progress</span>;
        const start = new Date(row.started_at).getTime();
        const end = new Date(row.completed_at).getTime();
        const seconds = Math.round((end - start) / 1000);
        if (seconds < 60) return `${seconds}s`;
        const minutes = Math.floor(seconds / 60);
        const remaining = seconds % 60;
        return `${minutes}m ${remaining}s`;
      },
    },
  ];

  // ── Loading state ──────────────────────────────────────────────────
  if (cyclesLoading && playbooksLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Learning Center</h1>
        <button
          onClick={() => triggerCycle.mutate()}
          disabled={triggerCycle.isPending}
          className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {triggerCycle.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Trigger Learning Cycle
        </button>
      </div>

      {/* Error banners */}
      {cyclesError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to load learning cycles.
        </div>
      )}
      {playbooksError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to load playbooks.
        </div>
      )}

      {/* Recent Learning Cycles */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-100">Recent Learning Cycles</h2>
        {cyclesLoading ? (
          <LoadingSpinner size="sm" className="py-12" />
        ) : (
          <DataTable
            columns={cycleColumns}
            data={cycles}
            keyExtractor={(row) => row.id}
            emptyMessage="No learning cycles yet. Trigger your first cycle to start improving."
          />
        )}
      </section>

      {/* Playbook Library */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-100">Playbook Library</h2>
        </div>

        {playbooksLoading ? (
          <LoadingSpinner size="sm" className="py-12" />
        ) : playbooks.length === 0 ? (
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center">
            <Brain className="mx-auto h-10 w-10 text-gray-600" />
            <p className="mt-3 text-sm text-gray-500">
              No playbooks yet. Playbooks are automatically created and refined as the learning
              agent analyzes incident patterns.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {playbooks.map((playbook) => (
              <PlaybookCard key={playbook.id} playbook={playbook} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Playbook Card ──────────────────────────────────────────────────────

function PlaybookCard({ playbook }: { playbook: Playbook }) {
  const successPercent = Math.round(playbook.success_rate * 100);

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      {/* Name + description */}
      <h3 className="font-semibold text-gray-100">{playbook.name}</h3>
      <p className="mt-1 text-sm text-gray-400">{playbook.description}</p>

      {/* Trigger conditions */}
      {playbook.trigger_conditions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {playbook.trigger_conditions.map((condition) => (
            <span
              key={condition}
              className="rounded-full bg-gray-800 px-2.5 py-0.5 text-xs text-gray-300"
            >
              {condition}
            </span>
          ))}
        </div>
      )}

      {/* Success rate bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Success rate</span>
          <span
            className={clsx(
              "font-medium tabular-nums",
              successPercent >= 80 ? "text-green-400" : successPercent >= 50 ? "text-yellow-400" : "text-red-400",
            )}
          >
            {successPercent}%
          </span>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-800">
          <div
            className={clsx(
              "h-full rounded-full transition-all",
              successPercent >= 80 ? "bg-green-500" : successPercent >= 50 ? "bg-yellow-500" : "bg-red-500",
            )}
            style={{ width: `${successPercent}%` }}
          />
        </div>
      </div>

      {/* Last used */}
      <p className="mt-3 text-xs text-gray-500">
        {playbook.last_used
          ? `Last used ${formatDistanceToNow(new Date(playbook.last_used), { addSuffix: true })}`
          : "Never used"}
      </p>
    </div>
  );
}
