import { useState } from "react";
import {
  Zap,
  Search,
  Plus,
  Play,
  Pause,
  Settings,
  ArrowRight,
  Shield,
  Bell,
  Wrench,
  DollarSign,
  GitBranch,
  Clock,
  CheckCircle2,
  AlertTriangle,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ────────────────────────────────────────────────────────────

interface AutomationRule {
  id: string;
  name: string;
  description: string;
  trigger: { type: string; source: string; condition: string };
  actions: { type: string; target: string; detail: string }[];
  policyGate: string;
  enabled: boolean;
  lastTriggered?: string;
  executions24h: number;
  category: string;
  icon: LucideIcon;
  iconColor: string;
}

// ── Demo Data ────────────────────────────────────────────────────────

const DEMO_RULES: AutomationRule[] = [
  {
    id: "r1",
    name: "Critical Alert → Auto-Investigate",
    description: "When a P1/Critical alert fires, automatically launch an investigation agent with full context correlation",
    trigger: { type: "Alert", source: "PagerDuty / Datadog", condition: "severity = critical" },
    actions: [
      { type: "Launch Agent", target: "Investigation Agent", detail: "Full correlation: logs + metrics + traces" },
      { type: "Notify", target: "Slack #incidents", detail: "Post investigation summary" },
      { type: "Create Ticket", target: "Jira", detail: "Auto-create with findings" },
    ],
    policyGate: "allow_investigation",
    enabled: true,
    lastTriggered: "12 min ago",
    executions24h: 7,
    category: "incident",
    icon: Bell,
    iconColor: "text-red-400",
  },
  {
    id: "r2",
    name: "OOM Killed → Scale & Rollback",
    description: "Auto-detect OOMKilled pods, scale up memory limits, and rollback if a bad deploy is detected",
    trigger: { type: "K8s Event", source: "Kubernetes", condition: "reason = OOMKilled, count > 3 in 10m" },
    actions: [
      { type: "Remediate", target: "Kubernetes", detail: "Increase memory limit by 50%" },
      { type: "Check", target: "Deployment History", detail: "If deployed < 1h ago → rollback" },
      { type: "Notify", target: "Slack #sre-oncall", detail: "Post remediation result" },
    ],
    policyGate: "allow_scale_and_rollback",
    enabled: true,
    lastTriggered: "2h ago",
    executions24h: 3,
    category: "remediation",
    icon: Wrench,
    iconColor: "text-emerald-400",
  },
  {
    id: "r3",
    name: "CVE Critical → Auto-Patch Staging",
    description: "When a critical CVE is detected, auto-patch staging environments and create a PR for production",
    trigger: { type: "Vulnerability Scan", source: "Security Agent", condition: "CVSS >= 9.0" },
    actions: [
      { type: "Patch", target: "Staging Clusters", detail: "Auto-apply security patch" },
      { type: "Create PR", target: "GitHub", detail: "Version bump + changelog" },
      { type: "Notify", target: "Slack #security-alerts", detail: "Patch status + PR link" },
    ],
    policyGate: "allow_staging_patch",
    enabled: true,
    lastTriggered: "1d ago",
    executions24h: 1,
    category: "security",
    icon: Shield,
    iconColor: "text-red-400",
  },
  {
    id: "r4",
    name: "Cost Spike → Alert & Analyze",
    description: "Detect cost anomalies exceeding 20% of baseline and trigger root cause analysis",
    trigger: { type: "Cost Alert", source: "FinOps Agent", condition: "spend > 120% of 7-day average" },
    actions: [
      { type: "Analyze", target: "FinOps Agent", detail: "Root cause analysis on cost spike" },
      { type: "Notify", target: "Slack #finops + Email", detail: "Cost breakdown + recommendations" },
      { type: "Tag", target: "AWS/GCP Resources", detail: "Flag untagged resources" },
    ],
    policyGate: "allow_cost_analysis",
    enabled: true,
    lastTriggered: "4h ago",
    executions24h: 2,
    category: "finops",
    icon: DollarSign,
    iconColor: "text-amber-400",
  },
  {
    id: "r5",
    name: "Deploy → Security + Performance Scan",
    description: "On every production deployment, run security scanning and performance baseline check",
    trigger: { type: "Webhook", source: "GitHub Actions", condition: "deploy event, env = production" },
    actions: [
      { type: "Scan", target: "Security Agent", detail: "SAST + dependency + container scan" },
      { type: "Benchmark", target: "Performance Agent", detail: "Latency baseline comparison" },
      { type: "Gate", target: "GitHub Check", detail: "Pass/fail deployment gate" },
    ],
    policyGate: "require_deploy_scan",
    enabled: true,
    lastTriggered: "6h ago",
    executions24h: 4,
    category: "devops",
    icon: GitBranch,
    iconColor: "text-sky-400",
  },
  {
    id: "r6",
    name: "SLO Burn Rate → Proactive Scale",
    description: "When error budget burn rate exceeds 2x normal, proactively scale services before SLO breach",
    trigger: { type: "SLO Alert", source: "SLA Engine", condition: "burn_rate > 2x, window = 1h" },
    actions: [
      { type: "Scale", target: "Kubernetes HPA", detail: "Increase replicas by 50%" },
      { type: "Investigate", target: "Investigation Agent", detail: "Find contributing factors" },
      { type: "Notify", target: "PagerDuty", detail: "Create informational incident" },
    ],
    policyGate: "allow_proactive_scale",
    enabled: false,
    lastTriggered: "3d ago",
    executions24h: 0,
    category: "incident",
    icon: AlertTriangle,
    iconColor: "text-orange-400",
  },
];

// ── Component ────────────────────────────────────────────────────────

export default function AutomationRules() {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const filtered = DEMO_RULES.filter((r) =>
    r.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const stats = {
    total: DEMO_RULES.length,
    active: DEMO_RULES.filter((r) => r.enabled).length,
    executions: DEMO_RULES.reduce((sum, r) => sum + r.executions24h, 0),
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-white">
            <Zap className="h-5 w-5 text-brand-400" />
            Automation Rules
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Event-driven automation with OPA policy gates — trigger agents on
            alerts, deploys, and anomalies
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-gray-800/60 px-3 py-1.5 text-xs text-gray-300">
            <span className="font-bold text-white">{stats.total}</span> rules
          </span>
          <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
            <span className="font-bold">{stats.active}</span> active
          </span>
          <span className="rounded-lg bg-brand-500/10 px-3 py-1.5 text-xs text-brand-400">
            <span className="font-bold">{stats.executions}</span> runs today
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
            placeholder="Search rules..."
            aria-label="Search automation rules"
            className="w-full rounded-xl border border-gray-700 bg-gray-800/50 py-2.5 pl-10 pr-4 text-sm text-gray-200 placeholder-gray-500 focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
        <button className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50">
          <Plus className="h-4 w-4" />
          Create Rule
        </button>
      </div>

      {/* Rules list */}
      <div className="space-y-3">
        {filtered.map((rule) => {
          const Icon = rule.icon;
          const isExpanded = expandedRule === rule.id;

          return (
            <div
              key={rule.id}
              className={clsx(
                "rounded-xl border bg-gray-900/40 transition-all",
                rule.enabled
                  ? "border-gray-800/50 hover:border-gray-700"
                  : "border-gray-800/30 opacity-60",
              )}
            >
              {/* Main row */}
              <button
                onClick={() => setExpandedRule(isExpanded ? null : rule.id)}
                className="flex w-full items-center gap-4 px-5 py-4 text-left focus:outline-none focus:ring-2 focus:ring-brand-500/50 rounded-xl"
                aria-expanded={isExpanded}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-800/60">
                  <Icon className={clsx("h-5 w-5", rule.iconColor)} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-200 truncate">
                    {rule.name}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500 truncate">
                    {rule.description}
                  </p>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <div className="hidden items-center gap-3 text-xs text-gray-600 sm:flex">
                    {rule.lastTriggered && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {rule.lastTriggered}
                      </span>
                    )}
                    <span>{rule.executions24h} runs/24h</span>
                  </div>
                  <span
                    className={clsx(
                      "rounded-full px-2.5 py-1 text-xs font-medium",
                      rule.enabled
                        ? "bg-emerald-500/10 text-emerald-400"
                        : "bg-gray-500/10 text-gray-500",
                    )}
                  >
                    {rule.enabled ? "Active" : "Paused"}
                  </span>
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="border-t border-gray-800/50 px-5 py-4">
                  <div className="grid gap-4 md:grid-cols-3">
                    {/* Trigger */}
                    <div>
                      <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                        Trigger
                      </h4>
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3">
                        <p className="text-xs font-medium text-gray-300">
                          {rule.trigger.type}
                        </p>
                        <p className="mt-1 text-[10px] text-gray-500">
                          Source: {rule.trigger.source}
                        </p>
                        <p className="mt-0.5 font-mono text-[10px] text-brand-400">
                          {rule.trigger.condition}
                        </p>
                      </div>
                    </div>

                    {/* Actions */}
                    <div>
                      <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                        Actions
                      </h4>
                      <div className="space-y-1.5">
                        {rule.actions.map((action, i) => (
                          <div
                            key={i}
                            className="flex items-start gap-2 rounded-lg border border-gray-800 bg-gray-800/30 p-2"
                          >
                            <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-brand-400" />
                            <div>
                              <p className="text-[10px] font-medium text-gray-300">
                                {action.type}{" "}
                                <span className="text-gray-500">→</span>{" "}
                                {action.target}
                              </p>
                              <p className="text-[10px] text-gray-500">
                                {action.detail}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Policy gate */}
                    <div>
                      <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                        Policy Gate
                      </h4>
                      <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3">
                        <div className="flex items-center gap-2">
                          <Shield className="h-3.5 w-3.5 text-emerald-400" />
                          <span className="font-mono text-xs text-emerald-400">
                            {rule.policyGate}
                          </span>
                        </div>
                        <p className="mt-2 text-[10px] text-gray-500">
                          OPA policy evaluated before every execution.
                          High-risk actions require human approval.
                        </p>
                        <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-400">
                          <CheckCircle2 className="h-3 w-3" />
                          Policy active
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Bottom actions */}
                  <div className="mt-4 flex items-center gap-2 border-t border-gray-800/50 pt-3">
                    <button className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50">
                      <Settings className="h-3.5 w-3.5" />
                      Edit Rule
                    </button>
                    <button className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50">
                      {rule.enabled ? (
                        <>
                          <Pause className="h-3.5 w-3.5" />
                          Pause
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5" />
                          Enable
                        </>
                      )}
                    </button>
                    <button className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50">
                      <Play className="h-3.5 w-3.5" />
                      Test Run
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="py-16 text-center">
          <Zap className="mx-auto mb-3 h-10 w-10 text-gray-700" />
          <p className="text-sm text-gray-500">No rules match your search.</p>
        </div>
      )}
    </div>
  );
}
