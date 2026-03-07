import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldAlert,
  Bug,
  GitPullRequest,
  Search,
  Wrench,
  Siren,
  Workflow,
  DollarSign,
  FileCode,
  Scan,
  RotateCcw,
  AlertTriangle,
  Users,
  Server,
  Terminal,
  Brain,
  Globe,
  Lock,
  Sparkles,
  Clock,
  Activity,
  ChevronDown,
  ChevronUp,
  Zap,
  type LucideIcon,
} from "lucide-react";
import AgentPromptInput from "../components/AgentPromptInput";
import TaskCard, { type TaskTemplate } from "../components/TaskCard";
import PersonaSwitcher from "../components/PersonaSwitcher";
import MetricsBar from "../components/MetricsBar";

// ── Task templates ──────────────────────────────────────────────────────
const ALL_TASKS: TaskTemplate[] = [
  // Suggested (top-level)
  {
    id: "investigate-incidents",
    title: "Investigate & Resolve Incidents",
    description:
      "Monitor Slack, PagerDuty, or Teams for new incidents. Auto-investigate root cause using logs, metrics, and traces, then apply remediation.",
    icon: Siren,
    iconBg: "bg-red-500/10",
    iconColor: "text-red-400",
    category: "suggested",
    prompt:
      "Investigate the latest critical incidents from our alerting channels. Pull logs from Splunk, correlate with metrics, identify root cause, and suggest or auto-apply remediation.",
    estimatedTime: "2-5 min",
    tags: ["MTTR", "auto-remediate"],
  },
  {
    id: "scan-vulnerabilities",
    title: "Find & Fix Security Vulnerabilities",
    description:
      "Scan codebase and infrastructure for CVEs, misconfigurations, and exposed secrets. Auto-generate patches and PRs.",
    icon: ShieldAlert,
    iconBg: "bg-amber-500/10",
    iconColor: "text-amber-400",
    category: "suggested",
    prompt:
      "Run a full security scan across our repositories and cloud infrastructure. Identify critical CVEs, exposed secrets, and misconfigurations. Generate fix PRs for the top 10 findings.",
    estimatedTime: "3-8 min",
    tags: ["security", "CVE"],
  },
  {
    id: "fix-bugs-slack",
    title: "Fix Bugs Reported in Slack",
    description:
      "Monitor a Slack channel for bug reports. Investigate the codebase, identify the issue, and submit a PR with the fix.",
    icon: Bug,
    iconBg: "bg-purple-500/10",
    iconColor: "text-purple-400",
    category: "suggested",
    prompt:
      "Connect to #bugs Slack channel. For each unresolved bug report, investigate the relevant codebase, identify the root cause, write a fix, and open a PR.",
    estimatedTime: "5-10 min",
    tags: ["Slack", "auto-fix"],
  },
  {
    id: "create-pipeline",
    title: "Create CI/CD Pipeline",
    description:
      "Auto-generate a production-grade CI/CD pipeline for your repo with testing, security scanning, and deployment stages.",
    icon: Workflow,
    iconBg: "bg-sky-500/10",
    iconColor: "text-sky-400",
    category: "suggested",
    prompt:
      "Analyze the repository structure and create a comprehensive CI/CD pipeline with build, test, security scan, and deployment stages. Include rollback capabilities.",
    estimatedTime: "3-5 min",
    tags: ["CI/CD", "DevOps"],
  },

  // Incident Response
  {
    id: "splunk-errors",
    title: "Investigate Splunk Errors",
    description:
      "Query Splunk for recurring error patterns, correlate with deployment events, and identify root cause.",
    icon: Search,
    iconBg: "bg-green-500/10",
    iconColor: "text-green-400",
    category: "incident",
    prompt:
      "Search Splunk for the top error patterns in the last 24 hours. Correlate with recent deployments and infrastructure changes. Identify root causes and recommended fixes.",
    estimatedTime: "2-4 min",
    tags: ["Splunk", "RCA"],
  },
  {
    id: "spin-war-room",
    title: "Spin Up War Room",
    description:
      "Create an incident war room, auto-page responsible teams based on service ownership, and coordinate response.",
    icon: Users,
    iconBg: "bg-red-500/10",
    iconColor: "text-red-400",
    category: "incident",
    prompt:
      "Create a war room for the current critical incident. Identify affected services, page the responsible on-call teams, set up a shared timeline, and coordinate remediation.",
    estimatedTime: "1-2 min",
    tags: ["war-room", "paging"],
  },
  {
    id: "auto-remediate",
    title: "Auto-Remediate Known Issues",
    description:
      "Match current alerts against known playbooks and automatically execute safe remediations with policy gates.",
    icon: Wrench,
    iconBg: "bg-brand-500/10",
    iconColor: "text-brand-400",
    category: "incident",
    prompt:
      "Check all active alerts. Match against our remediation playbooks. For issues with approved runbooks, auto-execute remediation with rollback safety. Escalate unknowns.",
    estimatedTime: "1-3 min",
    tags: ["auto-heal", "playbooks"],
  },
  {
    id: "rollback-deployment",
    title: "Rollback Failed Deployment",
    description:
      "Detect deployment failures, verify blast radius, and safely rollback to the last known good version.",
    icon: RotateCcw,
    iconBg: "bg-orange-500/10",
    iconColor: "text-orange-400",
    category: "incident",
    prompt:
      "Identify the latest failed deployment. Assess blast radius and affected services. Execute a safe rollback to the last stable version. Verify health post-rollback.",
    estimatedTime: "2-5 min",
    tags: ["rollback", "deployment"],
  },

  // Security
  {
    id: "threat-hunt",
    title: "Run Threat Hunt Campaign",
    description:
      "Execute MITRE ATT&CK-based threat hunting across your environment. Identify IOCs, lateral movement, and suspicious patterns.",
    icon: Scan,
    iconBg: "bg-red-500/10",
    iconColor: "text-red-400",
    category: "security",
    prompt:
      "Run a threat hunt campaign using MITRE ATT&CK tactics. Scan for IOCs across endpoints, network flows, and cloud audit logs. Report findings with evidence and recommended containment.",
    estimatedTime: "5-15 min",
    tags: ["MITRE", "threat-hunt"],
  },
  {
    id: "credential-rotation",
    title: "Rotate Expired Credentials",
    description:
      "Detect expiring or compromised credentials and auto-rotate them across services with zero downtime.",
    icon: Lock,
    iconBg: "bg-yellow-500/10",
    iconColor: "text-yellow-400",
    category: "security",
    prompt:
      "Scan all credential stores and certificates for expiring or compromised secrets. Auto-rotate with zero-downtime strategy. Update dependent services and verify connectivity.",
    estimatedTime: "3-8 min",
    tags: ["credentials", "zero-downtime"],
  },
  {
    id: "compliance-check",
    title: "Run Compliance Audit",
    description:
      "Audit infrastructure against SOC2, HIPAA, or PCI-DSS controls. Generate evidence reports and remediation plans.",
    icon: FileCode,
    iconBg: "bg-amber-500/10",
    iconColor: "text-amber-400",
    category: "security",
    prompt:
      "Run a comprehensive compliance audit against SOC2 Type II controls. Identify gaps, collect evidence, and generate a compliance report with prioritized remediation plan.",
    estimatedTime: "5-10 min",
    tags: ["SOC2", "compliance"],
  },

  // Automation
  {
    id: "onboard-codebase",
    title: "Automate a New Codebase",
    description:
      "Analyze a new repository, set up monitoring, alerting rules, SLOs, and integrate with your observability stack.",
    icon: Terminal,
    iconBg: "bg-sky-500/10",
    iconColor: "text-sky-400",
    category: "automation",
    prompt:
      "Analyze this new codebase. Set up observability (metrics, logs, traces), define SLOs, create alerting rules, and integrate with our Datadog/Splunk stack. Generate runbooks for common failure modes.",
    estimatedTime: "5-10 min",
    tags: ["onboarding", "SLO"],
  },
  {
    id: "generate-runbooks",
    title: "Generate Runbooks from History",
    description:
      "Analyze past incidents and remediations to auto-generate runbooks for recurring patterns.",
    icon: Brain,
    iconBg: "bg-violet-500/10",
    iconColor: "text-violet-400",
    category: "automation",
    prompt:
      "Analyze the last 90 days of incidents and remediations. Identify recurring patterns and generate executable runbooks for the top 10 most common issues.",
    estimatedTime: "3-5 min",
    tags: ["learning", "runbooks"],
  },
  {
    id: "assign-pr-reviewers",
    title: "Auto-Assign PR Reviewers",
    description:
      "Analyze code changes, determine risk level, and assign the right reviewers. Auto-approve low-risk PRs.",
    icon: GitPullRequest,
    iconBg: "bg-green-500/10",
    iconColor: "text-green-400",
    category: "automation",
    prompt:
      "For all open PRs, analyze code changes for risk. Assign appropriate reviewers based on code ownership and expertise. Auto-approve low-risk PRs that pass all checks.",
    estimatedTime: "1-3 min",
    tags: ["GitHub", "reviews"],
  },
  {
    id: "scale-infrastructure",
    title: "Predictive Scaling",
    description:
      "Analyze traffic patterns and auto-scale infrastructure ahead of demand spikes to prevent outages.",
    icon: Server,
    iconBg: "bg-brand-500/10",
    iconColor: "text-brand-400",
    category: "automation",
    prompt:
      "Analyze the last 30 days of traffic patterns. Predict upcoming demand spikes. Pre-scale infrastructure to handle predicted load with a 20% buffer. Set up auto-rollback if predictions are wrong.",
    estimatedTime: "3-5 min",
    tags: ["scaling", "prediction"],
  },

  // Cost
  {
    id: "cost-optimization",
    title: "Find Cost Savings",
    description:
      "Scan cloud accounts for idle resources, over-provisioned instances, and missed RI opportunities.",
    icon: DollarSign,
    iconBg: "bg-emerald-500/10",
    iconColor: "text-emerald-400",
    category: "cost",
    prompt:
      "Scan all cloud accounts for cost optimization opportunities. Identify idle resources, right-sizing candidates, and RI/Savings Plan recommendations. Calculate potential monthly savings.",
    estimatedTime: "3-5 min",
    tags: ["FinOps", "savings"],
  },

  // Compliance
  {
    id: "drift-detection",
    title: "Detect Configuration Drift",
    description:
      "Compare live infrastructure against IaC definitions. Flag and auto-fix drift in Terraform, K8s, and cloud configs.",
    icon: AlertTriangle,
    iconBg: "bg-orange-500/10",
    iconColor: "text-orange-400",
    category: "compliance",
    prompt:
      "Compare live infrastructure state against Terraform and Kubernetes manifests. Identify all configuration drift. Auto-generate PRs to reconcile drift or flag items requiring manual review.",
    estimatedTime: "3-8 min",
    tags: ["drift", "IaC"],
  },
  {
    id: "multi-region-check",
    title: "Multi-Region Health Check",
    description:
      "Run a comprehensive health check across all regions and cloud providers. Verify failover readiness.",
    icon: Globe,
    iconBg: "bg-sky-500/10",
    iconColor: "text-sky-400",
    category: "compliance",
    prompt:
      "Run health checks across all regions (us-east-1, us-west-2, eu-west-1). Verify cross-region replication, failover readiness, and DNS routing. Report any region-specific issues.",
    estimatedTime: "2-5 min",
    tags: ["multi-region", "DR"],
  },
];

