import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Siren,
  Users,
  Clock,
  MessageSquare,
  Activity,
  Phone,
  Plus,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Shield,
  Server,
  Globe,
  Zap,
  ArrowRight,
} from "lucide-react";
import clsx from "clsx";

// ── Types ───────────────────────────────────────────────────────────────
interface WarRoomIncident {
  id: string;
  title: string;
  severity: "P1" | "P2" | "P3";
  status: "active" | "mitigating" | "resolved" | "monitoring";
  startedAt: string;
  duration: string;
  affectedServices: string[];
  responders: Responder[];
  timeline: TimelineEvent[];
  agents: AgentActivity[];
}

interface Responder {
  name: string;
  role: string;
  team: string;
  status: "active" | "paged" | "acknowledged" | "offline";
  avatar?: string;
}

interface TimelineEvent {
  time: string;
  content: string;
  type: "alert" | "action" | "agent" | "human" | "resolved";
}

interface AgentActivity {
  name: string;
  task: string;
  status: "running" | "completed" | "waiting";
  progress?: number;
}

// ── Mock Data ───────────────────────────────────────────────────────────
const ACTIVE_WAR_ROOMS: WarRoomIncident[] = [
  {
    id: "wr-1",
    title: "Payment Gateway Outage - US East",
    severity: "P1",
    status: "mitigating",
    startedAt: "14:23 UTC",
    duration: "42m",
    affectedServices: ["payment-service", "checkout-api", "order-processor"],
    responders: [
      { name: "Sarah Chen", role: "Incident Commander", team: "Payments", status: "active" },
      { name: "Mike Ross", role: "On-Call SRE", team: "Platform", status: "active" },
      { name: "Priya Patel", role: "Backend Lead", team: "Orders", status: "acknowledged" },
      { name: "James Liu", role: "DBA", team: "Data", status: "paged" },
    ],
    timeline: [
      { time: "14:23", content: "PagerDuty alert: payment-service latency > 5s", type: "alert" },
      { time: "14:24", content: "Investigation Agent started root cause analysis", type: "agent" },
      { time: "14:25", content: "Agent identified DB connection pool exhaustion", type: "agent" },
      { time: "14:26", content: "War room created, teams paged automatically", type: "action" },
      { time: "14:28", content: "Sarah Chen acknowledged and joined", type: "human" },
      { time: "14:30", content: "Agent correlated with deploy v2.4.1 config change", type: "agent" },
      { time: "14:32", content: "Mike Ross confirmed: pool_size changed 50->20 in config", type: "human" },
      { time: "14:35", content: "Remediation Agent: Preparing config rollback", type: "agent" },
      { time: "14:38", content: "Config rollback deployed to canary (10% traffic)", type: "action" },
      { time: "14:42", content: "Canary healthy, expanding to 50%...", type: "action" },
    ],
    agents: [
      { name: "Investigation Agent", task: "Monitoring recovery metrics", status: "running", progress: 80 },
      { name: "Remediation Agent", task: "Rolling out config fix to all pods", status: "running", progress: 55 },
      { name: "Learning Agent", task: "Capturing incident pattern for playbook", status: "waiting" },
    ],
  },
  {
    id: "wr-2",
    title: "SSL Certificate Expiry - eu-west-1",
    severity: "P2",
    status: "active",
    startedAt: "13:45 UTC",
    duration: "1h 20m",
    affectedServices: ["api-gateway-eu", "cdn-eu"],
    responders: [
      { name: "Alex Kim", role: "On-Call SRE", team: "Infra", status: "active" },
      { name: "Nina Volkov", role: "Security", team: "SecOps", status: "acknowledged" },
    ],
    timeline: [
      { time: "13:45", content: "Certificate expiry warning: api-gateway-eu (24h remaining)", type: "alert" },
      { time: "13:46", content: "Security Agent started certificate audit", type: "agent" },
      { time: "13:48", content: "Found 3 additional certificates expiring within 7 days", type: "agent" },
      { time: "13:50", content: "Auto-renewal initiated for all 4 certificates", type: "action" },
    ],
    agents: [
      { name: "Security Agent", task: "Renewing certificates via Let's Encrypt", status: "running", progress: 60 },
    ],
  },
];

