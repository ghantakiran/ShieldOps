import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Wrench,
  X,
  Clock,
  Zap,
} from "lucide-react";
import clsx from "clsx";

interface Notification {
  id: string;
  type: "agent_complete" | "approval_required" | "alert" | "remediation" | "info";
  title: string;
  body: string;
  time: string;
  read: boolean;
  link?: string;
}

const DEMO_NOTIFICATIONS: Notification[] = [
  {
    id: "n1",
    type: "approval_required",
    title: "Approval Required",
    body: "Remediation Agent wants to rollback payment-service config to v2.3.9",
    time: "2 min ago",
    read: false,
    link: "/app/agent-task?run=run-004",
  },
  {
    id: "n2",
    type: "agent_complete",
    title: "Investigation Complete",
    body: "Root cause identified: DB connection pool exhaustion in payment-service",
    time: "12 min ago",
    read: false,
    link: "/app/agent-history",
  },
  {
    id: "n3",
    type: "remediation",
    title: "Auto-Remediation Applied",
    body: "Scaled k8s-prod-cluster-03 from 4 to 8 replicas to address high CPU",
    time: "28 min ago",
    read: false,
    link: "/app/remediations",
  },
  {
    id: "n4",
    type: "alert",
    title: "New P1 Alert",
    body: "Payment gateway latency exceeded 5s threshold in us-east-1",
    time: "42 min ago",
    read: true,
    link: "/app/war-room",
  },
  {
    id: "n5",
    type: "agent_complete",
    title: "Security Scan Complete",
    body: "Found 4 critical, 7 high vulnerabilities across 12 repositories",
    time: "1h ago",
    read: true,
    link: "/app/vulnerabilities",
  },
  {
    id: "n6",
    type: "info",
    title: "Playbook Updated",
    body: "Learning Agent updated restart-service playbook with new cooldown settings",
    time: "2h ago",
    read: true,
    link: "/app/playbooks",
  },
];

const TYPE_CONFIG = {
  agent_complete: { icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  approval_required: { icon: ShieldCheck, color: "text-amber-400", bg: "bg-amber-500/10" },
  alert: { icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10" },
  remediation: { icon: Wrench, color: "text-brand-400", bg: "bg-brand-500/10" },
  info: { icon: Zap, color: "text-blue-400", bg: "bg-blue-500/10" },
};

export default function NotificationDropdown() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState(DEMO_NOTIFICATIONS);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  function markAllRead() {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }

  function handleNotificationClick(n: Notification) {
    setNotifications((prev) =>
      prev.map((item) => (item.id === n.id ? { ...item, read: true } : item)),
    );
    setOpen(false);
    if (n.link) navigate(n.link);
  }

  function dismissNotification(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={() => setOpen(!open)}
        className="relative rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
            {unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 rounded-xl border border-gray-700 bg-gray-900 shadow-xl z-50">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
            <h3 className="text-sm font-semibold text-gray-200">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-10 text-center">
                <Bell className="h-8 w-8 text-gray-700 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No notifications</p>
              </div>
            ) : (
              notifications.map((n) => {
                const config = TYPE_CONFIG[n.type];
                const Icon = config.icon;
                return (
                  <button
                    key={n.id}
                    onClick={() => handleNotificationClick(n)}
                    className={clsx(
                      "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-800/50",
                      !n.read && "bg-gray-800/20",
                    )}
                  >
                    <div className={clsx("mt-0.5 rounded-lg p-1.5", config.bg)}>
                      <Icon className={clsx("h-3.5 w-3.5", config.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={clsx("text-sm font-medium", n.read ? "text-gray-400" : "text-gray-200")}>
                          {n.title}
                        </p>
                        {!n.read && <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.body}</p>
                      <span className="text-[10px] text-gray-600 mt-1 flex items-center gap-1">
                        <Clock className="h-2.5 w-2.5" />
                        {n.time}
                      </span>
                    </div>
                    <button
                      onClick={(e) => dismissNotification(e, n.id)}
                      className="mt-0.5 rounded p-1 text-gray-600 hover:bg-gray-700 hover:text-gray-400 transition-colors"
                      aria-label="Dismiss"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </button>
                );
              })
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="border-t border-gray-800 px-4 py-2">
              <button
                onClick={() => { setOpen(false); navigate("/app/agent-history"); }}
                className="w-full text-center text-xs text-gray-500 hover:text-brand-400 transition-colors py-1"
              >
                View all activity
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
