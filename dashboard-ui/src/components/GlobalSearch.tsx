import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  FileText,
  Wrench,
  Shield,
  Bot,
  X,
  Loader2,
} from "lucide-react";
import clsx from "clsx";
import { get } from "../api/client";

// ── Types ────────────────────────────────────────────────────────

interface SearchResult {
  entity_type: "investigation" | "remediation" | "vulnerability" | "agent";
  id: string;
  title: string;
  description: string;
  status: string;
  relevance: number;
  url: string;
  created_at: string | null;
}

interface SearchResponse {
  query: string;
  total: number;
  results: SearchResult[];
}

// ── Constants ────────────────────────────────────────────────────

const ENTITY_ICONS: Record<string, typeof FileText> = {
  investigation: FileText,
  remediation: Wrench,
  vulnerability: Shield,
  agent: Bot,
};

const ENTITY_LABELS: Record<string, string> = {
  investigation: "Investigation",
  remediation: "Remediation",
  vulnerability: "Vulnerability",
  agent: "Agent",
};

const ENTITY_COLORS: Record<string, string> = {
  investigation: "text-blue-400",
  remediation: "text-amber-400",
  vulnerability: "text-red-400",
  agent: "text-green-400",
};

const RECENT_SEARCHES_KEY = "shieldops_recent_searches";
const MAX_RECENT = 5;

// ── Helpers ──────────────────────────────────────────────────────

function loadRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s): s is string => typeof s === "string").slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string): void {
  const recent = loadRecentSearches().filter((s) => s !== query);
  recent.unshift(query);
  localStorage.setItem(
    RECENT_SEARCHES_KEY,
    JSON.stringify(recent.slice(0, MAX_RECENT)),
  );
}

// ── Component ────────────────────────────────────────────────────

interface GlobalSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function GlobalSearch({ isOpen, onClose }: GlobalSearchProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recentSearches] = useState(loadRecentSearches);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setResults([]);
      setSelectedIndex(0);
      // Small delay to ensure modal is rendered
      const timer = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Debounced search
  const performSearch = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const encoded = encodeURIComponent(searchQuery);
      const data = await get<SearchResponse>(
        `/search?q=${encoded}&limit=20`,
      );
      setResults(data.results);
      setSelectedIndex(0);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.length < 2) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    debounceRef.current = setTimeout(() => {
      performSearch(query);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, performSearch]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && results.length > 0) {
        e.preventDefault();
        const selected = results[selectedIndex];
        if (selected) {
          saveRecentSearch(query);
          onClose();
          navigate(selected.url);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    },
    [results, selectedIndex, query, onClose, navigate],
  );

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const items = listRef.current.querySelectorAll("[data-search-item]");
    const item = items[selectedIndex];
    if (item) {
      item.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  const handleResultClick = (result: SearchResult) => {
    saveRecentSearch(query);
    onClose();
    navigate(result.url);
  };

  // Group results by entity type
  const grouped = results.reduce<Record<string, SearchResult[]>>(
    (acc, result) => {
      const key = result.entity_type;
      if (!acc[key]) acc[key] = [];
      acc[key].push(result);
      return acc;
    },
    {},
  );

  // Track flat index for keyboard nav
  let flatIndex = 0;

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-xl overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Search Input */}
        <div className="flex items-center gap-3 border-b border-gray-800 px-4 py-3">
          <Search className="h-5 w-5 shrink-0 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search investigations, remediations, vulnerabilities..."
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none"
            autoComplete="off"
            spellCheck={false}
          />
          {isLoading && (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-gray-400" />
          )}
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results */}
        <div
          ref={listRef}
          className="max-h-[400px] overflow-y-auto"
        >
          {/* Empty state: no query yet */}
          {query.length < 2 && results.length === 0 && (
            <div className="px-4 py-6">
              {recentSearches.length > 0 ? (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                    Recent Searches
                  </p>
                  {recentSearches.map((recent) => (
                    <button
                      key={recent}
                      onClick={() => setQuery(recent)}
                      className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                    >
                      <Search className="h-3.5 w-3.5" />
                      {recent}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-center text-sm text-gray-500">
                  Type at least 2 characters to search
                </p>
              )}
            </div>
          )}

          {/* Empty state: no results */}
          {query.length >= 2 && !isLoading && results.length === 0 && (
            <div className="px-4 py-8 text-center">
              <Search className="mx-auto mb-2 h-8 w-8 text-gray-600" />
              <p className="text-sm text-gray-400">No results found</p>
              <p className="mt-1 text-xs text-gray-600">
                Try different keywords or check for typos
              </p>
            </div>
          )}

          {/* Grouped results */}
          {Object.entries(grouped).map(([entityType, items]) => {
            const Icon = ENTITY_ICONS[entityType] ?? FileText;
            const label = ENTITY_LABELS[entityType] ?? entityType;
            const color = ENTITY_COLORS[entityType] ?? "text-gray-400";

            return (
              <div key={entityType}>
                {/* Group header */}
                <div className="sticky top-0 flex items-center gap-2 bg-gray-900/95 px-4 py-2 backdrop-blur">
                  <Icon className={clsx("h-3.5 w-3.5", color)} />
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                    {label}s
                  </span>
                  <span className="text-xs text-gray-600">
                    ({items.length})
                  </span>
                </div>

                {/* Items */}
                {items.map((result) => {
                  const currentIndex = flatIndex;
                  flatIndex += 1;
                  const isSelected = currentIndex === selectedIndex;

                  return (
                    <button
                      key={`${result.entity_type}-${result.id}`}
                      data-search-item
                      onClick={() => handleResultClick(result)}
                      onMouseEnter={() => setSelectedIndex(currentIndex)}
                      className={clsx(
                        "flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors",
                        isSelected
                          ? "bg-gray-800"
                          : "hover:bg-gray-800/50",
                      )}
                    >
                      <Icon
                        className={clsx(
                          "mt-0.5 h-4 w-4 shrink-0",
                          color,
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-gray-200">
                            {result.title}
                          </span>
                          <span className="shrink-0 rounded bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">
                            {result.status}
                          </span>
                        </div>
                        <p className="mt-0.5 truncate text-xs text-gray-500">
                          {result.description}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-800 px-4 py-2">
          <div className="flex items-center gap-3 text-xs text-gray-600">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-gray-700 bg-gray-800 px-1 py-0.5 font-mono text-[10px]">
                ↑↓
              </kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-gray-700 bg-gray-800 px-1 py-0.5 font-mono text-[10px]">
                ↵
              </kbd>
              select
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-gray-700 bg-gray-800 px-1 py-0.5 font-mono text-[10px]">
                esc
              </kbd>
              close
            </span>
          </div>
          {results.length > 0 && (
            <span className="text-xs text-gray-600">
              {results.length} result{results.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