const SEVERITY_STYLES = {
  P1: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30", dot: "bg-red-400" },
  P2: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/30", dot: "bg-amber-400" },
  P3: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/30", dot: "bg-blue-400" },
};

const STATUS_STYLES = {
  active: { bg: "bg-red-500/10", text: "text-red-400", label: "Active" },
  mitigating: { bg: "bg-amber-500/10", text: "text-amber-400", label: "Mitigating" },
  resolved: { bg: "bg-emerald-500/10", text: "text-emerald-400", label: "Resolved" },
  monitoring: { bg: "bg-blue-500/10", text: "text-blue-400", label: "Monitoring" },
};

const RESPONDER_STATUS = {
  active: { dot: "bg-emerald-400", label: "Active" },
  acknowledged: { dot: "bg-amber-400", label: "Acknowledged" },
  paged: { dot: "bg-red-400 animate-pulse", label: "Paged" },
  offline: { dot: "bg-gray-600", label: "Offline" },
};

const TIMELINE_ICONS = {
  alert: AlertTriangle,
  action: Zap,
  agent: Shield,
  human: Users,
  resolved: CheckCircle2,
};

// ── Component ───────────────────────────────────────────────────────────
export default function WarRoom() {
  const navigate = useNavigate();
  const [selectedRoom, setSelectedRoom] = useState<string>(ACTIVE_WAR_ROOMS[0].id);

  const room = ACTIVE_WAR_ROOMS.find((r) => r.id === selectedRoom) ?? ACTIVE_WAR_ROOMS[0];
  const severity = SEVERITY_STYLES[room.severity];
  const status = STATUS_STYLES[room.status];

  return (
    <div className="flex h-full">
      {/* Left: War room list */}
      <div className="w-80 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <div className="flex items-center gap-2">
            <Siren className="h-4 w-4 text-red-400" />
            <h2 className="text-sm font-semibold text-gray-200">War Rooms</h2>
          </div>
          <button
            onClick={() =>
              navigate(
                "/app/agent-task?prompt=" +
                  encodeURIComponent(
                    "Create a war room for the current critical incident. Identify affected services, page the responsible on-call teams, set up a shared timeline, and coordinate remediation."
                  )
              )
            }
            className="rounded-lg bg-red-600/20 p-1.5 text-red-400 hover:bg-red-600/30 transition-colors"
            title="Create war room"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {ACTIVE_WAR_ROOMS.map((wr) => {
            const sev = SEVERITY_STYLES[wr.severity];
            const st = STATUS_STYLES[wr.status];
            return (
              <button
                key={wr.id}
                onClick={() => setSelectedRoom(wr.id)}
                className={clsx(
                  "w-full rounded-xl border p-3 text-left transition-all",
                  selectedRoom === wr.id
                    ? `${sev.border} bg-gray-800/60`
                    : "border-gray-800/30 bg-gray-900/30 hover:border-gray-700",
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={clsx("text-xs font-bold", sev.text)}>{wr.severity}</span>
                  <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-medium", st.bg, st.text)}>
                    {st.label}
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-200 line-clamp-2">{wr.title}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {wr.duration}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="h-3 w-3" />
                    {wr.responders.length}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: War room detail */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className={clsx("border-b px-6 py-4", severity.border, severity.bg)}>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className={clsx("h-2.5 w-2.5 rounded-full animate-pulse", severity.dot)} />
                <span className={clsx("text-xs font-bold", severity.text)}>{room.severity} INCIDENT</span>
                <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-medium", status.bg, status.text)}>
                  {status.label}
                </span>
              </div>
              <h1 className="text-lg font-bold text-white">{room.title}</h1>
              <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                <span>Started: {room.startedAt}</span>
                <span>Duration: {room.duration}</span>
                <span>{room.affectedServices.length} services affected</span>
              </div>
            </div>
            <button className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-3 py-2 text-xs font-medium text-red-400 hover:bg-red-600/30">
              <Phone className="h-3.5 w-3.5" />
              Page More
            </button>
          </div>

          {/* Affected services */}
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            {room.affectedServices.map((svc) => (
              <span
                key={svc}
                className="inline-flex items-center gap-1.5 rounded-lg bg-gray-900/40 px-2.5 py-1 text-xs font-medium text-gray-300"
              >
                <Server className="h-3 w-3 text-gray-500" />
                {svc}
              </span>
            ))}
          </div>
        </div>

        {/* Content grid */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-0 h-full">
            {/* Timeline */}
            <div className="lg:col-span-2 border-r border-gray-800 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-300 mb-4">
                <Activity className="h-4 w-4 text-gray-500" />
                Incident Timeline
              </h3>
              <div className="space-y-3">
                {room.timeline.map((event, i) => {
                  const Icon = TIMELINE_ICONS[event.type] ?? Activity;
                  return (
                    <div key={i} className="flex items-start gap-3">
                      <span className="shrink-0 text-xs font-mono text-gray-600 w-10 pt-0.5">
                        {event.time}
                      </span>
                      <div className="flex h-5 w-5 items-center justify-center">
                        <Icon
                          className={clsx(
                            "h-3.5 w-3.5",
                            event.type === "alert"
                              ? "text-red-400"
                              : event.type === "agent"
                              ? "text-brand-400"
                              : event.type === "action"
                              ? "text-amber-400"
                              : event.type === "resolved"
                              ? "text-emerald-400"
                              : "text-gray-400",
                          )}
                        />
                      </div>
                      <p className="text-sm text-gray-300 flex-1">{event.content}</p>
                    </div>
                  );
                })}
              </div>

              {/* Agent activities */}
              <div className="mt-6">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-300 mb-3">
                  <Shield className="h-4 w-4 text-brand-400" />
                  Active Agents
                </h3>
                <div className="space-y-2">
                  {room.agents.map((agent, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-gray-800/50 bg-gray-900/30 p-3"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-200">{agent.name}</span>
                        {agent.status === "running" ? (
                          <Loader2 className="h-3.5 w-3.5 text-brand-400 animate-spin" />
                        ) : agent.status === "completed" ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <Clock className="h-3.5 w-3.5 text-gray-600" />
                        )}
                      </div>
                      <p className="text-xs text-gray-500">{agent.task}</p>
                      {agent.progress !== undefined && (
                        <div className="mt-2 h-1 rounded-full bg-gray-800">
                          <div
                            className="h-full rounded-full bg-brand-500 transition-all"
                            style={{ width: `${agent.progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Responders sidebar */}
            <div className="p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-300 mb-4">
                <Users className="h-4 w-4 text-gray-500" />
                Responders ({room.responders.length})
              </h3>
              <div className="space-y-2">
                {room.responders.map((resp, i) => {
                  const rs = RESPONDER_STATUS[resp.status];
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-3 rounded-lg border border-gray-800/30 bg-gray-900/30 p-3"
                    >
                      <div className="relative">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gray-800 text-sm font-medium text-gray-300">
                          {resp.name.split(" ").map((n) => n[0]).join("")}
                        </div>
                        <span
                          className={clsx(
                            "absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-gray-900",
                            rs.dot,
                          )}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-200 truncate">{resp.name}</p>
                        <p className="text-xs text-gray-500">{resp.role}</p>
                        <p className="text-[10px] text-gray-600">{resp.team}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Quick actions */}
              <div className="mt-6">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Quick Actions
                </h3>
                <div className="space-y-1.5">
                  {[
                    { label: "Page additional team", icon: Phone },
                    { label: "Escalate to P1", icon: AlertTriangle },
                    { label: "Open Slack thread", icon: MessageSquare },
                    { label: "View service map", icon: Globe },
                    { label: "Run agent investigation", icon: Shield },
                  ].map((action) => (
                    <button
                      key={action.label}
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
                    >
                      <action.icon className="h-3.5 w-3.5" />
                      {action.label}
                      <ArrowRight className="h-3 w-3 ml-auto text-gray-700" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
