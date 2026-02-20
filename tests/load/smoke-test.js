/**
 * Smoke test -- quick validation that the ShieldOps API is alive,
 * authenticated endpoints are reachable, and response times are
 * within acceptable bounds.
 *
 * Usage:
 *   k6 run tests/load/smoke-test.js
 *   k6 run tests/load/smoke-test.js -e API_URL=http://staging:8000/api/v1
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, STAGES, THRESHOLDS, TEST_EMAIL, TEST_PASSWORD } from './config.js';
import { login, authHeaders, authGet } from './helpers.js';

export const options = {
  stages: STAGES.smoke,
  thresholds: THRESHOLDS,
};

// --- Setup (runs once before VU iterations) --------------------------------

export function setup() {
  const token = login(TEST_EMAIL, TEST_PASSWORD);
  if (!token) {
    throw new Error('Setup failed: could not authenticate. Is the API running?');
  }
  return { token };
}

// --- Default VU function ---------------------------------------------------

export default function (data) {
  const headers = authHeaders(data.token);

  // 1. Health check (unauthenticated)
  const health = http.get(`${BASE_URL.replace('/api/v1', '')}/health`, {
    tags: { name: 'health' },
  });
  check(health, {
    'health status 200': (r) => r.status === 200,
    'health body ok': (r) => {
      try {
        return r.json('status') === 'healthy';
      } catch (_) {
        return false;
      }
    },
  });

  // 2. List investigations
  authGet('/investigations?limit=10', data.token, 200, 'list_investigations');

  // 3. List remediations
  authGet('/remediations?limit=10', data.token, 200, 'list_remediations');

  // 4. Current user profile
  authGet('/auth/me', data.token, 200, 'auth_me');

  // 5. Analytics summary
  authGet('/analytics/summary', data.token, 200, 'analytics_summary');

  // 6. Agents fleet
  authGet('/agents', data.token, 200, 'list_agents');

  sleep(1);
}
