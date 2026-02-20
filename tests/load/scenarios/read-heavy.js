/**
 * Read-heavy scenario -- simulates the dashboard workload where multiple
 * widgets fetch data concurrently.  This is the most realistic day-to-day
 * traffic pattern: lots of paginated GETs, analytics queries, and security
 * posture reads with very few writes.
 *
 * Usage:
 *   k6 run tests/load/scenarios/read-heavy.js
 *   k6 run tests/load/scenarios/read-heavy.js -e PROFILE=stress
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { BASE_URL, STAGES, THRESHOLDS, TEST_EMAIL, TEST_PASSWORD } from '../config.js';
import { login, authHeaders, authGet, randomInt, randomChoice } from '../helpers.js';

const profile = __ENV.PROFILE || 'load';

export const options = {
  stages: STAGES[profile] || STAGES.load,
  thresholds: {
    ...THRESHOLDS,
    // Analytics endpoints may aggregate data and be slightly slower.
    'http_req_duration{name:analytics_mttr}': ['p(95)<400'],
    'http_req_duration{name:analytics_resolution}': ['p(95)<400'],
    'http_req_duration{name:analytics_summary}': ['p(95)<400'],
  },
};

// --- Setup -----------------------------------------------------------------

export function setup() {
  const token = login(TEST_EMAIL, TEST_PASSWORD);
  if (!token) {
    throw new Error('Setup failed: could not authenticate.');
  }
  return { token };
}

// --- VU iteration ----------------------------------------------------------

export default function (data) {
  const token = data.token;

  // ── Dashboard overview widgets ──────────────────────────────────
  group('dashboard_overview', () => {
    // Analytics summary (main dashboard card)
    authGet('/analytics/summary', token, 200, 'analytics_summary');

    // Recent investigations (paginated)
    const invOffset = randomInt(0, 3) * 10;
    authGet(
      `/investigations?limit=10&offset=${invOffset}`,
      token,
      200,
      'list_investigations',
    );

    // Recent remediations (paginated)
    const remOffset = randomInt(0, 3) * 10;
    authGet(
      `/remediations?limit=10&offset=${remOffset}`,
      token,
      200,
      'list_remediations',
    );
  });

  // ── Analytics deep-dive ─────────────────────────────────────────
  group('analytics', () => {
    const period = randomChoice(['7d', '14d', '30d', '90d']);

    authGet(`/analytics/mttr?period=${period}`, token, 200, 'analytics_mttr');
    authGet(`/analytics/resolution-rate?period=${period}`, token, 200, 'analytics_resolution');
    authGet(`/analytics/agent-accuracy?period=${period}`, token, 200, 'analytics_accuracy');
    authGet(`/analytics/cost-savings?period=${period}`, token, 200, 'analytics_cost_savings');
  });

  // ── Security posture ────────────────────────────────────────────
  group('security', () => {
    authGet('/security/scans?limit=10', token, 200, 'list_scans');
    authGet('/security/posture', token, 200, 'security_posture');
    authGet('/security/cves?limit=20', token, 200, 'list_cves');
  });

  // ── Vulnerability management ────────────────────────────────────
  group('vulnerabilities', () => {
    const severity = randomChoice(['critical', 'high', 'medium', 'low']);
    authGet(
      `/vulnerabilities?severity=${severity}&limit=20`,
      token,
      200,
      'list_vulnerabilities',
    );
    authGet('/vulnerabilities/stats', token, 200, 'vulnerability_stats');
    authGet('/vulnerabilities/sla-breaches?limit=10', token, 200, 'sla_breaches');
  });

  // ── Agent fleet ─────────────────────────────────────────────────
  group('agents', () => {
    authGet('/agents', token, 200, 'list_agents');
  });

  sleep(randomInt(1, 3));
}
