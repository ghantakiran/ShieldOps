import type { AgentPerformanceResponse, HeatmapCell } from "../../api/types";
import { pastDate } from "../config";

export function getAgentPerformance(_period: string = "24h"): AgentPerformanceResponse {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const heatmap: HeatmapCell[] = [];
  for (const day of days) {
    for (let hour = 0; hour < 24; hour++) {
      const isBusinessHours = hour >= 9 && hour <= 18;
      const isWeekend = day === "Sat" || day === "Sun";
      const base = isWeekend ? 2 : isBusinessHours ? 12 : 4;
      heatmap.push({
        hour,
        day,
        count: Math.round(base + Math.random() * base),
      });
    }
  }

  function makeTrend(days: number) {
    const trend = [];
    for (let i = days - 1; i >= 0; i--) {
      trend.push({
        date: pastDate(i),
        executions: Math.round(20 + Math.random() * 30),
        success_rate: 0.85 + Math.random() * 0.14,
      });
    }
    return trend;
  }

  return {
    period: _period,
    summary: {
      total_executions: 1_247,
      avg_success_rate: 0.912,
      avg_duration_seconds: 45.3,
      total_errors: 110,
    },
    agents: [
      {
        agent_type: "investigation",
        total_executions: 520,
        success_rate: 0.93,
        avg_duration_seconds: 62.4,
        error_count: 36,
        p50_duration: 48.0,
        p95_duration: 120.0,
        p99_duration: 180.0,
        trend: makeTrend(7),
      },
      {
        agent_type: "remediation",
        total_executions: 380,
        success_rate: 0.89,
        avg_duration_seconds: 35.7,
        error_count: 42,
        p50_duration: 28.0,
        p95_duration: 85.0,
        p99_duration: 150.0,
        trend: makeTrend(7),
      },
      {
        agent_type: "security",
        total_executions: 210,
        success_rate: 0.95,
        avg_duration_seconds: 42.1,
        error_count: 11,
        p50_duration: 35.0,
        p95_duration: 90.0,
        p99_duration: 140.0,
        trend: makeTrend(7),
      },
      {
        agent_type: "learning",
        total_executions: 137,
        success_rate: 0.88,
        avg_duration_seconds: 28.9,
        error_count: 16,
        p50_duration: 22.0,
        p95_duration: 65.0,
        p99_duration: 110.0,
        trend: makeTrend(7),
      },
    ],
    hourly_heatmap: heatmap,
  };
}
