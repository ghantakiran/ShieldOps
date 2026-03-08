import { NavLink, useLocation } from "react-router-dom";
import { Shield, ChevronRight, PanelLeftClose, PanelLeft } from "lucide-react";
import clsx from "clsx";
import { useEffect } from "react";
import { NAV_GROUPS } from "../config/products";
import { useSidebarStore } from "../store/sidebar";

export default function Sidebar() {
  const location = useLocation();
  const { collapsed, expandedGroups, toggleCollapsed, toggleGroup, expandGroup } =
    useSidebarStore();

  // Auto-expand the group containing the active route
  useEffect(() => {
    for (const group of NAV_GROUPS) {
      const isActive = group.items.some(
        (item) =>
          location.pathname === item.to ||
          (item.to !== "/app" && location.pathname.startsWith(item.to)),
      );
      const isAgentRoute =
        group.id === "agent-factory" &&
        (location.pathname.startsWith("/app/agent-task") ||
          location.pathname.startsWith("/app/war-room"));
      if (isActive || isAgentRoute) {
        expandGroup(group.id);
        break;
      }
    }
  }, [location.pathname, expandGroup]);

  return (
    <aside
      className={clsx(
        "flex h-full flex-col border-r border-gray-800 bg-gray-900 transition-all duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between px-4 py-5">
        <div className="flex items-center gap-2">
          <Shield className="h-7 w-7 shrink-0 text-brand-500" />
          {!collapsed && (
            <span className="text-lg font-semibold tracking-tight">ShieldOps</span>
          )}
        </div>
        <button
          onClick={toggleCollapsed}
          className="rounded p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-2 py-1">
        {NAV_GROUPS.map((group) => {
          const isExpanded = expandedGroups.has(group.id);
          const isGroupActive = group.items.some(
            (item) =>
              location.pathname === item.to ||
              (item.to !== "/app" && location.pathname.startsWith(item.to)),
          );

          return (
            <div key={group.id} className="mb-1">
              {/* Group header */}
              <button
                onClick={() => toggleGroup(group.id)}
                className={clsx(
                  "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                  isGroupActive
                    ? `${group.color} bg-gray-800/50`
                    : "text-gray-500 hover:text-gray-400",
                )}
                aria-expanded={isExpanded}
                aria-label={`${group.label} section`}
                title={collapsed ? group.label : undefined}
              >
                <ChevronRight
                  className={clsx(
                    "h-3 w-3 shrink-0 transition-transform duration-200",
                    isExpanded && "rotate-90",
                  )}
                />
                {!collapsed && <span className="truncate">{group.label}</span>}
              </button>

              {/* Group items */}
              {isExpanded && (
              <div className="mt-0.5 space-y-0.5">
                  {group.items.map(({ to, icon: Icon, label }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === "/app"}
                      className={({ isActive }) =>
                        clsx(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                          collapsed && "justify-center px-2",
                          isActive
                            ? "bg-brand-600/20 text-brand-400"
                            : "text-gray-400 hover:bg-gray-800 hover:text-gray-200",
                        )
                      }
                      title={collapsed ? label : undefined}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {!collapsed && <span className="truncate">{label}</span>}
                    </NavLink>
                  ))}
              </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-800 px-4 py-3">
        {!collapsed && <p className="text-xs text-gray-500">ShieldOps v0.1.0</p>}
      </div>
    </aside>
  );
}
