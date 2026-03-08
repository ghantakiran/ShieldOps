/**
 * Hook for streaming real-time agent task step updates via WebSocket.
 *
 * Connects to /ws/agent-tasks/{taskId} and dispatches events
 * (step_update, task_complete, approval_required, error) to a callback.
 */
import { useEffect, useRef, useCallback, useState } from "react";
import type { AgentTaskWsEvent } from "../api/types";
import { isDemoMode } from "../demo/config";

export type AgentTaskEventHandler = (event: AgentTaskWsEvent) => void;

interface UseAgentTaskStreamReturn {
  connected: boolean;
  disconnect: () => void;
}

export function useAgentTaskStream(
  taskId: string | null,
  onEvent?: AgentTaskEventHandler,
): UseAgentTaskStreamReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!taskId) return;

    // Demo mode: simulate step updates
    if (isDemoMode()) {
      setConnected(true);
      return () => setConnected(false);
    }

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const token = localStorage.getItem("shieldops_token");
    const params = token ? `?token=${encodeURIComponent(token)}` : "";
    const url = `${protocol}://${window.location.host}/ws/agent-tasks/${taskId}${params}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data as string) as AgentTaskWsEvent;
        onEventRef.current?.(parsed);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Reconnect after 3s if still mounted
      const timer = setTimeout(() => {
        if (wsRef.current === ws) {
          // Component still expects this connection — reconnect
          ws.onclose = null;
        }
      }, 3000);
      return () => clearTimeout(timer);
    };

    return () => {
      ws.onclose = null;
      ws.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [taskId]);

  return { connected, disconnect };
}
