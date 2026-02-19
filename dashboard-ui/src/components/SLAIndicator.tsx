import { Clock, AlertTriangle } from "lucide-react";
import clsx from "clsx";

interface SLAIndicatorProps {
  dueAt: string | null;
  breached: boolean;
}

export default function SLAIndicator({ dueAt, breached }: SLAIndicatorProps) {
  if (!dueAt) return <span className="text-xs text-gray-500">No SLA</span>;

  const due = new Date(dueAt);
  const now = new Date();
  const hoursRemaining = (due.getTime() - now.getTime()) / (1000 * 60 * 60);

  if (breached) {
    const hoursOverdue = Math.abs(hoursRemaining);
    return (
      <div className="flex items-center gap-1.5 text-red-400">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span className="text-xs font-medium">
          {hoursOverdue < 24
            ? `${hoursOverdue.toFixed(0)}h overdue`
            : `${(hoursOverdue / 24).toFixed(0)}d overdue`}
        </span>
      </div>
    );
  }

  const urgency =
    hoursRemaining < 4
      ? "text-red-400"
      : hoursRemaining < 24
        ? "text-yellow-400"
        : "text-gray-400";

  return (
    <div className={clsx("flex items-center gap-1.5", urgency)}>
      <Clock className="h-3.5 w-3.5" />
      <span className="text-xs">
        {hoursRemaining < 24
          ? `${hoursRemaining.toFixed(0)}h left`
          : `${(hoursRemaining / 24).toFixed(0)}d left`}
      </span>
    </div>
  );
}
