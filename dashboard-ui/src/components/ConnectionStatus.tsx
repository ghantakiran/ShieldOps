/**
 * Small status indicator showing the WebSocket connection state.
 * Designed to sit in the header bar.
 *
 * - Green dot + "Live"          when connected
 * - Yellow dot + "Connecting..."  when reconnecting
 * - Red dot + "Offline"         when disconnected
 */
import { Wifi, WifiOff, Loader2 } from "lucide-react";
import { useConnectionStatus } from "../hooks/useRealtimeUpdates";

const STATUS_CONFIG = {
  connected: {
    icon: Wifi,
    label: "Live",
    dotColor: "bg-green-400",
    textColor: "text-green-400",
    iconColor: "text-green-400",
  },
  connecting: {
    icon: Loader2,
    label: "Connecting...",
    dotColor: "bg-yellow-400",
    textColor: "text-yellow-400",
    iconColor: "text-yellow-400",
  },
  disconnected: {
    icon: WifiOff,
    label: "Offline",
    dotColor: "bg-red-400",
    textColor: "text-gray-500",
    iconColor: "text-gray-500",
  },
} as const;

export default function ConnectionStatus() {
  const status = useConnectionStatus();
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="relative flex h-2 w-2">
        {status === "connected" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
        )}
        <span
          className={`relative inline-flex h-2 w-2 rounded-full ${config.dotColor}`}
        />
      </span>
      <Icon
        className={`h-3.5 w-3.5 ${config.iconColor} ${
          status === "connecting" ? "animate-spin" : ""
        }`}
      />
      <span className={config.textColor}>{config.label}</span>
    </div>
  );
}
