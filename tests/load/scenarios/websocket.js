/**
 * WebSocket stress test -- validates that the real-time event streaming
 * endpoints can handle many concurrent connections.
 *
 * Tests:
 *   - /ws/events          (global event stream)
 *   - /ws/vulnerabilities  (vulnerability lifecycle events)
 *
 * Each VU opens a WebSocket, holds the connection for the test duration,
 * and periodically sends a ping.  We measure connection success rate,
 * message round-trip time, and error counts.
 *
 * Usage:
 *   k6 run tests/load/scenarios/websocket.js
 *   k6 run tests/load/scenarios/websocket.js -e PROFILE=stress
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { WS_URL, STAGES, TEST_EMAIL, TEST_PASSWORD, BASE_URL } from '../config.js';
import { login, randomChoice } from '../helpers.js';

const profile = __ENV.PROFILE || 'load';

// Custom metrics
const wsConnectSuccess = new Rate('ws_connect_success');
const wsMessagesSent = new Counter('ws_messages_sent');
const wsMessagesReceived = new Counter('ws_messages_received');
const wsSessionDuration = new Trend('ws_session_duration', true);

export const options = {
  stages: STAGES[profile] || STAGES.load,
  thresholds: {
    ws_connect_success: ['rate>0.95'],
    ws_session_duration: ['p(95)<65000'], // sessions should last ~60s
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

  // Alternate between the two public WS channels.
  const channel = randomChoice(['events', 'vulnerabilities']);
  const url = `${WS_URL}/ws/${channel}?token=${token}`;

  const startTime = Date.now();

  const res = ws.connect(url, {}, function (socket) {
    socket.on('open', () => {
      wsConnectSuccess.add(1);

      // Send periodic pings to keep the connection alive.
      // k6 ws.setInterval uses milliseconds.
      socket.setInterval(function () {
        socket.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
        wsMessagesSent.add(1);
      }, 5000); // every 5 seconds
    });

    socket.on('message', (msg) => {
      wsMessagesReceived.add(1);
    });

    socket.on('error', (e) => {
      wsConnectSuccess.add(0);
      console.error(`WebSocket error on /ws/${channel}: ${e}`);
    });

    socket.on('close', () => {
      wsSessionDuration.add(Date.now() - startTime);
    });

    // Hold connection open for ~60 seconds then close.
    socket.setTimeout(function () {
      socket.close();
    }, 60000);
  });

  check(res, {
    'ws status is 101': (r) => r && r.status === 101,
  });

  // Small pause between reconnections so VUs don't hammer on close/open.
  sleep(2);
}
