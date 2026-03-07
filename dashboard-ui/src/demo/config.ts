/** Demo mode detection and constants. */

import type { User } from "../api/types";

export const DEMO_USER: User = {
  id: "demo-user-001",
  email: "demo@shieldops.io",
  name: "Demo User",
  role: "admin",
  is_active: true,
};

export const DEMO_TOKEN = "demo-token-shieldops-2024";

/**
 * Returns true if the app is running in demo mode.
 * Checks URL param `?demo=true` first, then localStorage.
 */
export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  if (params.get("demo") === "true") {
    localStorage.setItem("shieldops_demo", "true");
    return true;
  }
  return localStorage.getItem("shieldops_demo") === "true";
}

/** Timestamps relative to now for realistic fixture data. */
export function recentTimestamp(offsetSeconds: number = 0): string {
  return new Date(Date.now() - offsetSeconds * 1000).toISOString();
}

export function pastDate(daysAgo: number): string {
  return new Date(Date.now() - daysAgo * 86_400_000).toISOString();
}
