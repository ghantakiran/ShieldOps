import { TrendingDown, Clock, Zap, ArrowDown } from "lucide-react";
import clsx from "clsx";

interface Metric {
  label: string;
  value: string;
  change: string;
  improved: boolean;
  icon: typeof Clock;
}

const METRICS: Metric[] = [
  {
    label: "MTTD",
    value: "2.3m",
    change: "-67%",
    improved: true,
    icon: Clock,
  },
  {
    label: "MTTA",
    value: "45s",
    change: "-84%",
    improved: true,
    icon: Zap,
  },
  {
    label: "MTTR",
    value: "8.1m",
    change: "-73%",
    improved: true,
    icon: TrendingDown,
  },
];

interface MetricsBarProps {
  className?: string;
}

export default function MetricsBar({ className }: MetricsBarProps) {
  return (
    <div className={clsx("flex items-center gap-6", className)}>
      {METRICS.map((metric) => (
        <div key={metric.label} className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-800/60">
            <metric.icon className="h-4 w-4 text-gray-400" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-gray-100">{metric.value}</span>
              <span
                className={clsx(
                  "inline-flex items-center gap-0.5 text-xs font-medium",
                  metric.improved ? "text-emerald-400" : "text-red-400",
                )}
              >
                <ArrowDown className="h-3 w-3" />
                {metric.change}
              </span>
            </div>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">
              {metric.label}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
