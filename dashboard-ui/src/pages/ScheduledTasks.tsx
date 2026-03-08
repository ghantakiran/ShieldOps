import { useState, useEffect, useCallback } from "react";
import {
  Calendar,
  Plus,
  Play,
  Pause,
  Trash2,
  Pencil,
  X,
  Timer,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { get, post, put, del } from "../api/client";
import { isDemoMode, recentTimestamp, pastDate } from "../demo/config";

// ── Types ─────────────────────────────────────────────────────────────

type ScheduleFrequency = "hourly" | "daily" | "weekly" | "monthly" | "cron";

interface ScheduledTask {
  id: string;
  name: string;
  prompt: string;
  workflow_type: string;
  frequency: ScheduleFrequency;
  cron_expression: string | null;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  created_by: string;
  run_count: number;
  last_status: string | null;
}

interface TaskFormData {
  name: string;
  prompt: string;
  workflow_type: string;
  frequency: ScheduleFrequency;
  cron_expression: string;
}

// ── Demo data ─────────────────────────────────────────────────────────

const DEMO_TASKS: ScheduledTask[] = [
  {
    id: "sched-001",
    name: "Nightly Security Scan",
    prompt:
      "Run a comprehensive security scan across all production services. Check for CVEs, exposed secrets, and misconfigurations. Report critical findings to #security-alerts.",
    workflow_type: "security_scan",
    frequency: "daily",
    cron_expression: "0 2 * * *",
    enabled: true,
    last_run_at: recentTimestamp(3600 * 6),
    next_run_at: recentTimestamp(-3600 * 18),
    created_at: pastDate(45),
    created_by: "demo-user-001",
    run_count: 127,
    last_status: "completed",
  },
  {
    id: "sched-002",
    name: "Weekly Cost Report",
    prompt:
      "Generate a weekly cost analysis report. Compare cloud spending across AWS, GCP, and Azure. Highlight anomalies and optimization opportunities over $500.",
    workflow_type: "cost_report",
    frequency: "weekly",
    cron_expression: "0 9 * * 1",
    enabled: true,
    last_run_at: recentTimestamp(3600 * 24 * 3),
    next_run_at: recentTimestamp(-3600 * 24 * 4),
    created_at: pastDate(90),
    created_by: "demo-user-001",
    run_count: 38,
    last_status: "completed",
  },
  {
    id: "sched-003",
    name: "Hourly Health Check",
    prompt:
      "Check health endpoints for all critical services. Verify response times are within SLO thresholds. Alert on-call if any service degrades below 99.9% availability.",
    workflow_type: "health_check",
    frequency: "hourly",
    cron_expression: null,
    enabled: true,
    last_run_at: recentTimestamp(1800),
    next_run_at: recentTimestamp(-1800),
    created_at: pastDate(120),
    created_by: "demo-user-001",
    run_count: 2184,
    last_status: "completed",
  },
  {
    id: "sched-004",
    name: "Monthly Compliance Audit",
    prompt:
      "Run a full compliance audit against SOC 2 and ISO 27001 controls. Generate evidence artifacts, flag control gaps, and update the compliance dashboard.",
    workflow_type: "compliance_audit",
    frequency: "monthly",
    cron_expression: "0 6 1 * *",
    enabled: true,
    last_run_at: recentTimestamp(3600 * 24 * 14),
    next_run_at: recentTimestamp(-3600 * 24 * 16),
    created_at: pastDate(180),
    created_by: "demo-user-001",
    run_count: 11,
    last_status: "completed",
  },
  {
    id: "sched-005",
    name: "Stale Certificate Detection",
    prompt:
      "Scan all TLS certificates across production and staging environments. Flag certificates expiring within 30 days. Auto-renew Let's Encrypt certs and alert on manual renewal needs.",
    workflow_type: "certificate_scan",
    frequency: "daily",
    cron_expression: "0 6 * * *",
    enabled: false,
    last_run_at: recentTimestamp(3600 * 24 * 5),
    next_run_at: null,
    created_at: pastDate(60),
    created_by: "demo-user-001",
    run_count: 42,
    last_status: "completed",
  },
  {
    id: "sched-006",
    name: "Infrastructure Drift Check",
    prompt:
      "Compare live infrastructure state against Terraform definitions. Identify configuration drift in AWS, GCP, and Kubernetes clusters. Generate drift reports and auto-create remediation PRs.",
    workflow_type: "drift_detection",
    frequency: "cron",
    cron_expression: "0 */6 * * *",
    enabled: true,
    last_run_at: recentTimestamp(3600 * 2),
    next_run_at: recentTimestamp(-3600 * 4),
    created_at: pastDate(30),
    created_by: "demo-user-001",
    run_count: 96,
    last_status: "failed",
  },
];

// ── Helpers ───────────────────────────────────────────────────────────

const FREQUENCY_BADGE: Record<ScheduleFrequency, { bg: string; text: string }> = {
  hourly: { bg: "bg-blue-500/10 ring-blue-500/20", text: "text-blue-400" },
  daily: { bg: "bg-green-500/10 ring-green-500/20", text: "text-green-400" },
  weekly: { bg: "bg-amber-500/10 ring-amber-500/20", text: "text-amber-400" },
  monthly: { bg: "bg-brand-500/10 ring-brand-500/20", text: "text-brand-400" },
  cron: { bg: "bg-gray-500/10 ring-gray-500/20", text: "text-gray-400" },
};

const WORKFLOW_LABELS: Record<string, string> = {
  security_scan: "Security Scan",
  cost_report: "Cost Report",
  health_check: "Health Check",
  compliance_audit: "Compliance Audit",
  certificate_scan: "Certificate Scan",
  drift_detection: "Drift Detection",
};

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const absDiff = Math.abs(diff);
  const isFuture = diff < 0;
  const seconds = Math.floor(absDiff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  let label: string;
  if (days > 0) label = `${days}d`;
  else if (hours > 0) label = `${hours}h`;
  else if (minutes > 0) label = `${minutes}m`;
  else label = `${seconds}s`;

  return isFuture ? `in ${label}` : `${label} ago`;
}

const EMPTY_FORM: TaskFormData = {
  name: "",
  prompt: "",
  workflow_type: "security_scan",
  frequency: "daily",
  cron_expression: "",
};

// ── Component ─────────────────────────────────────────────────────────

export default function ScheduledTasks() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
  const [form, setForm] = useState<TaskFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      if (isDemoMode()) {
        setTasks(DEMO_TASKS);
      } else {
        const res = await get<{ items: ScheduledTask[] }>("/scheduled-tasks");
        setTasks(res.items);
      }
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // ── Stats ─────────────────────────────────────────────────

  const totalCount = tasks.length;
  const activeCount = tasks.filter((t) => t.enabled).length;
  const pausedCount = tasks.filter((t) => !t.enabled).length;
  const runsThisWeek = tasks.reduce((sum, t) => {
    if (!t.last_run_at) return sum;
    const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
    return new Date(t.last_run_at).getTime() > weekAgo ? sum + 1 : sum;
  }, 0);

  // ── Actions ───────────────────────────────────────────────

  function openCreate() {
    setEditingTask(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  }

  function openEdit(task: ScheduledTask) {
    setEditingTask(task);
    setForm({
      name: task.name,
      prompt: task.prompt,
      workflow_type: task.workflow_type,
      frequency: task.frequency,
      cron_expression: task.cron_expression ?? "",
    });
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingTask(null);
    setForm(EMPTY_FORM);
  }

  async function handleSubmit() {
    if (!form.name.trim() || !form.prompt.trim()) return;
    setSubmitting(true);
    try {
      if (isDemoMode()) {
        if (editingTask) {
          setTasks((prev) =>
            prev.map((t) =>
              t.id === editingTask.id
                ? {
                    ...t,
                    name: form.name,
                    prompt: form.prompt,
                    workflow_type: form.workflow_type,
                    frequency: form.frequency,
                    cron_expression: form.frequency === "cron" ? form.cron_expression : null,
                  }
                : t,
            ),
          );
        } else {
          const newTask: ScheduledTask = {
            id: `sched-${Date.now()}`,
            name: form.name,
            prompt: form.prompt,
            workflow_type: form.workflow_type,
            frequency: form.frequency,
            cron_expression: form.frequency === "cron" ? form.cron_expression : null,
            enabled: true,
            last_run_at: null,
            next_run_at: null,
            created_at: new Date().toISOString(),
            created_by: "demo-user-001",
            run_count: 0,
            last_status: null,
          };
          setTasks((prev) => [newTask, ...prev]);
        }
      } else if (editingTask) {
        const updated = await put<ScheduledTask>(`/scheduled-tasks/${editingTask.id}`, {
          name: form.name,
          prompt: form.prompt,
          frequency: form.frequency,
          cron_expression: form.frequency === "cron" ? form.cron_expression : null,
        });
        setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      } else {
        const created = await post<ScheduledTask>("/scheduled-tasks", {
          name: form.name,
          prompt: form.prompt,
          workflow_type: form.workflow_type,
          frequency: form.frequency,
          cron_expression: form.frequency === "cron" ? form.cron_expression : null,
        });
        setTasks((prev) => [created, ...prev]);
      }
      closeModal();
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(task: ScheduledTask) {
    const newEnabled = !task.enabled;
    if (isDemoMode()) {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, enabled: newEnabled } : t)));
    } else {
      const updated = await put<ScheduledTask>(`/scheduled-tasks/${task.id}`, {
        enabled: newEnabled,
      });
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    }
  }

  async function handleTrigger(task: ScheduledTask) {
    if (isDemoMode()) {
      setTasks((prev) =>
        prev.map((t) =>
          t.id === task.id
            ? {
                ...t,
                last_run_at: new Date().toISOString(),
                run_count: t.run_count + 1,
                last_status: "triggered",
              }
            : t,
        ),
      );
    } else {
      await post(`/scheduled-tasks/${task.id}/trigger`);
      await fetchTasks();
    }
  }

  async function handleDelete(task: ScheduledTask) {
    if (isDemoMode()) {
      setTasks((prev) => prev.filter((t) => t.id !== task.id));
    } else {
      await del(`/scheduled-tasks/${task.id}`);
      setTasks((prev) => prev.filter((t) => t.id !== task.id));
    }
  }

  // ── Render ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-gray-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Scheduled Tasks</h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure recurring agent tasks that run on a schedule.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
        >
          <Plus className="h-4 w-4" />
          Create Schedule
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Total", value: totalCount, icon: Calendar, color: "text-gray-300" },
          { label: "Active", value: activeCount, icon: CheckCircle2, color: "text-emerald-400" },
          { label: "Paused", value: pausedCount, icon: Pause, color: "text-gray-400" },
          { label: "Runs This Week", value: runsThisWeek, icon: Timer, color: "text-blue-400" },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-gray-800 bg-gray-900 px-4 py-3"
          >
            <div className="flex items-center gap-2">
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
              <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
                {stat.label}
              </span>
            </div>
            <p className={`mt-1 text-2xl font-semibold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Task list */}
      {tasks.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-12 text-center">
          <Calendar className="mx-auto h-8 w-8 text-gray-600" />
          <p className="mt-2 text-sm text-gray-500">
            No scheduled tasks yet. Create one to get started.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full min-w-[800px] text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Task
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Frequency
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Last Run
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Next Run
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Runs
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 bg-gray-950">
              {tasks.map((task) => {
                const badge = FREQUENCY_BADGE[task.frequency];
                return (
                  <tr key={task.id} className="transition-colors hover:bg-gray-900/50">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-100">{task.name}</p>
                        <p className="mt-0.5 line-clamp-1 text-xs text-gray-500">{task.prompt}</p>
                        <span className="mt-1 inline-block text-xs text-gray-600">
                          {WORKFLOW_LABELS[task.workflow_type] ?? task.workflow_type}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${badge.bg} ${badge.text}`}
                      >
                        {task.frequency}
                      </span>
                      {task.cron_expression && (
                        <span className="ml-1.5 text-xs text-gray-600">
                          {task.cron_expression}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => handleToggle(task)}
                        className="group flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-brand-500/50 rounded"
                        aria-label={`${task.enabled ? "Disable" : "Enable"} ${task.name}`}
                      >
                        {task.enabled ? (
                          <>
                            <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
                            <span className="text-xs font-medium text-emerald-400 group-hover:text-emerald-300">
                              Enabled
                            </span>
                          </>
                        ) : (
                          <>
                            <span className="inline-block h-2 w-2 rounded-full bg-gray-500" />
                            <span className="text-xs font-medium text-gray-500 group-hover:text-gray-400">
                              Disabled
                            </span>
                          </>
                        )}
                      </button>
                      {task.last_status && (
                        <div className="mt-1 flex items-center gap-1">
                          {task.last_status === "completed" || task.last_status === "triggered" ? (
                            <CheckCircle2 className="h-3 w-3 text-green-500" />
                          ) : (
                            <AlertCircle className="h-3 w-3 text-red-500" />
                          )}
                          <span className="text-xs text-gray-600">{task.last_status}</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {task.last_run_at ? formatRelativeTime(task.last_run_at) : "--"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {task.enabled && task.next_run_at
                        ? formatRelativeTime(task.next_run_at)
                        : "--"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {task.run_count.toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(task)}
                          aria-label={`Edit ${task.name}`}
                          title="Edit"
                          className="rounded p-1.5 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleTrigger(task)}
                          aria-label={`Trigger ${task.name} now`}
                          title="Trigger Now"
                          className="rounded p-1.5 text-gray-500 transition-colors hover:bg-brand-500/10 hover:text-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                        >
                          <Play className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(task)}
                          aria-label={`Delete ${task.name}`}
                          title="Delete"
                          className="rounded p-1.5 text-gray-500 transition-colors hover:bg-red-500/10 hover:text-red-400 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" role="dialog" aria-modal="true" aria-label={editingTask ? "Edit schedule" : "Create schedule"}>
          <div className="w-full max-w-lg rounded-xl border border-gray-800 bg-gray-900 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
              <h2 className="text-lg font-semibold text-gray-100">
                {editingTask ? "Edit Schedule" : "Create Schedule"}
              </h2>
              <button
                type="button"
                onClick={closeModal}
                className="rounded p-1 text-gray-500 transition-colors hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                aria-label="Close dialog"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4 px-6 py-5">
              {/* Name */}
              <div>
                <label htmlFor="sched-name" className="mb-1 block text-xs font-medium text-gray-400">Name</label>
                <input
                  id="sched-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Nightly Security Scan"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>

              {/* Prompt */}
              <div>
                <label htmlFor="sched-prompt" className="mb-1 block text-xs font-medium text-gray-400">
                  Agent Prompt
                </label>
                <textarea
                  id="sched-prompt"
                  value={form.prompt}
                  onChange={(e) => setForm((f) => ({ ...f, prompt: e.target.value }))}
                  placeholder="Describe what the agent should do..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>

              {/* Workflow type */}
              <div>
                <label htmlFor="sched-workflow" className="mb-1 block text-xs font-medium text-gray-400">
                  Workflow Type
                </label>
                <select
                  id="sched-workflow"
                  value={form.workflow_type}
                  onChange={(e) => setForm((f) => ({ ...f, workflow_type: e.target.value }))}
                  disabled={!!editingTask}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-50"
                >
                  {Object.entries(WORKFLOW_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Frequency */}
              <div>
                <label htmlFor="sched-frequency" className="mb-1 block text-xs font-medium text-gray-400">Frequency</label>
                <select
                  id="sched-frequency"
                  value={form.frequency}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, frequency: e.target.value as ScheduleFrequency }))
                  }
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                >
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="cron">Custom Cron</option>
                </select>
              </div>

              {/* Cron expression (conditional) */}
              {form.frequency === "cron" && (
                <div>
                  <label htmlFor="sched-cron" className="mb-1 block text-xs font-medium text-gray-400">
                    Cron Expression
                  </label>
                  <input
                    id="sched-cron"
                    type="text"
                    value={form.cron_expression}
                    onChange={(e) => setForm((f) => ({ ...f, cron_expression: e.target.value }))}
                    placeholder="0 */6 * * *"
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono text-gray-100 placeholder-gray-600 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  />
                  <p className="mt-1 text-xs text-gray-600">
                    Standard cron syntax: minute hour day month weekday
                  </p>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-gray-800 px-6 py-4">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || !form.name.trim() || !form.prompt.trim()}
                className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
              >
                {submitting && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                {editingTask ? "Save Changes" : "Create Schedule"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
