import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Loader2,
  AlertTriangle,
  ShieldCheck,
  Clock,
  ThumbsUp,
  ThumbsDown,
  XCircle,
  Send,
  ChevronRight,
  Terminal,
  Eye,
  FileText,
  GitPullRequest,
  MessageSquare,
  Zap,
  Wifi,
  WifiOff,
} from "lucide-react";
import clsx from "clsx";
import { useAgentTaskStream } from "../hooks/useAgentTaskStream";
import { isDemoMode } from "../demo/config";

// ── Types ───────────────────────────────────────────────────────────────
type StepStatus = "pending" | "running" | "completed" | "failed" | "approval-required";

interface AgentStep {
  id: string;
  title: string;
  description: string;
  status: StepStatus;
  duration?: string;
  output?: string;
  substeps?: { label: string; done: boolean }[];
  requiresApproval?: boolean;
  artifacts?: { type: "pr" | "file" | "log" | "alert"; label: string; url?: string }[];
}

interface AgentMessage {
  id: string;
  role: "agent" | "user" | "system";
  content: string;
  timestamp: string;
}

// ── Mock simulation steps ───────────────────────────────────────────────
function generateSteps(prompt: string): AgentStep[] {
  const isSecurityTask = /vulnerab|cve|security|threat|scan/i.test(prompt);
  const isIncidentTask = /incident|error|splunk|investigate|root cause/i.test(prompt);
  const isWarRoom = /war room|page|coordinate/i.test(prompt);

  if (isWarRoom) {
    return [
      {
        id: "s1",
        title: "Identify affected services",
        description: "Analyzing alert data to determine blast radius and impacted services",
        status: "completed",
        duration: "8s",
        output: "Affected: payment-service, checkout-api, order-processor\nRegion: us-east-1\nSeverity: P1",
        substeps: [
          { label: "Queried PagerDuty for active incidents", done: true },
          { label: "Correlated with service dependency graph", done: true },
          { label: "Identified 3 affected services", done: true },
        ],
      },
      {
        id: "s2",
        title: "Page responsible teams",
        description: "Looking up service ownership and paging on-call engineers",
        status: "completed",
        duration: "4s",
        output: "Paged:\n- @payments-oncall (Sarah Chen) - payment-service\n- @platform-oncall (Mike Ross) - checkout-api\n- @data-oncall (Priya Patel) - order-processor",
        substeps: [
          { label: "Resolved service ownership from catalog", done: true },
          { label: "Found on-call schedules", done: true },
          { label: "Sent Slack DMs + PagerDuty pages", done: true },
        ],
      },
      {
        id: "s3",
        title: "Create war room channel",
        description: "Setting up dedicated Slack channel with all responders",
        status: "running",
        substeps: [
          { label: "Created #war-room-payment-outage-0307", done: true },
          { label: "Invited all on-call engineers", done: true },
          { label: "Posting incident timeline...", done: false },
        ],
      },
      {
        id: "s4",
        title: "Initialize shared timeline",
        description: "Create a real-time incident timeline with all context",
        status: "pending",
      },
      {
        id: "s5",
        title: "Begin parallel investigation",
        description: "Agents investigating each service simultaneously",
        status: "pending",
      },
    ];
  }

  if (isSecurityTask) {
    return [
      {
        id: "s1",
        title: "Scanning repositories and infrastructure",
        description: "Running security scans across codebases and cloud configurations",
        status: "completed",
        duration: "45s",
        output: "Scanned 12 repositories, 3 cloud accounts\nFound 23 findings (4 critical, 7 high, 12 medium)",
        substeps: [
          { label: "Scanned GitHub repos for dependency CVEs", done: true },
          { label: "Checked AWS/GCP security groups", done: true },
          { label: "Scanned container images", done: true },
          { label: "Checked for exposed secrets", done: true },
        ],
      },
      {
        id: "s2",
        title: "Prioritizing findings by risk",
        description: "Correlating CVEs with EPSS scores, reachability, and exposure",
        status: "completed",
        duration: "12s",
        output: "Top Critical:\n1. CVE-2024-3094 (xz-utils) - CVSS 10.0 - auth-service\n2. CVE-2024-21626 (runc) - CVSS 8.6 - all containers\n3. Open S3 bucket: logs-backup-prod\n4. Exposed API key in env vars: billing-service",
      },
      {
        id: "s3",
        title: "Generating fix patches",
        description: "Creating automated patches for critical and high vulnerabilities",
        status: "running",
        substeps: [
          { label: "Generated patch for CVE-2024-3094", done: true },
          { label: "Generated runc upgrade manifest", done: true },
          { label: "Creating S3 bucket policy fix...", done: false },
          { label: "Rotating exposed API key...", done: false },
        ],
      },
      {
        id: "s4",
        title: "Policy evaluation",
        description: "Evaluating all patches against OPA security policies",
        status: "pending",
        requiresApproval: true,
      },
      {
        id: "s5",
        title: "Apply remediations",
        description: "Deploy fixes and verify resolution",
        status: "pending",
        artifacts: [
          { type: "pr", label: "PR #342: Fix CVE-2024-3094 in auth-service" },
          { type: "pr", label: "PR #343: Upgrade runc to 1.1.12" },
          { type: "file", label: "Security scan report" },
        ],
      },
    ];
  }

  if (isIncidentTask) {
    return [
      {
        id: "s1",
        title: "Collecting signals",
        description: "Gathering logs, metrics, and traces from observability stack",
        status: "completed",
        duration: "15s",
        output: "Collected:\n- 12,847 log lines from Splunk (last 1h)\n- 34 metric anomalies from Datadog\n- 156 error traces from Jaeger\n- 3 related PagerDuty alerts",
        substeps: [
          { label: "Queried Splunk for error patterns", done: true },
          { label: "Pulled Datadog metric anomalies", done: true },
          { label: "Fetched distributed traces", done: true },
          { label: "Correlated PagerDuty alerts", done: true },
        ],
      },
      {
        id: "s2",
        title: "Root cause analysis",
        description: "Correlating signals to identify the root cause",
        status: "completed",
        duration: "22s",
        output: "Root Cause Identified:\n\nDatabase connection pool exhaustion in payment-service.\n\nTimeline:\n- 14:23 UTC: Deploy v2.4.1 changed pool size from 50 -> 20 (config regression)\n- 14:25 UTC: Connection timeouts started\n- 14:27 UTC: Cascading failures to checkout-api\n\nConfidence: 94%",
      },
      {
        id: "s3",
        title: "Generating remediation plan",
        description: "Creating a safe remediation strategy with rollback",
        status: "running",
        substeps: [
          { label: "Identified config change to revert", done: true },
          { label: "Verified rollback safety", done: true },
          { label: "Preparing deployment...", done: false },
        ],
      },
      {
        id: "s4",
        title: "Approval gate",
        description: "Remediation requires approval before execution",
        status: "pending",
        requiresApproval: true,
      },
      {
        id: "s5",
        title: "Execute remediation & verify",
        description: "Apply fix and confirm service recovery",
        status: "pending",
        artifacts: [
          { type: "pr", label: "PR #341: Revert connection pool config" },
          { type: "log", label: "Investigation report" },
          { type: "alert", label: "PagerDuty incident resolved" },
        ],
      },
    ];
  }

  // Generic task steps
  return [
    {
      id: "s1",
      title: "Understanding request",
      description: "Analyzing your prompt and planning the execution strategy",
      status: "completed",
      duration: "3s",
      output: `Parsed intent: "${prompt.slice(0, 80)}..."\nPlanned 4 execution phases.`,
    },
    {
      id: "s2",
      title: "Gathering context",
      description: "Collecting relevant data from connected integrations",
      status: "completed",
      duration: "18s",
    },
    {
      id: "s3",
      title: "Executing agent workflow",
      description: "Running the planned actions with safety checks",
      status: "running",
      substeps: [
        { label: "Phase 1: Analysis complete", done: true },
        { label: "Phase 2: Generating changes...", done: false },
        { label: "Phase 3: Validation pending", done: false },
      ],
    },
    {
      id: "s4",
      title: "Review & apply",
      description: "Final review and application of changes",
      status: "pending",
      requiresApproval: true,
    },
  ];
}