// Filter tasks by persona relevance
const PERSONA_TASKS: Record<string, string[]> = {
  sre: [
    "investigate-incidents", "splunk-errors", "spin-war-room", "auto-remediate",
    "rollback-deployment", "onboard-codebase", "generate-runbooks", "scale-infrastructure",
    "multi-region-check", "drift-detection",
  ],
  security: [
    "scan-vulnerabilities", "threat-hunt", "credential-rotation", "compliance-check",
    "investigate-incidents", "spin-war-room", "drift-detection", "multi-region-check",
  ],
  finops: [
    "cost-optimization", "scale-infrastructure", "onboard-codebase", "drift-detection",
    "create-pipeline", "multi-region-check",
  ],
  devops: [
    "create-pipeline", "onboard-codebase", "assign-pr-reviewers", "rollback-deployment",
    "drift-detection", "fix-bugs-slack", "generate-runbooks", "scale-infrastructure",
  ],
  manager: [
    "investigate-incidents", "cost-optimization", "compliance-check", "spin-war-room",
    "generate-runbooks", "scale-infrastructure", "multi-region-check",
  ],
  observer: [
    "compliance-check", "drift-detection", "cost-optimization", "multi-region-check",
    "splunk-errors",
  ],
};

// ── Recent agent runs (mock) ────────────────────────────────────────────
interface RecentRun {
  id: string;
  title: string;
  status: "completed" | "running" | "failed" | "awaiting-approval";
  startedAt: string;
  duration: string;
  icon: LucideIcon;
  iconColor: string;
}

