export type WarRoomSeverity = "P1" | "P2" | "P3";
export type WarRoomStatus = "active" | "mitigating" | "resolved" | "monitoring";
export type ResponderStatusType = "active" | "paged" | "acknowledged" | "offline";
export type TimelineEventType = "alert" | "action" | "agent" | "human" | "resolved";
export type AgentActivityStatus = "running" | "completed" | "waiting";

export interface WarRoomResponder {
  name: string;
  role: string;
  team: string;
  status: ResponderStatusType;
}

export interface WarRoomTimelineEvent {
  time: string;
  content: string;
  type: TimelineEventType;
}

export interface WarRoomAgentActivity {
  name: string;
  task: string;
  status: AgentActivityStatus;
  progress?: number;
}

export interface WarRoomIncident {
  id: string;
  title: string;
  severity: WarRoomSeverity;
  status: WarRoomStatus;
  startedAt: string;
  duration: string;
  affectedServices: string[];
  responders: WarRoomResponder[];
  timeline: WarRoomTimelineEvent[];
  agents: WarRoomAgentActivity[];
}

export const DEMO_WAR_ROOMS: WarRoomIncident[] = [
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
      {
        time: "14:30",
        content: "Agent correlated with deploy v2.4.1 config change",
        type: "agent",
      },
      {
        time: "14:32",
        content: "Mike Ross confirmed: pool_size changed 50->20 in config",
        type: "human",
      },
      { time: "14:35", content: "Remediation Agent: Preparing config rollback", type: "agent" },
      {
        time: "14:38",
        content: "Config rollback deployed to canary (10% traffic)",
        type: "action",
      },
      { time: "14:42", content: "Canary healthy, expanding to 50%...", type: "action" },
    ],
    agents: [
      {
        name: "Investigation Agent",
        task: "Monitoring recovery metrics",
        status: "running",
        progress: 80,
      },
      {
        name: "Remediation Agent",
        task: "Rolling out config fix to all pods",
        status: "running",
        progress: 55,
      },
      {
        name: "Learning Agent",
        task: "Capturing incident pattern for playbook",
        status: "waiting",
      },
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
      {
        time: "13:45",
        content: "Certificate expiry warning: api-gateway-eu (24h remaining)",
        type: "alert",
      },
      { time: "13:46", content: "Security Agent started certificate audit", type: "agent" },
      {
        time: "13:48",
        content: "Found 3 additional certificates expiring within 7 days",
        type: "agent",
      },
      {
        time: "13:50",
        content: "Auto-renewal initiated for all 4 certificates",
        type: "action",
      },
    ],
    agents: [
      {
        name: "Security Agent",
        task: "Renewing certificates via Let's Encrypt",
        status: "running",
        progress: 60,
      },
    ],
  },
];
