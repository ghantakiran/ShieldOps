/**
 * Timer-based mock WebSocket for demo mode.
 * Emits fake events to keep the UI feeling alive.
 */
import type { QueryClient } from "@tanstack/react-query";

let timers: ReturnType<typeof setInterval>[] = [];

export function startMockWebSocket(queryClient: QueryClient): void {
  stopMockWebSocket();

  // Periodic investigation progress update
  timers.push(
    setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
    }, 8_000),
  );

  // Agent heartbeat refresh
  timers.push(
    setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
    }, 12_000),
  );

  // Occasional alert / analytics refresh
  timers.push(
    setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    }, 20_000),
  );
}

export function stopMockWebSocket(): void {
  for (const t of timers) clearInterval(t);
  timers = [];
}
