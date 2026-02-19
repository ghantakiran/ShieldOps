import { Bell, Wifi, WifiOff, LogOut } from "lucide-react";
import { useAuthStore } from "../store/auth";

interface HeaderProps {
  wsConnected: boolean;
}

export default function Header({ wsConnected }: HeaderProps) {
  const { user, logout } = useAuthStore();

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-800 bg-gray-900 px-6">
      <div />

      <div className="flex items-center gap-4">
        {/* WebSocket status */}
        <div className="flex items-center gap-1.5 text-xs">
          {wsConnected ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-green-400" />
              <span className="text-green-400">Live</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-gray-500" />
              <span className="text-gray-500">Offline</span>
            </>
          )}
        </div>

        {/* Notifications */}
        <button className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-gray-200">
          <Bell className="h-4 w-4" />
        </button>

        {/* User */}
        {user && (
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium">{user.name}</p>
              <p className="text-xs text-gray-500">{user.role}</p>
            </div>
            <button
              onClick={logout}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-red-400"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
