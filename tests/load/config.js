/**
 * Shared k6 configuration for ShieldOps load tests.
 *
 * Environment variables:
 *   API_URL  - Base URL for the REST API (default: http://localhost:8000/api/v1)
 *   WS_URL   - Base URL for WebSocket endpoints (default: ws://localhost:8000)
 */

export const BASE_URL = __ENV.API_URL || 'http://localhost:8000/api/v1';
export const WS_URL = __ENV.WS_URL || 'ws://localhost:8000';

// Default credentials used in seeded demo environments.
// Override via TEST_EMAIL / TEST_PASSWORD env vars for non-default setups.
export const TEST_EMAIL = __ENV.TEST_EMAIL || 'admin@shieldops.io';
export const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'admin123';

// --- Thresholds -----------------------------------------------------------
// These are applied globally unless overridden per-scenario.
export const THRESHOLDS = {
  http_req_duration: ['p(95)<200', 'p(99)<500'],
  http_req_failed: ['rate<0.01'],
  http_reqs: ['rate>100'],
};

// Relaxed thresholds for write-heavy or async (202) endpoints.
export const THRESHOLDS_RELAXED = {
  http_req_duration: ['p(95)<500', 'p(99)<1500'],
  http_req_failed: ['rate<0.05'],
};

// --- Stage profiles -------------------------------------------------------

export const STAGES = {
  // Quick validation that the API is alive and responsive.
  smoke: [
    { duration: '30s', target: 5 },
    { duration: '1m', target: 5 },
    { duration: '30s', target: 0 },
  ],

  // Sustained load at expected peak concurrency.
  load: [
    { duration: '2m', target: 50 },
    { duration: '5m', target: 50 },
    { duration: '2m', target: 0 },
  ],

  // Gradually increase beyond expected capacity to find the breaking point.
  stress: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 300 },
    { duration: '5m', target: 300 },
    { duration: '5m', target: 0 },
  ],

  // Sudden burst of traffic to test auto-scaling and circuit breakers.
  spike: [
    { duration: '1m', target: 10 },
    { duration: '10s', target: 500 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 0 },
  ],
};