const RECENT_RUNS: RecentRun[] = [
  {
    id: "run-1",
    title: "Investigated Splunk 500 errors in payment-service",
    status: "completed",
    startedAt: "12 min ago",
    duration: "3m 22s",
    icon: Search,
    iconColor: "text-green-400",
  },
  {
    id: "run-2",
    title: "Auto-remediated high CPU on k8s-prod-cluster-03",
    status: "completed",
    startedAt: "28 min ago",
    duration: "1m 47s",
    icon: Wrench,
    iconColor: "text-brand-400",
  },
  {
    id: "run-3",
    title: "Scanning CVEs in auth-service dependencies",
    status: "running",
    startedAt: "2 min ago",
    duration: "2m 10s",
    icon: ShieldAlert,
    iconColor: "text-amber-400",
  },
  {
    id: "run-4",
    title: "War room for payment gateway outage",
    status: "awaiting-approval",
    startedAt: "5 min ago",
    duration: "—",
    icon: Users,
    iconColor: "text-red-400",
  },
];

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  completed: { bg: "bg-emerald-500/10", text: "text-emerald-400", label: "Completed" },
  running: { bg: "bg-brand-500/10", text: "text-brand-400", label: "Running" },
  failed: { bg: "bg-red-500/10", text: "text-red-400", label: "Failed" },
  "awaiting-approval": { bg: "bg-amber-500/10", text: "text-amber-400", label: "Needs Approval" },
};

