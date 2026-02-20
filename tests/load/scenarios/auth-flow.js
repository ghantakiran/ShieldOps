/**
 * Auth flow scenario -- tests the authentication lifecycle:
 *   1. Login (POST /auth/login)
 *   2. Get current user (GET /auth/me)
 *   3. Refresh token (POST /auth/refresh)
 *   4. Verify refreshed token still works (GET /auth/me)
 *
 * This scenario focuses on auth latency and correctness under load.
 *
 * Usage:
 *   k6 run tests/load/scenarios/auth-flow.js
 *   k6 run tests/load/scenarios/auth-flow.js -e PROFILE=stress
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { BASE_URL, STAGES, TEST_EMAIL, TEST_PASSWORD } from '../config.js';
import { authHeaders } from '../helpers.js';

const profile = __ENV.PROFILE || 'load';

// Custom metrics for auth-specific tracking.
const loginDuration = new Trend('auth_login_duration', true);
const refreshDuration = new Trend('auth_refresh_duration', true);
const authFailures = new Counter('auth_failures');

export const options = {
  stages: STAGES[profile] || STAGES.load,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    auth_login_duration: ['p(95)<300', 'p(99)<800'],
    auth_refresh_duration: ['p(95)<200', 'p(99)<500'],
    auth_failures: ['count<10'],
  },
};

// --- VU iteration ----------------------------------------------------------
// No shared setup() -- each VU authenticates independently to test the full
// login flow under concurrency.

export default function () {
  let token = '';

  // ── Step 1: Login ─────────────────────────────────────────────────
  group('login', () => {
    const res = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'auth_login' },
      },
    );

    loginDuration.add(res.timings.duration);

    const ok = check(res, {
      'login status 200': (r) => r.status === 200,
      'login has access_token': (r) => {
        try {
          return typeof r.json('access_token') === 'string';
        } catch (_) {
          return false;
        }
      },
    });

    if (ok) {
      token = res.json('access_token');
    } else {
      authFailures.add(1);
      return; // Skip remaining steps if login failed.
    }
  });

  if (!token) return;

  // ── Step 2: Get current user ──────────────────────────────────────
  group('me', () => {
    const res = http.get(`${BASE_URL}/auth/me`, {
      headers: authHeaders(token),
      tags: { name: 'auth_me' },
    });

    check(res, {
      'me status 200': (r) => r.status === 200,
      'me returns email': (r) => {
        try {
          return r.json('email') === TEST_EMAIL;
        } catch (_) {
          return false;
        }
      },
    });
  });

  // ── Step 3: Refresh token ─────────────────────────────────────────
  group('refresh', () => {
    const res = http.post(`${BASE_URL}/auth/refresh`, null, {
      headers: authHeaders(token),
      tags: { name: 'auth_refresh' },
    });

    refreshDuration.add(res.timings.duration);

    const ok = check(res, {
      'refresh status 200': (r) => r.status === 200,
      'refresh returns new token': (r) => {
        try {
          return typeof r.json('access_token') === 'string';
        } catch (_) {
          return false;
        }
      },
    });

    if (ok) {
      token = res.json('access_token');
    } else {
      authFailures.add(1);
    }
  });

  // ── Step 4: Verify refreshed token ────────────────────────────────
  group('verify_refreshed_token', () => {
    const res = http.get(`${BASE_URL}/auth/me`, {
      headers: authHeaders(token),
      tags: { name: 'auth_me_after_refresh' },
    });

    const ok = check(res, {
      'refreshed token accepted': (r) => r.status === 200,
    });

    if (!ok) {
      authFailures.add(1);
    }
  });

  sleep(1);
}
