import { useState } from "react";
import {
  Plug,
  Search,
  AlertTriangle,
  ArrowUpDown,
  ExternalLink,
  Settings,
  Activity,
  MessageSquare,
  Bell,
  Shield,
  GitBranch,
  Database,
  BarChart3,
  FileText,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ────────────────────────────────────────────────────────────

type IntegrationStatus = "connected" | "warning" | "disconnected" | "available";
type IntegrationCategory = "communication" | "monitoring" | "security" | "devops" | "ticketing" | "cloud";

interface Integration {
  id: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  status: IntegrationStatus;
  icon: LucideIcon;
  iconColor: string;
  lastSync?: string;
  eventsToday?: number;
  direction: "inbound" | "outbound" | "bidirectional";
  features: string[];
  error?: string;
}

// ── Demo Data ────────────────────────────────────────────────────────

const INTEGRATIONS: Integration[] = [
  {
    id: "slack",
    name: "Slack",
    description: "Bi-directional alerts, ChatOps commands, incident notifications, and approval workflows",
    category: "communication",
    status: "connected",
    icon: MessageSquare,
    iconColor: "text-sky-400",
    lastSync: "< 1 min ago",
    eventsToday: 847,
    direction: "bidirectional",
    features: ["ChatOps commands", "Alert routing", "Approval workflows", "Incident threads", "Status updates"],
  },
  {
    id: "teams",
    name: "Microsoft Teams",
    description: "Enterprise messaging with adaptive cards, approval buttons, and incident channels",
    category: "communication",
    status: "connected",
    icon: MessageSquare,
    iconColor: "text-brand-400",
    lastSync: "2 min ago",
    eventsToday: 234,
    direction: "bidirectional",
    features: ["Adaptive cards", "Approval buttons", "Incident channels", "Bot commands"],
  },
  {
    id: "pagerduty",
    name: "PagerDuty",
    description: "On-call scheduling, incident escalation, and acknowledgment sync",
    category: "communication",
    status: "connected",
    icon: Bell,
    iconColor: "text-emerald-400",
    lastSync: "< 1 min ago",
    eventsToday: 56,
    direction: "bidirectional",
    features: ["On-call sync", "Escalation policies", "Auto-acknowledge", "Incident creation", "Schedule import"],
  },
  {
    id: "jira",
    name: "Jira",
    description: "Automated ticket creation, status sync, and remediation tracking",
    category: "ticketing",
    status: "connected",
    icon: FileText,
    iconColor: "text-sky-400",
    lastSync: "5 min ago",
    eventsToday: 128,
    direction: "bidirectional",
    features: ["Auto-ticket creation", "Status sync", "Custom fields", "Sprint integration", "Bulk updates"],
  },
  {
    id: "github",
    name: "GitHub",
    description: "PR-triggered scans, deployment events, SBOM analysis, and IaC validation",
    category: "devops",
    status: "connected",
    icon: GitBranch,
    iconColor: "text-gray-300",
    lastSync: "3 min ago",
    eventsToday: 312,
    direction: "bidirectional",
    features: ["PR scanning", "Deploy webhooks", "SBOM analysis", "IaC validation", "Actions integration"],
  },
  {
    id: "datadog",
    name: "Datadog",
    description: "Metric ingestion, alert forwarding, and dashboard linking",
    category: "monitoring",
    status: "connected",
    icon: BarChart3,
    iconColor: "text-amber-400",
    lastSync: "< 1 min ago",
    eventsToday: 1423,
    direction: "inbound",
    features: ["Metric ingestion", "Alert forwarding", "APM traces", "Log forwarding", "Dashboard deep links"],
  },
  {
    id: "splunk",
    name: "Splunk",
    description: "Log search, SIEM correlation, and security event forwarding",
    category: "security",
    status: "connected",
    icon: Search,
    iconColor: "text-emerald-400",
    lastSync: "1 min ago",
    eventsToday: 567,
    direction: "bidirectional",
    features: ["Log search", "SIEM alerts", "Saved searches", "Event correlation", "Report export"],
  },
  {
    id: "crowdstrike",
    name: "CrowdStrike",
    description: "Endpoint detection, threat intelligence, and IOC enrichment",
    category: "security",
    status: "warning",
    icon: Shield,
    iconColor: "text-red-400",
    lastSync: "15 min ago",
    eventsToday: 89,
    direction: "inbound",
    features: ["Endpoint telemetry", "Threat intel", "IOC enrichment", "Incident response"],
    error: "API rate limit reached — reduced polling",
  },
  {
    id: "servicenow",
    name: "ServiceNow",
    description: "ITSM integration with change requests, incidents, and CMDB sync",
    category: "ticketing",
    status: "available",
    icon: Database,
    iconColor: "text-sky-400",
    direction: "bidirectional",
    features: ["Change requests", "Incident sync", "CMDB import", "ITIL workflows"],
  },
  {
    id: "opsgenie",
    name: "OpsGenie",
    description: "Alert management, on-call routing, and incident orchestration",
    category: "communication",
    status: "available",
    icon: Bell,
    iconColor: "text-brand-400",
    direction: "bidirectional",
    features: ["Alert routing", "On-call management", "Heartbeat monitoring", "Escalation"],
  },
  {
    id: "prometheus",
    name: "Prometheus",
    description: "Metric scraping, alertmanager integration, and custom queries",
    category: "monitoring",
    status: "connected",
    icon: Activity,
    iconColor: "text-orange-400",
    lastSync: "< 1 min ago",
    eventsToday: 2340,
    direction: "inbound",
    features: ["Metric scraping", "AlertManager sync", "PromQL queries", "Recording rules"],
  },
  {
    id: "sentinel",
    name: "Microsoft Sentinel",
    description: "SIEM event ingestion, analytics rules, and automated response",
    category: "security",
    status: "available",
    icon: Shield,
    iconColor: "text-sky-400",
    direction: "bidirectional",
    features: ["Event ingestion", "Analytics rules", "Playbook triggers", "Threat hunting"],
  },
];

const CATEGORIES: { key: IntegrationCategory | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "communication", label: "Communication" },
  { key: "monitoring", label: "Monitoring" },
  { key: "security", label: "Security" },
  { key: "devops", label: "DevOps" },
  { key: "ticketing", label: "Ticketing" },
  { key: "cloud", label: "Cloud" },
];

