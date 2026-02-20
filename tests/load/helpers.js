/**
 * Shared helpers for ShieldOps k6 load tests.
 *
 * Provides authentication utilities and common request patterns
 * so individual scenarios stay focused on the workload logic.
 */

import http from 'k6/http';
import { check } from 'k6';
import { BASE_URL } from './config.js';

/**
 * Authenticate against the ShieldOps API and return an access token.
 *
 * @param {string} email    - User email address.
 * @param {string} password - User password.
 * @returns {string} JWT access token (empty string on failure).
 */
export function login(email, password) {
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'login' } },
  );

  const ok = check(res, {
    'login status 200': (r) => r.status === 200,
    'login returns token': (r) => {
      try {
        return r.json('access_token') !== undefined;
      } catch (_) {
        return false;
      }
    },
  });

  if (!ok) {
    console.error(`Login failed: status=${res.status} body=${res.body}`);
    return '';
  }

  return res.json('access_token');
}

/**
 * Build standard Authorization + Content-Type headers from a JWT token.
 *
 * @param {string} token - JWT access token.
 * @returns {object} Headers object suitable for http.get / http.post options.
 */
export function authHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

/**
 * Perform an authenticated GET request and check for the expected status code.
 *
 * @param {string} path         - API path relative to BASE_URL (e.g., "/investigations").
 * @param {string} token        - JWT access token.
 * @param {number} expectedStatus - Expected HTTP status (default 200).
 * @param {string} [tag]        - Optional k6 tag name for grouping in results.
 * @returns {object} k6 http response.
 */
export function authGet(path, token, expectedStatus = 200, tag = undefined) {
  const url = `${BASE_URL}${path}`;
  const opts = { headers: authHeaders(token) };
  if (tag) {
    opts.tags = { name: tag };
  }
  const res = http.get(url, opts);
  check(res, { [`GET ${path} => ${expectedStatus}`]: (r) => r.status === expectedStatus });
  return res;
}

/**
 * Perform an authenticated POST request with a JSON body.
 *
 * @param {string} path           - API path relative to BASE_URL.
 * @param {object} body           - Request body (will be JSON-serialized).
 * @param {string} token          - JWT access token.
 * @param {number} expectedStatus - Expected HTTP status (default 200).
 * @param {string} [tag]          - Optional k6 tag name.
 * @returns {object} k6 http response.
 */
export function authPost(path, body, token, expectedStatus = 200, tag = undefined) {
  const url = `${BASE_URL}${path}`;
  const opts = { headers: authHeaders(token) };
  if (tag) {
    opts.tags = { name: tag };
  }
  const res = http.post(url, JSON.stringify(body), opts);
  check(res, { [`POST ${path} => ${expectedStatus}`]: (r) => r.status === expectedStatus });
  return res;
}

/**
 * Generate a random integer between min (inclusive) and max (exclusive).
 */
export function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min)) + min;
}

/**
 * Pick a random element from an array.
 */
export function randomChoice(arr) {
  return arr[randomInt(0, arr.length)];
}
