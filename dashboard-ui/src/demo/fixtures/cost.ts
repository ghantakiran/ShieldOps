import type { CostSummary } from "../../api/types";
import { recentTimestamp, pastDate } from "../config";

export function getCostSummary(): CostSummary {
  return {
    total_daily: 4_287.42,
    total_monthly: 128_622.60,
    change_percent: 8.3,
    top_services: [
      { service: "Amazon EKS", daily_cost: 1_245.30, monthly_cost: 37_359.00, change_percent: 12.5 },
      { service: "Amazon RDS", daily_cost: 892.10, monthly_cost: 26_763.00, change_percent: 3.2 },
      { service: "Google Cloud Run", daily_cost: 567.80, monthly_cost: 17_034.00, change_percent: -2.1 },
      { service: "Amazon S3", daily_cost: 423.50, monthly_cost: 12_705.00, change_percent: 5.7 },
      { service: "Azure AKS", daily_cost: 389.20, monthly_cost: 11_676.00, change_percent: 1.4 },
      { service: "CloudFlare CDN", daily_cost: 312.40, monthly_cost: 9_372.00, change_percent: -1.8 },
      { service: "Datadog", daily_cost: 234.12, monthly_cost: 7_023.60, change_percent: 15.3 },
      { service: "Amazon ElastiCache", daily_cost: 223.00, monthly_cost: 6_690.00, change_percent: 0.0 },
    ],
    anomalies: [
      {
        service: "Amazon EKS",
        expected: 1_100.00,
        actual: 1_245.30,
        deviation_percent: 13.2,
        detected_at: recentTimestamp(3600),
      },
      {
        service: "Datadog",
        expected: 200.00,
        actual: 234.12,
        deviation_percent: 17.1,
        detected_at: pastDate(1),
      },
    ],
  };
}
