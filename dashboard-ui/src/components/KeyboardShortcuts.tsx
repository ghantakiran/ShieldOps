import { useState, useEffect } from "react";
import { X } from "lucide-react";

const isMac = typeof navigator !== "undefined" && navigator.platform.includes("Mac");
const mod = isMac ? "\u2318" : "Ctrl";

const SHORTCUT_GROUPS = [
  {
    title: "Navigation",
    shortcuts: [
      { keys: [`${mod}+K`], description: "Open search" },
      { keys: ["?"], description: "Show keyboard shortcuts" },
      { keys: ["Esc"], description: "Close dialogs / panels" },
    ],
  },
  {
    title: "Search",
    shortcuts: [
      { keys: ["\u2191 \u2193"], description: "Navigate results" },
      { keys: ["Enter"], description: "Open selected result" },
      { keys: ["Esc"], description: "Close search" },
    ],
  },
  {
    title: "Agent Factory",
    shortcuts: [
      { keys: [`${mod}+Enter`], description: "Submit prompt" },
    ],
  },
];

export default function KeyboardShortcuts() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Only trigger on "?" when no input/textarea is focused
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "?" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) setIsOpen(false);
      }}
    >
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative z-10 w-full max-w-md overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-100">
            Keyboard Shortcuts
          </h2>
          <button
            onClick={() => setIsOpen(false)}
            className="rounded p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-5">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title} className="mb-5 last:mb-0">
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.shortcuts.map((shortcut) => (
                  <div
                    key={shortcut.description}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-gray-300">
                      {shortcut.description}
                    </span>
                    <div className="flex items-center gap-1">
                      {shortcut.keys.map((key) => (
                        <kbd
                          key={key}
                          className="rounded border border-gray-700 bg-gray-800 px-2 py-0.5 font-mono text-xs text-gray-400"
                        >
                          {key}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-gray-800 px-5 py-2.5">
          <p className="text-center text-xs text-gray-600">
            Press <kbd className="rounded border border-gray-700 bg-gray-800 px-1 py-0.5 font-mono text-[10px]">?</kbd> to toggle
          </p>
        </div>
      </div>
    </div>
  );
}
