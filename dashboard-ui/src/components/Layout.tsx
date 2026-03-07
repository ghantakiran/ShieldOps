import { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";
import MobileSidebar from "./MobileSidebar";
import DemoBanner from "./DemoBanner";
import ErrorBoundary from "./ErrorBoundary";
import { useRealtimeUpdates } from "../hooks/useRealtimeUpdates";
import { isDemoMode } from "../demo/config";

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useRealtimeUpdates();

  const openMobile = useCallback(() => setMobileOpen(true), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {isDemoMode() && <DemoBanner />}
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop sidebar */}
        <div className="hidden lg:flex">
          <Sidebar />
        </div>

        {/* Mobile sidebar */}
        <MobileSidebar isOpen={mobileOpen} onClose={closeMobile} />

        <div className="flex flex-1 flex-col overflow-hidden">
          <Header onMenuClick={openMobile} />
          <main className="flex-1 overflow-y-auto p-4 sm:p-6">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </div>
  );
}
