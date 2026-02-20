/**
 * Hook that subscribes to WebSocket events and invalidates
 * relevant React Query caches when data changes.
 *
 * Features:
 * - Automatic reconnection with exponential backoff (1s -> 2s -> 4s -> ... -> 30s)
 * - JWT authentication via query parameter
 * - Connection status tracking (connected / connecting / disconnected)
 * - Event-driven React Query cache invalidation
 */
import { useEffect, useRef } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { create } from "zustand";

// ── Types ────────────────────────────────────────────────────────────

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

interface WSEvent {
  type: string;
  entity_type?: string;
  entity_id?: string;
  action?: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

interface ConnectionState {
  status: ConnectionStatus;
  setStatus: (status: ConnectionStatus) => void;
}

// ── Connection status store ──────────────────────────────────────────

const useConnectionStore = create<ConnectionState>((set) => ({
  status: "disconnected",
  setStatus: (status) => set({ status }),
}));

export function useConnectionStatus(): ConnectionStatus {
  return useConnectionStore((s) => s.status);
}

// ── Invalidation map ─────────────────────────────────────────────────
// Maps event entity types to the React Query cache keys that should be
// invalidated when an event of that type arrives.

const INVALIDATION_MAP: Record<string, string[]> = {
  investigation: ["investigations", "analytics"],
  remediation: ["remediations", "analytics"],
  agent: ["agents"],
  security_scan: ["security-scans", "security-posture"],
  vulnerability: ["vulnerabilities", "vulnerability-stats"],
  alert: ["investigations"],
};

// ── Constants ────────────────────────────────────────────────────────

const INITIAL_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 30_000;
const BACKOFF_MULTIPLIER = 2;

// ── Pure helpers (no hooks, no closures over React state) ────────────

function invalidateForEvent(queryClient: QueryClient, event: WSEvent): void {
  const entityType = event.entity_type ?? event.type;
  const keys = INVALIDATION_MAP[entityType];
  if (!keys) return;

  for (const key of keys) {
    queryClient.invalidateQueries({ queryKey: [key] });
  }
}

function buildWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const token = localStorage.getItem("shieldops_token");
  const params = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${protocol}://${window.location.host}/ws/events${params}`;
}

// ── Hook ─────────────────────────────────────────────────────────────

export function useRealtimeUpdates(): void {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // Store queryClient in a ref so the connect/reconnect cycle always has
  // the latest reference without needing useCallback dependency chains.
  const queryClientRef = useRef(queryClient);
  queryClientRef.current = queryClient;

  useEffect(() => {
    mountedRef.current = true;
    const { setStatus } = useConnectionStore.getState();

    function scheduleReconnect(): void {
      if (!mountedRef.current) return;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }

      const delay = reconnectDelayRef.current;
      reconnectTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        connect();
      }, delay);

      // Exponential backoff with ceiling
      reconnectDelayRef.current = Math.min(
        delay * BACKOFF_MULTIPLIER,
        MAX_RECONNECT_DELAY_MS,
      );
    }

    function connect(): void {
      if (!mountedRef.current) return;

      // Close any existing connection before opening a new one
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }

      setStatus("connecting");

      const ws = new WebSocket(buildWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setStatus("connected");
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS;
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!mountedRef.current) return;
        try {
          const parsed = JSON.parse(event.data as string) as WSEvent;
          invalidateForEvent(queryClientRef.current, parsed);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        // onerror is always followed by onclose; reconnect is handled there
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setStatus("disconnected");
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      mountedRef.current = false;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }

      setStatus("disconnected");
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
