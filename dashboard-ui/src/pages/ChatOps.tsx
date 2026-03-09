import { useState } from "react";
import {
  MessageSquare,
  Send,
  Bot,
  User,
  Loader2,
  Hash,
  Shield,
  Wrench,
  Search,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Zap,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  channel?: string;
  actions?: CommandAction[];
  agentType?: string;
  status?: "pending" | "running" | "completed" | "failed";
}

interface CommandAction {
  label: string;
  type: "approve" | "reject" | "view" | "escalate";
  color: string;
}

interface QuickCommand {
  icon: LucideIcon;
  label: string;
  command: string;
  color: string;
  description: string;
}

interface ChannelInfo {
  name: string;
  platform: string;
  unread: number;
  status: "active" | "idle";
}

// ── Demo Data ────────────────────────────────────────────────────────

const QUICK_COMMANDS: QuickCommand[] = [
  {
    icon: Search,
    label: "Investigate",
    command: "/investigate",
    color: "text-brand-400",
    description: "Launch AI investigation on an alert or service",
  },
  {
    icon: Wrench,
    label: "Remediate",
    command: "/remediate",
    color: "text-emerald-400",
    description: "Execute a remediation playbook with policy gates",
  },
  {
    icon: Shield,
    label: "Security Scan",
    command: "/scan",
    color: "text-red-400",
    description: "Run vulnerability or posture scan",
  },
  {
    icon: DollarSign,
    label: "Cost Report",
    command: "/cost-report",
    color: "text-amber-400",
    description: "Generate cost analysis for a service or team",
  },
  {
    icon: AlertTriangle,
    label: "Escalate",
    command: "/escalate",
    color: "text-orange-400",
    description: "Escalate to on-call with context summary",
  },
  {
    icon: Zap,
    label: "Status",
    command: "/status",
    color: "text-sky-400",
    description: "Get real-time platform and agent status",
  },
];

const CHANNELS: ChannelInfo[] = [
  { name: "#incidents", platform: "Slack", unread: 3, status: "active" },
  { name: "#sre-oncall", platform: "Slack", unread: 0, status: "active" },
  { name: "SRE Ops", platform: "Teams", unread: 1, status: "active" },
  { name: "P1 Alerts", platform: "PagerDuty", unread: 2, status: "active" },
  { name: "#security-alerts", platform: "Slack", unread: 0, status: "idle" },
  { name: "#finops", platform: "Slack", unread: 0, status: "idle" },
];

const DEMO_MESSAGES: ChatMessage[] = [
  {
    id: "sys-1",
    role: "system",
    content: "ShieldOps ChatOps connected. Type / to see available commands.",
    timestamp: "10:00 AM",
  },
  {
    id: "u-1",
    role: "user",
    content: "/investigate payment-service high-latency",
    timestamp: "10:12 AM",
    channel: "#incidents",
  },
  {
    id: "a-1",
    role: "assistant",
    content:
      "Starting investigation on payment-service for high-latency alert.\n\n" +
      "**Agent:** Investigation Agent v2.4\n" +
      "**Correlating:** CloudWatch metrics, application logs, trace spans\n" +
      "**Scope:** payment-service, us-east-1\n\n" +
      "Found root cause: Redis connection pool exhaustion after deploy v3.2.1 (deployed 47m ago). " +
      "Connection pool size was reduced from 50 to 10 in config change.\n\n" +
      "**Confidence:** 94% | **Impact:** 12% of transactions affected\n" +
      "**Recommended:** Rollback config to v3.2.0 or increase pool size to 50",
    timestamp: "10:12 AM",
    agentType: "investigation",
    status: "completed",
    actions: [
      { label: "Approve Rollback", type: "approve", color: "text-emerald-400" },
      { label: "View Full Report", type: "view", color: "text-brand-400" },
      { label: "Escalate to On-Call", type: "escalate", color: "text-amber-400" },
    ],
  },
  {
    id: "u-2",
    role: "user",
    content: "/status agents",
    timestamp: "10:15 AM",
    channel: "#sre-oncall",
  },
  {
    id: "a-2",
    role: "assistant",
    content:
      "**Agent Status Summary**\n\n" +
      "| Agent | Status | Tasks |\n" +
      "|-------|--------|-------|\n" +
      "| Investigation | Running | 3 active |\n" +
      "| Remediation | Idle | 0 queued |\n" +
      "| Security | Running | 1 scan |\n" +
      "| Learning | Idle | Next cycle in 2h |\n" +
      "| FinOps | Running | Cost analysis |\n\n" +
      "**Platform Health:** All systems operational\n" +
      "**Active Incidents:** 2 open (1 P2, 1 P3)",
    timestamp: "10:15 AM",
    agentType: "supervisor",
    status: "completed",
  },
  {
    id: "u-3",
    role: "user",
    content: "/scan vulnerabilities --critical --service=api-gateway",
    timestamp: "10:18 AM",
    channel: "#security-alerts",
  },
  {
    id: "a-3",
    role: "assistant",
    content:
      "Scanning api-gateway for critical vulnerabilities...\n\n" +
      "**Results:** 2 critical findings\n\n" +
      "1. **CVE-2024-38816** — Spring Framework path traversal\n" +
      "   Severity: Critical (9.8) | Fix: Upgrade to 6.1.13\n\n" +
      "2. **CVE-2024-22262** — Spring URL parsing bypass\n" +
      "   Severity: Critical (8.1) | Fix: Upgrade to 6.1.6\n\n" +
      "**OPA Policy:** Auto-patch allowed for non-prod. Production requires approval.\n\n" +
      "Shall I create remediation tickets?",
    timestamp: "10:19 AM",
    agentType: "security",
    status: "completed",
    actions: [
      { label: "Auto-Patch Staging", type: "approve", color: "text-emerald-400" },
      { label: "Create Jira Tickets", type: "view", color: "text-brand-400" },
      { label: "Reject", type: "reject", color: "text-red-400" },
    ],
  },
];

