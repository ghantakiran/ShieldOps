import clsx from "clsx";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  icon?: React.ReactNode;
}

export default function MetricCard({ label, value, change, icon }: MetricCardProps) {
  const trend =
    change === undefined || change === 0
      ? "neutral"
      : change > 0
        ? "up"
        : "down";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-gray-400">{label}</p>
        {icon && <div className="text-gray-500">{icon}</div>}
      </div>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {change !== undefined && (
        <div
          className={clsx(
            "mt-1 flex items-center gap-1 text-xs font-medium",
            trend === "up" && "text-green-400",
            trend === "down" && "text-red-400",
            trend === "neutral" && "text-gray-500",
          )}
        >
          {trend === "up" && <TrendingUp className="h-3 w-3" />}
          {trend === "down" && <TrendingDown className="h-3 w-3" />}
          {trend === "neutral" && <Minus className="h-3 w-3" />}
          {change > 0 ? "+" : ""}
          {change.toFixed(1)}%
        </div>
      )}
    </div>
  );
}
