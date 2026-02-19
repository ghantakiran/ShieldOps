import clsx from "clsx";

const VARIANT_CLASSES: Record<string, string> = {
  success: "bg-green-500/10 text-green-400 ring-green-500/20",
  warning: "bg-yellow-500/10 text-yellow-400 ring-yellow-500/20",
  error: "bg-red-500/10 text-red-400 ring-red-500/20",
  info: "bg-blue-500/10 text-blue-400 ring-blue-500/20",
  neutral: "bg-gray-500/10 text-gray-400 ring-gray-500/20",
};

// Map common statuses to variants
const STATUS_MAP: Record<string, string> = {
  healthy: "success",
  running: "success",
  completed: "success",
  approved: "success",
  idle: "info",
  pending: "info",
  pending_approval: "info",
  in_progress: "warning",
  executing: "warning",
  warning: "warning",
  degraded: "warning",
  error: "error",
  failed: "error",
  critical: "error",
  rolled_back: "error",
  offline: "neutral",
  low: "success",
  medium: "warning",
  high: "error",
};

interface StatusBadgeProps {
  status: string;
  variant?: keyof typeof VARIANT_CLASSES;
}

export default function StatusBadge({ status, variant }: StatusBadgeProps) {
  const v = variant ?? STATUS_MAP[status.toLowerCase()] ?? "neutral";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        VARIANT_CLASSES[v],
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
