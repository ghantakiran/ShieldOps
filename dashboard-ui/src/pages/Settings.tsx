import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  Bell,
  Key,
  ExternalLink,
  Copy,
  Check,
  MessageSquare,
  Siren,
  Mail,
  Webhook,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";
import { get } from "../api/client";
import type { Agent } from "../api/types";
import type { Column } from "../components/DataTable";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import { useAuthStore } from "../store/auth";

type SettingsTab = "agents" | "notifications" | "api";

const TABS: { key: SettingsTab; label: string; icon: React.ReactNode }[] = [
  { key: "agents", label: "Agents", icon: <Bot className="h-4 w-4" /> },
  { key: "notifications", label: "Notifications", icon: <Bell className="h-4 w-4" /> },
  { key: "api", label: "API", icon: <Key className="h-4 w-4" /> },
];

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("agents");

  return (
    <div className="space-y-6">
      {/* Header */}
      <h1 className="text-2xl font-bold text-gray-100">Settings</h1>

      {/* Tab navigation */}
      <div className="flex gap-1 rounded-lg bg-gray-900 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              "flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "bg-gray-800 text-gray-100"
                : "text-gray-400 hover:text-gray-200",
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "agents" && <AgentsTab />}
      {activeTab === "notifications" && <NotificationsTab />}
      {activeTab === "api" && <ApiTab />}
    </div>
  );
}

// ── Agents Tab ───────────────────────────────────────────────────────────

function AgentsTab() {
  const {
    data: agents = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: () => get<Agent[]>("/agents/"),
  });

  const agentColumns: Column<Agent>[] = [
    {
      key: "id",
      header: "ID",
      render: (row) => (
        <span className="font-mono text-xs text-gray-400" title={row.id}>
          {row.id.slice(0, 8)}...
        </span>
      ),
    },
    {
      key: "agent_type",
      header: "Type",
      render: (row) => <span className="capitalize text-gray-200">{row.agent_type}</span>,
    },
    {
      key: "environment",
      header: "Environment",
      render: (row) => <span className="text-gray-300">{row.environment}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "last_heartbeat",
      header: "Last Heartbeat",
      render: (row) =>
        row.last_heartbeat ? (
          <span className="text-gray-400">
            {formatDistanceToNow(new Date(row.last_heartbeat), { addSuffix: true })}
          </span>
        ) : (
          <span className="text-gray-600">Never</span>
        ),
    },
  ];

  if (isLoading) {
    return <LoadingSpinner size="sm" className="py-12" />;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        Failed to load agents.
      </div>
    );
  }

  return (
    <DataTable
      columns={agentColumns}
      data={agents}
      keyExtractor={(row) => row.id}
      emptyMessage="No agents registered yet."
    />
  );
}

// ── Notifications Tab ────────────────────────────────────────────────────

interface NotificationChannel {
  name: string;
  description: string;
  configured: boolean;
  icon: React.ReactNode;
}

const CHANNELS: NotificationChannel[] = [
  {
    name: "Slack",
    description: "Send alerts and incident updates to Slack channels",
    configured: true,
    icon: <MessageSquare className="h-5 w-5" />,
  },
  {
    name: "PagerDuty",
    description: "Escalate critical incidents to on-call engineers",
    configured: true,
    icon: <Siren className="h-5 w-5" />,
  },
  {
    name: "Email",
    description: "Email notifications for daily digests and reports",
    configured: false,
    icon: <Mail className="h-5 w-5" />,
  },
  {
    name: "Webhook",
    description: "Custom HTTP webhooks for third-party integrations",
    configured: false,
    icon: <Webhook className="h-5 w-5" />,
  },
];

function NotificationsTab() {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900">
      <div className="border-b border-gray-800 px-5 py-4">
        <h3 className="font-semibold text-gray-100">Notification Channels</h3>
        <p className="mt-1 text-sm text-gray-500">
          Configure how ShieldOps alerts your team about incidents and agent actions.
        </p>
      </div>
      <ul className="divide-y divide-gray-800">
        {CHANNELS.map((channel) => (
          <li key={channel.name} className="flex items-center gap-4 px-5 py-4">
            <div className="text-gray-400">{channel.icon}</div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-200">{channel.name}</p>
              <p className="text-xs text-gray-500">{channel.description}</p>
            </div>
            <div className="flex items-center gap-2">
              <div
                className={clsx(
                  "h-2 w-2 rounded-full",
                  channel.configured ? "bg-green-400" : "bg-gray-600",
                )}
              />
              <span className="text-xs text-gray-400">
                {channel.configured ? "Configured" : "Not configured"}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── API Tab ──────────────────────────────────────────────────────────────

function ApiTab() {
  const { token } = useAuthStore();
  const [copied, setCopied] = useState(false);

  const baseUrl = `${window.location.origin}/api/v1`;
  const docsUrl = `${baseUrl}/docs`;
  const openApiUrl = `${baseUrl}/openapi.json`;

  function maskToken(t: string | null): string {
    if (!t) return "No token available";
    if (t.length <= 12) return "****";
    return `${t.slice(0, 6)}${"*".repeat(20)}${t.slice(-6)}`;
  }

  async function copyToken() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may fail in non-secure contexts
    }
  }

  return (
    <div className="space-y-4">
      {/* API Endpoints */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h3 className="font-semibold text-gray-100">API Endpoints</h3>
        <p className="mt-1 text-sm text-gray-500">
          Use these endpoints to integrate with the ShieldOps API.
        </p>

        <dl className="mt-4 space-y-3">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wider text-gray-500">
              Base URL
            </dt>
            <dd className="mt-0.5 font-mono text-sm text-gray-200">{baseUrl}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wider text-gray-500">
              API Docs
            </dt>
            <dd className="mt-0.5">
              <a
                href={docsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono text-sm text-brand-400 hover:text-brand-300"
              >
                {docsUrl}
                <ExternalLink className="h-3 w-3" />
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wider text-gray-500">
              OpenAPI Spec
            </dt>
            <dd className="mt-0.5">
              <a
                href={openApiUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono text-sm text-brand-400 hover:text-brand-300"
              >
                {openApiUrl}
                <ExternalLink className="h-3 w-3" />
              </a>
            </dd>
          </div>
        </dl>
      </div>

      {/* Token section */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h3 className="font-semibold text-gray-100">Your Token</h3>
        <p className="mt-1 text-sm text-gray-500">
          Use this bearer token to authenticate API requests.
        </p>

        <div className="mt-3 flex items-center gap-2">
          <div className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2">
            <code className="text-sm text-gray-300">{maskToken(token)}</code>
          </div>
          <button
            onClick={copyToken}
            disabled={!token}
            className="flex items-center gap-1.5 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-green-400" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy
              </>
            )}
          </button>
        </div>
      </div>

      {/* Swagger link */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
        <h3 className="font-semibold text-gray-100">Interactive Documentation</h3>
        <p className="mt-1 text-sm text-gray-500">
          Explore and test API endpoints using the interactive Swagger UI.
        </p>
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600"
        >
          Open Swagger Docs
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}
