import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Search,
  ChevronDown,
  ChevronUp,
  Play,
  Pencil,
} from "lucide-react";
import clsx from "clsx";
import { get, post } from "../api/client";
import LoadingSpinner from "../components/LoadingSpinner";

interface PlaybookTrigger {
  alert_type: string;
  severity: string[];
}

interface PlaybookItem {
  name: string;
  version: string;
  description: string;
  trigger: PlaybookTrigger;
  decision_tree_count: number;
}

interface PlaybookDetail {
  name: string;
  version: string;
  description: string;
  trigger: PlaybookTrigger;
  investigation: Record<string, unknown>;
  remediation: Record<string, unknown>;
  validation: Record<string, unknown> | null;
}

interface PlaybooksResponse {
  playbooks: PlaybookItem[];
  total: number;
}

function alertTypeBadgeColor(alertType: string): string {
  const colors: Record<string, string> = {
    high_cpu: "bg-red-500/20 text-red-400",
    high_memory: "bg-orange-500/20 text-orange-400",
    disk_full: "bg-yellow-500/20 text-yellow-400",
    pod_crash_loop: "bg-purple-500/20 text-purple-400",
    service_down: "bg-red-500/20 text-red-400",
    high_latency: "bg-amber-500/20 text-amber-400",
  };
  return (
    colors[alertType] ?? "bg-blue-500/20 text-blue-400"
  );
}

function PlaybookCard({ playbook }: { playbook: PlaybookItem }) {
  const [expanded, setExpanded] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const { data: detail, isLoading: detailLoading } =
    useQuery({
      queryKey: ["playbook-detail", playbook.name],
      queryFn: () =>
        get<PlaybookDetail>(
          `/playbooks/${encodeURIComponent(playbook.name)}`
        ),
      enabled: expanded,
    });

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await post(
        `/playbooks/${encodeURIComponent(playbook.name)}/trigger`
      );
    } catch {
      // Trigger endpoint may not exist yet
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div
      className={clsx(
        "rounded-xl border border-gray-800 bg-gray-900",
        "transition-colors hover:border-gray-700"
      )}
    >
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-brand-400" />
              <h3 className="font-semibold text-gray-100">
                {playbook.name}
              </h3>
              <span className="text-xs text-gray-500">
                v{playbook.version}
              </span>
            </div>
            <p className="mt-1.5 text-sm text-gray-400">
              {playbook.description || "No description"}
            </p>
          </div>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className={clsx(
              "ml-3 flex items-center gap-1.5 rounded-lg",
              "border border-brand-600 px-3 py-1.5",
              "text-xs font-medium text-brand-400",
              "transition-colors hover:bg-brand-600/20",
              "disabled:opacity-40"
            )}
          >
            <Play className="h-3 w-3" />
            {triggering ? "..." : "Trigger"}
          </button>
        </div>

        {/* Badges */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className={clsx(
              "rounded-full px-2.5 py-0.5 text-xs font-medium",
              alertTypeBadgeColor(
                playbook.trigger.alert_type
              )
            )}
          >
            {playbook.trigger.alert_type}
          </span>
          {playbook.trigger.severity.map((sev) => (
            <span
              key={sev}
              className={clsx(
                "rounded-full px-2 py-0.5",
                "text-xs text-gray-400",
                "border border-gray-700"
              )}
            >
              {sev}
            </span>
          ))}
          <span className="text-xs text-gray-500">
            {playbook.decision_tree_count} decision
            {playbook.decision_tree_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Expand/Collapse Toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={clsx(
          "flex w-full items-center justify-center gap-1",
          "border-t border-gray-800 py-2 text-xs",
          "text-gray-500 transition-colors",
          "hover:bg-gray-800/50 hover:text-gray-300"
        )}
      >
        {expanded ? (
          <>
            <ChevronUp className="h-3.5 w-3.5" />
            Hide Details
          </>
        ) : (
          <>
            <ChevronDown className="h-3.5 w-3.5" />
            Show Details
          </>
        )}
      </button>

      {/* Expanded Detail */}
      {expanded && (
        <div className="border-t border-gray-800 p-5">
          {detailLoading ? (
            <LoadingSpinner size="sm" className="py-4" />
          ) : detail ? (
            <div className="space-y-4">
              {detail.investigation &&
                Object.keys(detail.investigation).length >
                  0 && (
                  <div>
                    <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Investigation
                    </h4>
                    <pre className="overflow-x-auto rounded-lg bg-gray-950 p-3 text-xs text-gray-300">
                      {JSON.stringify(
                        detail.investigation,
                        null,
                        2
                      )}
                    </pre>
                  </div>
                )}
              {detail.remediation &&
                Object.keys(detail.remediation).length >
                  0 && (
                  <div>
                    <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Remediation
                    </h4>
                    <pre className="overflow-x-auto rounded-lg bg-gray-950 p-3 text-xs text-gray-300">
                      {JSON.stringify(
                        detail.remediation,
                        null,
                        2
                      )}
                    </pre>
                  </div>
                )}
              {detail.validation && (
                <div>
                  <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Validation
                  </h4>
                  <pre className="overflow-x-auto rounded-lg bg-gray-950 p-3 text-xs text-gray-300">
                    {JSON.stringify(
                      detail.validation,
                      null,
                      2
                    )}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              Unable to load playbook details.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function Playbooks() {
  const [searchTerm, setSearchTerm] = useState("");
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["playbooks"],
    queryFn: () => get<PlaybooksResponse>("/playbooks"),
  });

  const playbooks = data?.playbooks ?? [];
  const filtered = searchTerm
    ? playbooks.filter(
        (pb) =>
          pb.name
            .toLowerCase()
            .includes(searchTerm.toLowerCase()) ||
          pb.description
            .toLowerCase()
            .includes(searchTerm.toLowerCase()) ||
          pb.trigger.alert_type
            .toLowerCase()
            .includes(searchTerm.toLowerCase())
      )
    : playbooks;

  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            Playbooks
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            View and manage remediation playbooks
          </p>
        </div>
        <button
          onClick={() => navigate("/playbooks/editor")}
          className={clsx(
            "flex items-center gap-2 rounded-lg",
            "bg-brand-600 px-4 py-2",
            "text-sm font-medium text-white",
            "transition-colors hover:bg-brand-700"
          )}
        >
          <Pencil className="h-4 w-4" />
          Edit Playbooks
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
        <input
          type="text"
          placeholder="Search playbooks by name, description, or alert type..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className={clsx(
            "w-full rounded-lg border border-gray-700",
            "bg-gray-800 py-2 pl-10 pr-4 text-sm",
            "text-gray-200 placeholder-gray-500",
            "focus:border-brand-500 focus:outline-none",
            "focus:ring-1 focus:ring-brand-500"
          )}
        />
      </div>

      {/* Results */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-800 bg-gray-900 py-16">
          <BookOpen className="h-10 w-10 text-gray-600" />
          <p className="mt-3 text-gray-400">
            {searchTerm
              ? "No playbooks match your search."
              : "No playbooks loaded."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filtered.map((pb) => (
            <PlaybookCard key={pb.name} playbook={pb} />
          ))}
        </div>
      )}
    </div>
  );
}
