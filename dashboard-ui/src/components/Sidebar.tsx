import { NavLink } from "react-router-dom";
import {
  Shield,
  Search,
  Wrench,
  ShieldAlert,
  DollarSign,
  Brain,
  BarChart3,
  Gauge,
  Settings,
  LayoutDashboard,
  Bug,
  FileText,
  BookOpen,
  Users,
  CreditCard,
  HeartPulse,
  Rocket,
  Store,
  Layers,
  Webhook,
  ShieldCheck,
} from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/onboarding", icon: Rocket, label: "Onboarding" },
  { to: "/", icon: LayoutDashboard, label: "Fleet Overview" },
  { to: "/investigations", icon: Search, label: "Investigations" },
  { to: "/incidents", icon: Layers, label: "Incidents" },
  { to: "/remediations", icon: Wrench, label: "Remediations" },
  { to: "/security", icon: ShieldAlert, label: "Security" },
  { to: "/vulnerabilities", icon: Bug, label: "Vulnerabilities" },
  { to: "/marketplace", icon: Store, label: "Marketplace" },
  { to: "/playbooks", icon: BookOpen, label: "Playbooks" },
  { to: "/cost", icon: DollarSign, label: "Cost" },
  { to: "/learning", icon: Brain, label: "Learning" },
  { to: "/analytics", icon: BarChart3, label: "Analytics" },
  { to: "/agent-performance", icon: Gauge, label: "Agent Performance" },
  { to: "/audit-log", icon: FileText, label: "Audit Log" },
  { to: "/compliance", icon: ShieldCheck, label: "Compliance" },
  { to: "/billing", icon: CreditCard, label: "Billing" },
  { to: "/system-health", icon: HeartPulse, label: "System Health" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/users", icon: Users, label: "Users" },
] as const;

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-60 flex-col border-r border-gray-800 bg-gray-900">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5">
        <Shield className="h-7 w-7 text-brand-500" />
        <span className="text-lg font-semibold tracking-tight">ShieldOps</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
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
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-800 px-5 py-3">
        <p className="text-xs text-gray-500">ShieldOps v0.1.0</p>
      </div>
    </aside>
  );
}
