import { Link, useLocation } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";

// ── Route label overrides ────────────────────────────────────────

const ROUTE_LABELS: Record<string, string> = {
  app: "Dashboard",
  "agent-task": "Agent Task",
  "agent-history": "Agent History",
  "war-room": "War Rooms",
  fleet: "Fleet Overview",
  investigations: "Investigations",
  remediations: "Remediations",
  security: "Security",
  vulnerabilities: "Vulnerabilities",
  cost: "Cost",
  learning: "Learning",
  analytics: "Analytics",
  "agent-performance": "Agent Performance",
  marketplace: "Marketplace",
  playbooks: "Playbooks",
  editor: "Editor",
  "audit-log": "Audit Log",
  compliance: "Compliance",
  billing: "Billing",
  "system-health": "System Health",
  settings: "Settings",
  users: "Users",
  incidents: "Incidents",
  predictions: "Predictions",
  capacity: "Capacity",
  "infra-as-code": "Infra as Code",
  onboarding: "Onboarding",
  pipeline: "Pipeline",
  "api-keys": "API Keys",
  workflows: "Workflows",
  schedules: "Schedules",
  timeline: "Timeline",
};

function getLabel(segment: string): string {
  return ROUTE_LABELS[segment] ?? segment.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function isId(segment: string): boolean {
  // UUIDs, numeric IDs, or common ID patterns
  return /^[0-9a-f-]{8,}$/i.test(segment) || /^\d+$/.test(segment);
}

export default function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  // Only show breadcrumbs for paths deeper than /app
  if (segments.length <= 1) return null;

  const crumbs = segments.map((segment, index) => {
    const path = "/" + segments.slice(0, index + 1).join("/");
    const isLast = index === segments.length - 1;
    const label = isId(segment) ? segment.slice(0, 8) + "..." : getLabel(segment);

    return { segment, path, label, isLast };
  });

  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1 text-sm">
      <Link
        to="/app"
        className="flex items-center text-gray-500 transition-colors hover:text-gray-300"
      >
        <Home className="h-3.5 w-3.5" />
      </Link>

      {crumbs.slice(1).map(({ path, label, isLast }) => (
        <span key={path} className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5 text-gray-600" />
          {isLast ? (
            <span className="font-medium text-gray-200">{label}</span>
          ) : (
            <Link
              to={path}
              className="text-gray-500 transition-colors hover:text-gray-300"
            >
              {label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
