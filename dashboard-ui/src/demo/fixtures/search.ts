import type { SearchResponse } from "../../api/types";

export function getSearchResults(query: string): SearchResponse {
  if (!query || query.trim().length < 2) {
    return { query, total: 0, results: [] };
  }

  const q = query.toLowerCase();
  const allResults = [
    {
      entity_type: "investigation" as const,
      id: "inv-001",
      title: "KubePodCrashLooping — payment-service",
      description: "OOM kill due to memory leak in payment-service v2.3.1",
      status: "completed",
      relevance: 1.0,
      url: "/app/investigations/inv-001",
      created_at: null,
    },
    {
      entity_type: "investigation" as const,
      id: "inv-002",
      title: "HighErrorRate5xx — api-gateway-prod",
      description: "Investigating elevated 5xx errors on API gateway",
      status: "in_progress",
      relevance: 0.9,
      url: "/app/investigations/inv-002",
      created_at: null,
    },
    {
      entity_type: "remediation" as const,
      id: "rem-001",
      title: "Rollback payment-service to v2.3.0",
      description: "Rolling back deployment to fix OOM crash loop",
      status: "pending_approval",
      relevance: 0.95,
      url: "/app/remediations/rem-001",
      created_at: null,
    },
    {
      entity_type: "vulnerability" as const,
      id: "vuln-001",
      title: "CVE-2024-21762 — FortiOS RCE",
      description: "Critical out-of-bounds write vulnerability",
      status: "in_progress",
      relevance: 0.85,
      url: "/app/vulnerabilities/vuln-001",
      created_at: null,
    },
    {
      entity_type: "agent" as const,
      id: "agent-inv-001",
      title: "Investigation Agent — production",
      description: "Active investigation agent monitoring production",
      status: "running",
      relevance: 0.7,
      url: "/app",
      created_at: null,
    },
  ];

  const filtered = allResults.filter(
    (r) =>
      r.title.toLowerCase().includes(q) ||
      r.description.toLowerCase().includes(q) ||
      r.entity_type.includes(q),
  );

  return {
    query,
    total: filtered.length,
    results: filtered.length > 0 ? filtered : allResults.slice(0, 3),
  };
}