// ── Step icon helper ────────────────────────────────────────────────────
function StepIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-emerald-400" />;
    case "running":
      return <Loader2 className="h-5 w-5 text-brand-400 animate-spin" />;
    case "failed":
      return <XCircle className="h-5 w-5 text-red-400" />;
    case "approval-required":
      return <ShieldCheck className="h-5 w-5 text-amber-400" />;
    default:
      return <Circle className="h-5 w-5 text-gray-700" />;
  }
}

// ── Artifact icon helper ────────────────────────────────────────────────
function ArtifactIcon({ type }: { type: string }) {
  switch (type) {
    case "pr":
      return <GitPullRequest className="h-3.5 w-3.5 text-green-400" />;
    case "file":
      return <FileText className="h-3.5 w-3.5 text-blue-400" />;
    case "log":
      return <Terminal className="h-3.5 w-3.5 text-gray-400" />;
    case "alert":
      return <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />;
    default:
      return <Eye className="h-3.5 w-3.5 text-gray-400" />;
  }
}

// ── Main Component ──────────────────────────────────────────────────────
export default function AgentTask() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const prompt = searchParams.get("prompt") ?? "Running agent task...";
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [userInput, setUserInput] = useState("");
  const [elapsedTime, setElapsedTime] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [taskId] = useState<string | null>(() => searchParams.get("run") ?? (isDemoMode() ? `task-demo-${Date.now()}` : null));

  // WebSocket streaming for real-time step updates
  const handleWsEvent = useCallback((wsEvent: import("../api/types").AgentTaskWsEvent) => {
    if (wsEvent.event === "step_update" && wsEvent.step_id) {
      setSteps((prev) =>
        prev.map((s) =>
          s.id === wsEvent.step_id
            ? { ...s, status: (wsEvent.status ?? s.status) as StepStatus }
            : s,
        ),
      );
    }
    if (wsEvent.event === "task_complete") {
      setMessages((prev) => [
        ...prev,
        { id: `m-done-${Date.now()}`, role: "system", content: "Task completed.", timestamp: new Date().toLocaleTimeString() },
      ]);
    }
  }, []);

  const { connected } = useAgentTaskStream(taskId, handleWsEvent);

  // Initialize steps
  useEffect(() => {
    setSteps(generateSteps(prompt));
    setMessages([
      {
        id: "m1",
        role: "system",
        content: "Agent initialized. Executing task...",
        timestamp: new Date().toLocaleTimeString(),
      },
      {
        id: "m2",
        role: "agent",
        content: `I'm working on: "${prompt.length > 120 ? prompt.slice(0, 120) + "..." : prompt}"\n\nI'll walk you through each step and ask for approval when needed.`,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
  }, [prompt]);

  // Demo mode: auto-progress steps to simulate agent execution
  useEffect(() => {
    if (!isDemoMode()) return;
    const timer = setInterval(() => {
      setSteps((prev) => {
        const runningIdx = prev.findIndex((s) => s.status === "running");
        if (runningIdx === -1) return prev;
        const next = [...prev];
        const current = { ...next[runningIdx] };
        // Progress substeps first
        if (current.substeps) {
          const unfinished = current.substeps.findIndex((sub) => !sub.done);
          if (unfinished !== -1) {
            current.substeps = current.substeps.map((sub, i) =>
              i === unfinished ? { ...sub, done: true } : sub,
            );
            next[runningIdx] = current;
            return next;
          }
        }
        // Complete current step
        current.status = "completed";
        current.duration = current.duration ?? `${Math.floor(Math.random() * 20 + 5)}s`;
        next[runningIdx] = current;
        // Advance next pending step
        const nextPending = next.findIndex((s, i) => i > runningIdx && s.status === "pending");
        if (nextPending !== -1) {
          const upcoming = { ...next[nextPending] };
          upcoming.status = upcoming.requiresApproval ? "approval-required" : "running";
          next[nextPending] = upcoming;
        }
        return next;
      });
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  // Timer
  useEffect(() => {
    const interval = setInterval(() => setElapsedTime((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function toggleStep(id: string) {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleApprove(stepId: string) {
    setSteps((prev) =>
      prev.map((s) =>
        s.id === stepId ? { ...s, status: "completed" as StepStatus } : s,
      ),
    );
    setMessages((prev) => [
      ...prev,
      {
        id: `m-approve-${stepId}`,
        role: "user",
        content: "Approved. Proceed with execution.",
        timestamp: new Date().toLocaleTimeString(),
      },
      {
        id: `m-ack-${stepId}`,
        role: "agent",
        content: "Approval received. Continuing execution...",
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
  }

  function handleReject(stepId: string) {
    setSteps((prev) =>
      prev.map((s) =>
        s.id === stepId ? { ...s, status: "failed" as StepStatus } : s,
      ),
    );
    setMessages((prev) => [
      ...prev,
      {
        id: `m-reject-${stepId}`,
        role: "user",
        content: "Rejected. Do not proceed.",
        timestamp: new Date().toLocaleTimeString(),
      },
      {
        id: `m-halt-${stepId}`,
        role: "agent",
        content: "Understood. Halting this step. Let me know if you'd like to adjust the approach.",
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
  }

  function handleSendMessage() {
    if (!userInput.trim()) return;
    setMessages((prev) => [
      ...prev,
      {
        id: `m-user-${Date.now()}`,
        role: "user",
        content: userInput.trim(),
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
    setUserInput("");
    // Simulate agent response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `m-agent-${Date.now()}`,
          role: "agent",
          content:
            "I understand. Let me adjust my approach based on your input and continue the investigation.",
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    }, 1500);
  }

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const runningStep = steps.find((s) => s.status === "running");
  const completedCount = steps.filter((s) => s.status === "completed").length;

  return (
    <div className="flex h-full">
      {/* Left panel: Steps */}
      <div className="flex w-full flex-col lg:w-[55%] border-r border-gray-800">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/app")}
              className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <h1 className="text-sm font-semibold text-gray-200 line-clamp-1 max-w-md">
                {prompt.length > 60 ? prompt.slice(0, 60) + "..." : prompt}
              </h1>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-xs text-gray-500">
                  <Clock className="inline h-3 w-3 mr-1" />
                  {formatTime(elapsedTime)}
                </span>
                <span className="text-xs text-gray-500">
                  {completedCount}/{steps.length} steps
                </span>
                {runningStep && (
                  <span className="text-xs text-brand-400 flex items-center gap-1">
                    <Zap className="h-3 w-3 animate-pulse" />
                    {runningStep.title}
                  </span>
                )}
                {taskId && (
                  <span className={clsx("text-xs flex items-center gap-1", connected ? "text-emerald-500" : "text-gray-600")}>
                    {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                    {connected ? "Live" : "Offline"}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Steps list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {steps.map((step, i) => {
            const isExpanded = expandedSteps.has(step.id) || step.status === "running";

            return (
              <div
                key={step.id}
                className={clsx(
                  "rounded-xl border transition-all",
                  step.status === "running"
                    ? "border-brand-500/30 bg-brand-500/5"
                    : step.status === "completed"
                    ? "border-gray-800/50 bg-gray-900/30"
                    : step.status === "failed"
                    ? "border-red-500/30 bg-red-500/5"
                    : "border-gray-800/30 bg-gray-900/20",
                )}
              >
                {/* Step header */}
                <button
                  onClick={() => toggleStep(step.id)}
                  className="flex w-full items-center gap-3 p-3 text-left"
                >
                  <StepIcon status={step.status} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-600">
                        Step {i + 1}
                      </span>
                      {step.duration && (
                        <span className="text-[10px] text-gray-600">{step.duration}</span>
                      )}
                    </div>
                    <p className="text-sm font-medium text-gray-200">{step.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{step.description}</p>
                  </div>
                  {(step.output || step.substeps) && (
                    <ChevronRight
                      className={clsx(
                        "h-4 w-4 text-gray-600 transition-transform",
                        isExpanded && "rotate-90",
                      )}
                    />
                  )}
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-gray-800/30 px-4 py-3 space-y-3">
                    {/* Substeps */}
                    {step.substeps && (
                      <div className="space-y-1.5">
                        {step.substeps.map((sub, j) => (
                          <div key={j} className="flex items-center gap-2 text-xs">
                            {sub.done ? (
                              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400/70" />
                            ) : (
                              <Loader2 className="h-3.5 w-3.5 text-brand-400/70 animate-spin" />
                            )}
                            <span
                              className={
                                sub.done ? "text-gray-400" : "text-gray-300"
                              }
                            >
                              {sub.label}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Output */}
                    {step.output && (
                      <pre className="rounded-lg bg-gray-950/60 p-3 text-xs text-gray-400 font-mono whitespace-pre-wrap overflow-x-auto">
                        {step.output}
                      </pre>
                    )}

                    {/* Artifacts */}
                    {step.artifacts && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-gray-500">Artifacts</p>
                        {step.artifacts.map((art, j) => (
                          <div
                            key={j}
                            className="flex items-center gap-2 rounded-lg bg-gray-800/30 px-3 py-2 text-xs text-gray-300"
                          >
                            <ArtifactIcon type={art.type} />
                            {art.label}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Approval buttons */}
                    {step.requiresApproval && step.status === "pending" && (
                      <div className="flex items-center gap-2 pt-2">
                        <button
                          onClick={() => handleApprove(step.id)}
                          className="flex items-center gap-1.5 rounded-lg bg-emerald-600/20 px-4 py-2 text-xs font-medium text-emerald-400 hover:bg-emerald-600/30 transition-colors"
                        >
                          <ThumbsUp className="h-3.5 w-3.5" />
                          Approve
                        </button>
                        <button
                          onClick={() => handleReject(step.id)}
                          className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-4 py-2 text-xs font-medium text-red-400 hover:bg-red-600/30 transition-colors"
                        >
                          <ThumbsDown className="h-3.5 w-3.5" />
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right panel: Chat */}
      <div className="hidden lg:flex flex-col flex-1">
        <div className="flex items-center gap-2 border-b border-gray-800 px-4 py-3">
          <MessageSquare className="h-4 w-4 text-gray-500" />
          <h2 className="text-sm font-semibold text-gray-300">Agent Chat</h2>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={clsx(
                "max-w-[85%] rounded-xl px-4 py-2.5",
                msg.role === "user"
                  ? "ml-auto bg-brand-600/20 text-brand-100"
                  : msg.role === "system"
                  ? "mx-auto text-center bg-gray-800/30 text-gray-500 text-xs max-w-full"
                  : "bg-gray-800/40 text-gray-300",
              )}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              <p className="text-[10px] text-gray-600 mt-1">{msg.timestamp}</p>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat input */}
        <div className="border-t border-gray-800 p-3">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              placeholder="Ask the agent or provide guidance..."
              className="flex-1 rounded-xl border border-gray-700 bg-gray-800/50 px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 focus:border-brand-500/50 focus:outline-none"
            />
            <button
              onClick={handleSendMessage}
              disabled={!userInput.trim()}
              className={clsx(
                "rounded-xl p-2.5 transition-colors",
                userInput.trim()
                  ? "bg-brand-600 text-white hover:bg-brand-500"
                  : "bg-gray-800 text-gray-600",
              )}
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