// ── Component ────────────────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  investigation: "text-brand-400 bg-brand-500/10",
  remediation: "text-emerald-400 bg-emerald-500/10",
  security: "text-red-400 bg-red-500/10",
  supervisor: "text-sky-400 bg-sky-500/10",
};

export default function ChatOps() {
  const [input, setInput] = useState("");
  const [activeChannel, setActiveChannel] = useState("#incidents");
  const [showCommands, setShowCommands] = useState(false);

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0">
      {/* Channels sidebar */}
      <div className="hidden w-56 shrink-0 border-r border-gray-800 bg-gray-900/60 lg:block">
        <div className="p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Channels
          </h2>
        </div>
        <div className="space-y-0.5 px-2">
          {CHANNELS.map((ch) => (
            <button
              key={ch.name}
              onClick={() => setActiveChannel(ch.name)}
              className={clsx(
                "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                activeChannel === ch.name
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200",
              )}
            >
              <span className="flex items-center gap-2 truncate">
                <Hash className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{ch.name.replace("#", "")}</span>
              </span>
              <span className="flex items-center gap-2">
                {ch.unread > 0 && (
                  <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-bold text-white">
                    {ch.unread}
                  </span>
                )}
                <span
                  className={clsx(
                    "h-1.5 w-1.5 rounded-full",
                    ch.status === "active" ? "bg-emerald-400" : "bg-gray-600",
                  )}
                />
              </span>
            </button>
          ))}
        </div>

        <div className="mt-6 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Connected Platforms
          </h2>
          <div className="space-y-2">
            {["Slack", "Microsoft Teams", "PagerDuty"].map((platform) => (
              <div
                key={platform}
                className="flex items-center gap-2 text-xs text-gray-400"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                {platform}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Chat header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <MessageSquare className="h-5 w-5 text-brand-400" />
            <div>
              <h1 className="text-sm font-semibold text-white">
                ChatOps Command Center
              </h1>
              <p className="text-xs text-gray-500">
                {activeChannel} — Natural language operations
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Connected
            </span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
          <div className="mx-auto max-w-3xl space-y-4">
            {DEMO_MESSAGES.map((msg) => {
              if (msg.role === "system") {
                return (
                  <div
                    key={msg.id}
                    className="text-center text-xs text-gray-600"
                  >
                    <span className="rounded-full bg-gray-800/50 px-3 py-1">
                      {msg.content}
                    </span>
                  </div>
                );
              }

              return (
                <div
                  key={msg.id}
                  className={clsx(
                    "flex gap-3",
                    msg.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  {msg.role === "assistant" && (
                    <div
                      className={clsx(
                        "mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                        AGENT_COLORS[msg.agentType || "investigation"] ||
                          "bg-brand-500/10",
                      )}
                    >
                      <Bot className="h-4 w-4" />
                    </div>
                  )}
                  <div
                    className={clsx(
                      "max-w-[85%] rounded-xl px-4 py-3",
                      msg.role === "user"
                        ? "bg-brand-600/20 text-gray-200"
                        : "border border-gray-800 bg-gray-900/60 text-gray-200",
                    )}
                  >
                    {msg.channel && msg.role === "user" && (
                      <span className="mb-1 flex items-center gap-1 text-[10px] text-gray-500">
                        <Hash className="h-2.5 w-2.5" />
                        {msg.channel.replace("#", "")}
                      </span>
                    )}
                    {msg.agentType && msg.role === "assistant" && (
                      <div className="mb-2 flex items-center gap-2">
                        <span
                          className={clsx(
                            "rounded-full px-2 py-0.5 text-[10px] font-medium",
                            AGENT_COLORS[msg.agentType] || "bg-gray-800",
                          )}
                        >
                          {msg.agentType} agent
                        </span>
                        {msg.status && (
                          <span className="flex items-center gap-1 text-[10px] text-gray-500">
                            {msg.status === "completed" ? (
                              <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                            ) : msg.status === "running" ? (
                              <Loader2 className="h-3 w-3 animate-spin text-brand-400" />
                            ) : (
                              <Clock className="h-3 w-3" />
                            )}
                            {msg.status}
                          </span>
                        )}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                      {msg.content}
                    </div>
                    {msg.actions && msg.actions.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2 border-t border-gray-800 pt-3">
                        {msg.actions.map((action) => (
                          <button
                            key={action.label}
                            className={clsx(
                              "rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                              action.color,
                            )}
                          >
                            {action.label}
                          </button>
                        ))}
                      </div>
                    )}
                    <span className="mt-1 block text-right text-[10px] text-gray-600">
                      {msg.timestamp}
                    </span>
                  </div>
                  {msg.role === "user" && (
                    <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-700">
                      <User className="h-4 w-4 text-gray-300" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Quick commands */}
        {showCommands && (
          <div className="border-t border-gray-800 bg-gray-900/80 px-4 py-3 sm:px-6">
            <div className="mx-auto grid max-w-3xl grid-cols-2 gap-2 sm:grid-cols-3">
              {QUICK_COMMANDS.map((cmd) => {
                const Icon = cmd.icon;
                return (
                  <button
                    key={cmd.command}
                    onClick={() => {
                      setInput(cmd.command + " ");
                      setShowCommands(false);
                    }}
                    className="flex items-center gap-2.5 rounded-lg border border-gray-800 bg-gray-900 px-3 py-2.5 text-left transition-all hover:border-gray-600 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  >
                    <Icon className={clsx("h-4 w-4 shrink-0", cmd.color)} />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-gray-200">
                        {cmd.command}
                      </p>
                      <p className="truncate text-[10px] text-gray-500">
                        {cmd.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-800 px-4 py-3 sm:px-6">
          <div className="mx-auto flex max-w-3xl items-center gap-2">
            <button
              onClick={() => setShowCommands(!showCommands)}
              className={clsx(
                "shrink-0 rounded-lg p-2.5 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                showCommands
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-500 hover:bg-gray-800 hover:text-gray-300",
              )}
              aria-label="Toggle quick commands"
              aria-expanded={showCommands}
            >
              <Zap className="h-4 w-4" />
            </button>
            <div className="flex flex-1 items-center gap-2 rounded-xl border border-gray-700 bg-gray-800/50 px-4 py-2.5">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a command (e.g. /investigate api-gateway) or ask a question..."
                className="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-500 focus:outline-none"
                aria-label="ChatOps command input"
              />
              <button
                disabled={!input.trim()}
                className={clsx(
                  "shrink-0 rounded-lg p-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50",
                  input.trim()
                    ? "bg-brand-600 text-white hover:bg-brand-500"
                    : "text-gray-600",
                )}
                aria-label="Send command"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
          <p className="mx-auto mt-1.5 max-w-3xl text-center text-[10px] text-gray-600">
            All commands are policy-gated via OPA. High-risk actions require
            approval.
          </p>
        </div>
      </div>

      {/* Right panel — Quick commands reference */}
      <div className="hidden w-64 shrink-0 border-l border-gray-800 bg-gray-900/60 xl:block">
        <div className="p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Quick Commands
          </h2>
        </div>
        <div className="space-y-1 px-2">
          {QUICK_COMMANDS.map((cmd) => {
            const Icon = cmd.icon;
            return (
              <button
                key={cmd.command}
                onClick={() => setInput(cmd.command + " ")}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
              >
                <Icon className={clsx("h-4 w-4 shrink-0", cmd.color)} />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-300">
                    {cmd.label}
                  </p>
                  <p className="truncate text-[10px] text-gray-500">
                    {cmd.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-6 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Recent Activity
          </h2>
          <div className="space-y-3">
            {[
              { label: "Incident auto-resolved", time: "2m ago", icon: CheckCircle2, color: "text-emerald-400" },
              { label: "Security scan completed", time: "8m ago", icon: Shield, color: "text-red-400" },
              { label: "Cost anomaly detected", time: "15m ago", icon: DollarSign, color: "text-amber-400" },
              { label: "Playbook executed", time: "22m ago", icon: Wrench, color: "text-brand-400" },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.label} className="flex items-start gap-2">
                  <Icon className={clsx("mt-0.5 h-3.5 w-3.5 shrink-0", item.color)} />
                  <div>
                    <p className="text-xs text-gray-300">{item.label}</p>
                    <p className="text-[10px] text-gray-600">{item.time}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