// ── Component ───────────────────────────────────────────────────────────
export default function AgentFactory() {
  const navigate = useNavigate();
  const [persona, setPersona] = useState("sre");
  const [showAllTasks, setShowAllTasks] = useState(false);

  // Filter & sort tasks by persona
  const personaTaskIds = PERSONA_TASKS[persona] ?? [];
  const suggestedTasks = useMemo(() => {
    return ALL_TASKS.filter((t) => personaTaskIds.includes(t.id)).slice(0, 4);
  }, [persona]);

  const moreTasks = useMemo(() => {
    return ALL_TASKS.filter((t) => !suggestedTasks.find((s) => s.id === t.id));
  }, [suggestedTasks]);

  function handlePromptSubmit(prompt: string, context?: string) {
    // Navigate to the agent task execution page
    const params = new URLSearchParams({ prompt });
    if (context) params.set("context", context);
    navigate(`/app/agent-task?${params.toString()}`);
  }

  function handleTaskSelect(task: TaskTemplate) {
    navigate(`/app/agent-task?prompt=${encodeURIComponent(task.prompt)}&template=${task.id}`);
  }

  function handleRunClick(run: RecentRun) {
    navigate(`/app/agent-task?run=${run.id}`);
  }

  return (
    <div className="min-h-full">
      {/* Hero section */}
      <div className="relative overflow-hidden">
        {/* Subtle gradient background */}
        <div className="absolute inset-0 bg-gradient-to-b from-brand-600/5 via-transparent to-transparent" />

        <div className="relative px-4 pt-8 pb-6 sm:px-6 lg:px-8">
          {/* Top row: persona + metrics */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
            <PersonaSwitcher selected={persona} onChange={setPersona} />
            <MetricsBar className="hidden md:flex" />
          </div>

          {/* Title */}
          <div className="max-w-3xl mx-auto text-center mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">
              What do you want to automate?
            </h1>
            <p className="text-gray-400 text-sm">
              Deploy autonomous agents to investigate, remediate, and secure your infrastructure in minutes.
            </p>
          </div>

          {/* Prompt input */}
          <AgentPromptInput
            onSubmit={handlePromptSubmit}
            placeholder="e.g. Investigate the Splunk errors in payment-service and fix the root cause..."
          />
        </div>
      </div>

      {/* Task cards */}
      <div className="px-4 py-6 sm:px-6 lg:px-8">
        {/* Suggested for persona */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="h-4 w-4 text-brand-400" />
            <h2 className="text-sm font-semibold text-gray-300">Suggested for you</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {suggestedTasks.map((task) => (
              <TaskCard key={task.id} task={task} onSelect={handleTaskSelect} />
            ))}
          </div>
        </div>

        {/* More tasks */}
        <div>
          <button
            onClick={() => setShowAllTasks(!showAllTasks)}
            className="flex items-center gap-2 mb-4 text-sm font-medium text-gray-400 hover:text-gray-300 transition-colors"
          >
            {showAllTasks ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
            {showAllTasks ? "Show less" : "More tasks"}
          </button>

          {showAllTasks && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {moreTasks.map((task) => (
                <TaskCard key={task.id} task={task} onSelect={handleTaskSelect} compact />
              ))}
            </div>
          )}
        </div>

        {/* Recent runs */}
        <div className="mt-10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-300">Recent Agent Runs</h2>
            </div>
            <button
              onClick={() => navigate("/app/agent-history")}
              className="text-xs text-gray-500 hover:text-brand-400 transition-colors"
            >
              View all
            </button>
          </div>

          <div className="space-y-2">
            {RECENT_RUNS.map((run) => {
              const status = STATUS_STYLES[run.status];
              return (
                <button
                  key={run.id}
                  onClick={() => handleRunClick(run)}
                  className="flex w-full items-center gap-4 rounded-xl border border-gray-800/50 bg-gray-900/40 px-4 py-3 text-left transition-all hover:border-gray-700 hover:bg-gray-800/40"
                >
                  <run.icon className={`h-4 w-4 shrink-0 ${run.iconColor}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-300 truncate">{run.title}</p>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs text-gray-600">{run.startedAt}</span>
                      <span className="text-xs text-gray-600">
                        <Clock className="inline h-3 w-3 mr-0.5" />
                        {run.duration}
                      </span>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${status.bg} ${status.text}`}
                  >
                    {run.status === "running" && (
                      <Zap className="inline h-3 w-3 mr-1 animate-pulse" />
                    )}
                    {status.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Agent stats footer */}
        <div className="mt-10 rounded-xl border border-gray-800/30 bg-gray-900/30 p-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="text-center">
              <p className="text-xl font-bold text-white">1,247</p>
              <p className="text-xs text-gray-500">Tasks Completed</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-emerald-400">94.2%</p>
              <p className="text-xs text-gray-500">Success Rate</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-brand-400">3.1m</p>
              <p className="text-xs text-gray-500">Avg Resolution</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-amber-400">847h</p>
              <p className="text-xs text-gray-500">Hours Saved</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
