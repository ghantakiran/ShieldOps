import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";
import { useRealtimeUpdates } from "../hooks/useRealtimeUpdates";

export default function Layout() {
  // Establishes the WebSocket connection and auto-invalidates React Query
  // caches when server-side events arrive. Connection status is exposed
  // via the useConnectionStatus() hook (used by <ConnectionStatus />).
  useRealtimeUpdates();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
