/**
 * Demo mock data for the APIKeys page.
 *
 * Each key has realistic scopes, rate limits, and timestamps computed
 * relative to "now" so the data always looks fresh.
 */

import { pastDate, recentTimestamp } from "./config";

// ── Types (mirrors APIKeys.tsx interface) ────────────────────────────

export interface APIKey {
  key_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  status: "active" | "revoked" | "expired";
  rate_limit_per_minute: number;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
}

// ── Demo API Keys ────────────────────────────────────────────────────

export const DEMO_API_KEYS: APIKey[] = [
  // 1. Production API — active, full agent execution scopes, last used 2 min ago
  {
    key_id: "key_demo_01",
    name: "Production API",
    prefix: "sk_prod_7f",
    scopes: ["read", "write", "agent_execute"],
    status: "active",
    rate_limit_per_minute: 1000,
    created_at: pastDate(60),
    expires_at: new Date(Date.now() + 90 * 86_400_000).toISOString(),
    last_used_at: recentTimestamp(120),
  },

  // 2. CI/CD Pipeline — active, read/write, last used 1 hour ago
  {
    key_id: "key_demo_02",
    name: "CI/CD Pipeline",
    prefix: "sk_cicd_3a",
    scopes: ["read", "write"],
    status: "active",
    rate_limit_per_minute: 500,
    created_at: pastDate(45),
    expires_at: new Date(Date.now() + 45 * 86_400_000).toISOString(),
    last_used_at: recentTimestamp(3600),
  },

  // 3. Monitoring Service — active, read-only, last used 30 seconds ago
  {
    key_id: "key_demo_03",
    name: "Monitoring Service",
    prefix: "sk_mon_e2",
    scopes: ["read"],
    status: "active",
    rate_limit_per_minute: 200,
    created_at: pastDate(90),
    expires_at: null,
    last_used_at: recentTimestamp(30),
  },

  // 4. Old Integration — revoked, previously had read/write/admin
  {
    key_id: "key_demo_04",
    name: "Old Integration",
    prefix: "sk_old_b8",
    scopes: ["read", "write", "admin"],
    status: "revoked",
    rate_limit_per_minute: 500,
    created_at: pastDate(180),
    expires_at: pastDate(30),
    last_used_at: pastDate(35),
  },

  // 5. Staging Key — expired 30 days ago
  {
    key_id: "key_demo_05",
    name: "Staging Key",
    prefix: "sk_stag_d1",
    scopes: ["read", "write"],
    status: "expired",
    rate_limit_per_minute: 300,
    created_at: pastDate(120),
    expires_at: pastDate(30),
    last_used_at: pastDate(31),
  },
];
