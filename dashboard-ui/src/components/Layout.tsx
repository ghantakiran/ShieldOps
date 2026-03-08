import { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";
import MobileSidebar from "./MobileSidebar";
import DemoBanner from "./DemoBanner";
import ErrorBoundary from "./ErrorBoundary";
import AIChatSidebar from "./AIChatSidebar";
import Breadcrumbs from "./Breadcrumbs";
import KeyboardShortcuts from "./KeyboardShortcuts";
import ProductTour from "./ProductTour";
import { useRealtimeUpdates } from "../hooks/useRealtimeUpdates";
import { isDemoMode } from "../demo/config";

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useRealtimeUpdates();

  const openMobile = useCallback(() => setMobileOpen(true), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Skip to main content link for accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-brand-500 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to main content
      </a>
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
          <main id="main-content" className="flex-1 overflow-y-auto p-4 sm:p-6">
            <Breadcrumbs />
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>

      {/* AI Chat assistant */}
      <AIChatSidebar />

      {/* Keyboard shortcuts overlay (press ?) */}
      <KeyboardShortcuts />

      {/* Interactive product tour for demo visitors */}
      <ProductTour />
    </div>
  );
}
