import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";
import clsx from "clsx";
import { useToastStore, type ToastType } from "../store/toast";

const ICONS: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const COLORS: Record<ToastType, string> = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  error: "border-red-500/30 bg-red-500/10 text-red-400",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  info: "border-brand-500/30 bg-brand-500/10 text-brand-400",
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = ICONS[toast.type];
        return (
          <div
            key={toast.id}
            className={clsx(
              "flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg animate-slide-in-right",
              COLORS[toast.type],
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <p className="text-sm font-medium text-gray-200">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="ml-2 shrink-0 text-gray-500 hover:text-gray-300"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
