import type { Agent } from "../../api/types";
import { recentTimestamp, pastDate } from "../config";

export function getAgents(): Agent[] {
  return [
    {
      id: "agent-inv-001",
      agent_type: "investigation",
      environment: "production",
      status: "running",
      last_heartbeat: recentTimestamp(5),
      registered_at: pastDate(30),
    },
    {
      id: "agent-rem-001",
      agent_type: "remediation",
      environment: "production",
      status: "idle",
      last_heartbeat: recentTimestamp(12),
      registered_at: pastDate(30),
    },
    {
      id: "agent-sec-001",
      agent_type: "security",
      environment: "production",
      status: "running",
      last_heartbeat: recentTimestamp(3),
      registered_at: pastDate(28),
    },
    {
      id: "agent-cost-001",
      agent_type: "cost",
      environment: "production",
      status: "idle",
      last_heartbeat: recentTimestamp(45),
      registered_at: pastDate(25),
    },
    {
      id: "agent-learn-001",
      agent_type: "learning",
      environment: "production",
      status: "idle",
      last_heartbeat: recentTimestamp(120),
      registered_at: pastDate(25),
    },
    {
      id: "agent-sup-001",
      agent_type: "supervisor",
      environment: "production",
      status: "running",
      last_heartbeat: recentTimestamp(2),
      registered_at: pastDate(30),
    },
  ];
}
