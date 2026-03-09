import { useState } from "react";
import {
  Server,
  Search,
  Plus,
  Settings,
  RefreshCw,
  Database,
  Globe,
  FileText,
  Zap,
  AlertTriangle,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ────────────────────────────────────────────────────────────
interface MCPServer {
  id: string;
  name: string;
  provider: string;
  description: string;
  status: "connected" | "degraded" | "disconnected";
  icon: LucideIcon;
  iconColor: string;
  lastPing: string;
  error?: string;
  tools: string[];
}

// ── Demo Data ────────────────────────────────────────────────────────
const DEMO_MCP_SERVERS: MCPServer[] = [
  {
    id: "fs",
    name: "Filesystem Server",
    provider: "@anthropic/mcp-filesystem",
    description: "Read, write, and search files in project directories",
    status: "connected",
    icon: FileText,
    iconColor: "text-brand-400",
    lastPing: "2s ago",
    tools: ["read_file", "write_file", "list_directory", "search_files", "get_file_info"],
  },
  {
    id: "pg",
    name: "PostgreSQL Server",
    provider: "@anthropic/mcp-postgres",
    description: "Query and manage PostgreSQL databases",
    status: "connected",
    icon: Database,
    iconColor: "text-sky-400",
    lastPing: "5s ago",
    tools: ["query", "list_tables", "describe_table", "insert", "update", "delete", "create_table", "run_migration"],
  },
  {
    id: "k8s",
    name: "Kubernetes Server",
    provider: "@shieldops/mcp-kubernetes",
    description: "Manage Kubernetes clusters, pods, deployments, and services",
    status: "connected",
    icon: Server,
    iconColor: "text-brand-400",
    lastPing: "3s ago",
    tools: ["get_pods", "get_deployments", "get_services", "get_nodes", "describe_pod", "get_logs", "scale_deployment", "rollout_restart", "apply_manifest", "get_events", "get_namespaces", "get_configmaps"],
  },
  {
    id: "cw",
    name: "AWS CloudWatch Server",
    provider: "@shieldops/mcp-aws-cloudwatch",
    description: "Query CloudWatch metrics, logs, and alarms",
    status: "connected",
    icon: Globe,
    iconColor: "text-amber-400",
    lastPing: "8s ago",
    tools: ["get_metric_data", "query_logs", "list_alarms", "get_log_groups", "put_metric_alarm", "describe_alarms"],
  },
  {
    id: "slack",
    name: "Slack Server",
    provider: "@anthropic/mcp-slack",
    description: "Send messages, manage channels, and read threads",
    status: "degraded",
    icon: Zap,
    iconColor: "text-sky-400",
    lastPing: "45s ago",
    tools: ["send_message", "list_channels", "read_thread", "add_reaction"],
  },
  {
    id: "pd",
    name: "PagerDuty Server",
    provider: "@shieldops/mcp-pagerduty",
    description: "Manage incidents, on-call schedules, and escalations",
    status: "disconnected",
    icon: AlertTriangle,
    iconColor: "text-red-400",
    lastPing: "5m ago",
    error: "Authentication token expired",
    tools: ["list_incidents", "create_incident", "acknowledge_incident", "resolve_incident", "get_oncall"],
  },
  {
    id: "gh",
    name: "GitHub Server",
    provider: "@anthropic/mcp-github",
    description: "Manage repositories, issues, pull requests, and actions",
    status: "connected",
    icon: Globe,
    iconColor: "text-gray-300",
    lastPing: "4s ago",
    tools: ["list_repos", "create_issue", "list_prs", "merge_pr", "get_actions", "create_branch", "get_commits", "review_pr", "list_releases", "create_release"],
  },
  {
    id: "splunk",
    name: "Splunk Server",
    provider: "@shieldops/mcp-splunk",
    description: "Search logs, manage saved searches, and query dashboards",
    status: "connected",
    icon: Search,
    iconColor: "text-emerald-400",
    lastPing: "12s ago",
    tools: ["search", "list_saved_searches", "get_dashboard", "export_results"],
  },
];

const STATUS_CONFIG = {
  connected: { dot: "bg-emerald-400", bg: "bg-emerald-500/10", text: "text-emerald-400", label: "Connected" },
  degraded: { dot: "bg-amber-400", bg: "bg-amber-500/10", text: "text-amber-400", label: "Degraded" },
  disconnected: { dot: "bg-red-400", bg: "bg-red-500/10", text: "text-red-400", label: "Disconnected" },
};

// ── Component ────────────────────────────────────────────────────────
export default function MCPServers() {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedServer, setExpandedServer] = useState<string | null>(null);

  const filtered = DEMO_MCP_SERVERS.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.provider.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const stats = {
    total: DEMO_MCP_SERVERS.length,
    connected: DEMO_MCP_SERVERS.filter((s) => s.status === "connected").length,
    tools: DEMO_MCP_SERVERS.reduce((sum, s) => sum + s.tools.length, 0),
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-white">
            <Server className="h-5 w-5 text-brand-400" />
            MCP Servers
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage Model Context Protocol server connections and tools
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-gray-800/60 px-3 py-1.5 text-xs text-gray-300">
            <span className="font-bold text-white">{stats.total}</span> servers
          </span>
          <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
            <span className="font-bold">{stats.connected}</span> connected
          </span>
          <span className="rounded-lg bg-brand-500/10 px-3 py-1.5 text-xs text-brand-400">
            <span className="font-bold">{stats.tools}</span> tools available
          </span>
        </div>
      </div>

      {/* Action bar */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search servers..."
            aria-label="Search MCP servers"
            className="w-full rounded-xl border border-gray-700 bg-gray-800/50 py-2.5 pl-10 pr-4 text-sm text-gray-200 placeholder-gray-500 focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          aria-label="Add MCP server"
        >
          <Plus className="h-4 w-4" />
          Add Server
        </button>
      </div>

      {/* Server cards */}
      <div className="grid gap-4 md:grid-cols-2">
        {filtered.map((server) => {
          const Icon = server.icon;
          const status = STATUS_CONFIG[server.status];
          const isExpanded = expandedServer === server.id;

          return (
            <div
              key={server.id}
              className="rounded-xl border border-gray-800/50 bg-gray-900/40 p-5 transition-all hover:border-gray-700"
            >
              {/* Top row */}
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-800/60">
                    <Icon className={clsx("h-5 w-5", server.iconColor)} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-gray-200">{server.name}</h3>
                      <span className={clsx("h-2 w-2 rounded-full", status.dot)} />
                    </div>
                    <p className="text-xs text-gray-600">{server.provider}</p>
                  </div>
                </div>
                <span
                  className={clsx(
                    "rounded-full px-2.5 py-1 text-xs font-medium",
                    status.bg,
                    status.text,
                  )}
                >
                  {status.label}
                </span>
              </div>

              {/* Description */}
              <p className="mt-3 text-sm text-gray-400">{server.description}</p>

              {/* Error */}
              {server.error && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-red-400">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {server.error}
                </p>
              )}

              {/* Meta */}
              <div className="mt-3 flex items-center gap-4 text-xs text-gray-600">
                <span>{server.tools.length} tools</span>
                <span>Last ping: {server.lastPing}</span>
              </div>

              {/* Tools toggle */}
              <button
                onClick={() => setExpandedServer(isExpanded ? null : server.id)}
                className="mt-3 flex items-center gap-1 text-xs font-medium text-gray-500 transition-colors hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50 rounded"
                aria-expanded={isExpanded}
                aria-label={`${isExpanded ? "Hide" : "Show"} tools for ${server.name}`}
              >
                <ChevronDown
                  className={clsx(
                    "h-3.5 w-3.5 transition-transform",
                    isExpanded && "rotate-180",
                  )}
                />
                {isExpanded ? "Hide tools" : "Show tools"}
              </button>

              {isExpanded && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {server.tools.map((tool) => (
                    <span
                      key={tool}
                      className="rounded-md border border-gray-800 bg-gray-800/40 px-2 py-0.5 font-mono text-xs text-gray-400"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div className="mt-4 flex items-center gap-2 border-t border-gray-800/50 pt-3">
                <button
                  className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  aria-label={`Configure ${server.name}`}
                >
                  <Settings className="h-3.5 w-3.5" />
                  Configure
                </button>
                <button
                  className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  aria-label={`Reconnect ${server.name}`}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Reconnect
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="py-16 text-center">
          <Server className="mx-auto mb-3 h-10 w-10 text-gray-700" />
          <p className="text-sm text-gray-500">No servers match your search.</p>
        </div>
      )}
    </div>
  );
}
