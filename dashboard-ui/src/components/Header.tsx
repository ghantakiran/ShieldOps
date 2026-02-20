import { useState, useEffect, useCallback } from "react";
import { Bell, LogOut, Search } from "lucide-react";
import { useAuthStore } from "../store/auth";
import ConnectionStatus from "./ConnectionStatus";
import GlobalSearch from "./GlobalSearch";

export default function Header() {
  const { user, logout } = useAuthStore();
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  const openSearch = useCallback(() => setIsSearchOpen(true), []);
  const closeSearch = useCallback(() => setIsSearchOpen(false), []);

  // Global keyboard shortcut: Cmd+K (Mac) / Ctrl+K (Windows)
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <header className="flex h-14 items-center justify-between border-b border-gray-800 bg-gray-900 px-6">
        {/* Search trigger */}
        <button
          onClick={openSearch}
          className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-1.5 text-sm text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-300"
        >
          <Search className="h-4 w-4" />
          <span>Search...</span>
          <kbd className="ml-4 hidden rounded border border-gray-700 bg-gray-800 px-1.5 py-0.5 font-mono text-[10px] text-gray-500 sm:inline">
            {navigator.platform.includes("Mac") ? "\u2318K" : "Ctrl+K"}
          </kbd>
        </button>

        <div className="flex items-center gap-4">
          {/* WebSocket connection status */}
          <ConnectionStatus />

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

      {/* Global search modal */}
      <GlobalSearch isOpen={isSearchOpen} onClose={closeSearch} />
    </>
  );
}
