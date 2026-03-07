import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Shield, ChevronRight, X } from "lucide-react";
import clsx from "clsx";
import { NAV_GROUPS } from "../config/products";
import { useSidebarStore } from "../store/sidebar";

interface MobileSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function MobileSidebar({ isOpen, onClose }: MobileSidebarProps) {
  const location = useLocation();
  const { expandedGroups, toggleGroup } = useSidebarStore();

  // Close on navigation
  useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <aside className="absolute left-0 top-0 h-full w-72 animate-slide-in-left border-r border-gray-800 bg-gray-900">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2">
            <Shield className="h-7 w-7 text-brand-500" />
            <span className="text-lg font-semibold tracking-tight">ShieldOps</span>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-1">
          {NAV_GROUPS.map((group) => {
            const isExpanded = expandedGroups.has(group.id);
            const isGroupActive = group.items.some(
              (item) =>
                location.pathname === item.to ||
                (item.to !== "/app" && location.pathname.startsWith(item.to)),
            );

            return (
              <div key={group.id} className="mb-1">
                <button
                  onClick={() => toggleGroup(group.id)}
                  className={clsx(
                    "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors",
                    isGroupActive
                      ? `${group.color} bg-gray-800/50`
                      : "text-gray-500 hover:text-gray-400",
                  )}
                >
                  <ChevronRight
                    className={clsx(
                      "h-3 w-3 shrink-0 transition-transform duration-200",
                      isExpanded && "rotate-90",
                    )}
                  />
                  <span>{group.label}</span>
                </button>

                {isExpanded && (
                <div className="mt-0.5 space-y-0.5">
                  {group.items.map(({ to, icon: Icon, label }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === "/app"}
                      className={({ isActive }) =>
                        clsx(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-brand-600/20 text-brand-400"
                            : "text-gray-400 hover:bg-gray-800 hover:text-gray-200",
                        )
                      }
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </NavLink>
                  ))}
                </div>
                )}
              </div>
            );
          })}
        </nav>
      </aside>
    </div>
  );
}