const STATUS_CONFIG: Record<IntegrationStatus, { dot: string; label: string; bg: string; text: string }> = {
  connected: { dot: "bg-emerald-400", label: "Connected", bg: "bg-emerald-500/10", text: "text-emerald-400" },
  warning: { dot: "bg-amber-400", label: "Warning", bg: "bg-amber-500/10", text: "text-amber-400" },
  disconnected: { dot: "bg-red-400", label: "Disconnected", bg: "bg-red-500/10", text: "text-red-400" },
  available: { dot: "bg-gray-500", label: "Available", bg: "bg-gray-500/10", text: "text-gray-400" },
};

const DIRECTION_LABELS: Record<string, string> = {
  inbound: "Inbound",
  outbound: "Outbound",
  bidirectional: "Bi-directional",
};

// ── Component ────────────────────────────────────────────────────────

export default function EnterpriseIntegrations() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<IntegrationCategory | "all">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = INTEGRATIONS.filter((i) => {
    if (categoryFilter !== "all" && i.category !== categoryFilter) return false;
    if (searchQuery && !i.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: INTEGRATIONS.length,
    connected: INTEGRATIONS.filter((i) => i.status === "connected").length,
    eventsToday: INTEGRATIONS.reduce((sum, i) => sum + (i.eventsToday || 0), 0),
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-white">
            <Plug className="h-5 w-5 text-brand-400" />
            Enterprise Integrations
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Connect your tools for bi-directional communication, alerting, and automated workflows
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-gray-800/60 px-3 py-1.5 text-xs text-gray-300">
            <span className="font-bold text-white">{stats.total}</span> integrations
          </span>
          <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
            <span className="font-bold">{stats.connected}</span> connected
          </span>
          <span className="rounded-lg bg-brand-500/10 px-3 py-1.5 text-xs text-brand-400">
            <span className="font-bold">{stats.eventsToday.toLocaleString()}</span> events today
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search integrations..."
            aria-label="Search integrations"
            className="w-full rounded-xl border border-gray-700 bg-gray-800/50 py-2.5 pl-10 pr-4 text-sm text-gray-200 placeholder-gray-500 focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setCategoryFilter(cat.key)}
              aria-pressed={categoryFilter === cat.key}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                categoryFilter === cat.key
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-500 hover:bg-gray-800 hover:text-gray-300",
              )}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Integrations grid */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((integration) => {
          const Icon = integration.icon;
          const status = STATUS_CONFIG[integration.status];
          const isExpanded = expandedId === integration.id;

          return (
            <div
              key={integration.id}
              className={clsx(
                "rounded-xl border bg-gray-900/40 p-5 transition-all",
                integration.status === "available"
                  ? "border-dashed border-gray-700 hover:border-gray-600"
                  : "border-gray-800/50 hover:border-gray-700",
              )}
            >
              {/* Top row */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-800/60">
                    <Icon className={clsx("h-5 w-5", integration.iconColor)} />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-gray-200">
                      {integration.name}
                    </h3>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-500">
                        {integration.category}
                      </span>
                      <ArrowUpDown className="h-2.5 w-2.5 text-gray-600" />
                      <span className="text-[10px] text-gray-500">
                        {DIRECTION_LABELS[integration.direction]}
                      </span>
                    </div>
                  </div>
                </div>
                <span
                  className={clsx(
                    "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                    status.bg,
                    status.text,
                  )}
                >
                  <span className={clsx("h-1.5 w-1.5 rounded-full", status.dot)} />
                  {status.label}
                </span>
              </div>

              {/* Description */}
              <p className="mt-3 text-xs leading-relaxed text-gray-400">
                {integration.description}
              </p>

              {/* Error */}
              {integration.error && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-400">
                  <AlertTriangle className="h-3 w-3 shrink-0" />
                  {integration.error}
                </p>
              )}

              {/* Stats */}
              {integration.status !== "available" && (
                <div className="mt-3 flex items-center gap-4 text-[10px] text-gray-600">
                  {integration.lastSync && <span>Synced {integration.lastSync}</span>}
                  {integration.eventsToday !== undefined && (
                    <span>{integration.eventsToday.toLocaleString()} events today</span>
                  )}
                </div>
              )}

              {/* Features toggle */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : integration.id)}
                className="mt-3 text-xs font-medium text-gray-500 transition-colors hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50 rounded"
                aria-expanded={isExpanded}
              >
                {isExpanded ? "Hide features" : "Show features"}
              </button>

              {isExpanded && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {integration.features.map((f) => (
                    <span
                      key={f}
                      className="rounded-md border border-gray-800 bg-gray-800/40 px-2 py-0.5 text-[10px] text-gray-400"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div className="mt-4 flex items-center gap-2 border-t border-gray-800/50 pt-3">
                {integration.status === "available" ? (
                  <button className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50">
                    <Plug className="h-3 w-3" />
                    Connect
                  </button>
                ) : (
                  <>
                    <button
                      className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                      aria-label={`Configure ${integration.name}`}
                    >
                      <Settings className="h-3 w-3" />
                      Configure
                    </button>
                    <button
                      className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                      aria-label={`View ${integration.name} docs`}
                    >
                      <ExternalLink className="h-3 w-3" />
                      Docs
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="py-16 text-center">
          <Plug className="mx-auto mb-3 h-10 w-10 text-gray-700" />
          <p className="text-sm text-gray-500">No integrations match your filters.</p>
        </div>
      )}
    </div>
  );
}
