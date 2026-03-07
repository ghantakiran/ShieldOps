import clsx from "clsx";
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";

export interface TaskTemplate {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  category: "suggested" | "incident" | "security" | "automation" | "compliance" | "cost";
  prompt: string;
  estimatedTime?: string;
  tags?: string[];
}

interface TaskCardProps {
  task: TaskTemplate;
  onSelect: (task: TaskTemplate) => void;
  compact?: boolean;
}

export default function TaskCard({ task, onSelect, compact = false }: TaskCardProps) {
  return (
    <button
      onClick={() => onSelect(task)}
      className={clsx(
        "group relative flex w-full text-left rounded-xl border border-gray-800 bg-gray-900/60 transition-all duration-200",
        "hover:border-gray-700 hover:bg-gray-800/60 hover:shadow-lg hover:shadow-black/20",
        "focus:outline-none focus:ring-2 focus:ring-brand-500/30",
        compact ? "p-3" : "p-4",
      )}
    >
      {/* Icon */}
      <div
        className={clsx(
          "flex shrink-0 items-center justify-center rounded-xl",
          compact ? "h-9 w-9 mr-3" : "h-10 w-10 mr-4",
          task.iconBg,
        )}
      >
        <task.icon className={clsx("h-5 w-5", task.iconColor)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <h3
          className={clsx(
            "font-semibold text-gray-200 group-hover:text-white transition-colors",
            compact ? "text-sm" : "text-sm",
          )}
        >
          {task.title}
        </h3>
        <p
          className={clsx(
            "text-gray-500 group-hover:text-gray-400 transition-colors line-clamp-2",
            compact ? "text-xs mt-0.5" : "text-xs mt-1",
          )}
        >
          {task.description}
        </p>

        {/* Tags & time */}
        {!compact && (task.tags || task.estimatedTime) && (
          <div className="mt-2 flex items-center gap-2">
            {task.estimatedTime && (
              <span className="text-[10px] font-medium text-gray-600">
                ~{task.estimatedTime}
              </span>
            )}
            {task.tags?.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-gray-800/80 px-2 py-0.5 text-[10px] text-gray-500"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Arrow */}
      <ArrowRight className="h-4 w-4 shrink-0 text-gray-700 transition-all group-hover:text-brand-400 group-hover:translate-x-0.5 mt-1" />
    </button>
  );
}
