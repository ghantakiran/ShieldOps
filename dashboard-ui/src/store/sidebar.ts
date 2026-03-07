import { create } from "zustand";

interface SidebarStore {
  collapsed: boolean;
  expandedGroups: Set<string>;
  toggleCollapsed: () => void;
  toggleGroup: (groupId: string) => void;
  expandGroup: (groupId: string) => void;
}

function loadExpandedGroups(): Set<string> {
  try {
    const stored = localStorage.getItem("shieldops_sidebar_groups");
    if (stored) return new Set(JSON.parse(stored) as string[]);
  } catch {
    // ignore
  }
  return new Set(["sre", "security", "finops", "compliance", "platform"]);
}

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem("shieldops_sidebar_collapsed") === "true";
  } catch {
    return false;
  }
}

function persistGroups(groups: Set<string>) {
  localStorage.setItem("shieldops_sidebar_groups", JSON.stringify([...groups]));
}

export const useSidebarStore = create<SidebarStore>((set) => ({
  collapsed: loadCollapsed(),
  expandedGroups: loadExpandedGroups(),

  toggleCollapsed: () =>
    set((state) => {
      const next = !state.collapsed;
      localStorage.setItem("shieldops_sidebar_collapsed", String(next));
      return { collapsed: next };
    }),

  toggleGroup: (groupId: string) =>
    set((state) => {
      const next = new Set(state.expandedGroups);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      persistGroups(next);
      return { expandedGroups: next };
    }),

  expandGroup: (groupId: string) =>
    set((state) => {
      if (state.expandedGroups.has(groupId)) return state;
      const next = new Set(state.expandedGroups);
      next.add(groupId);
      persistGroups(next);
      return { expandedGroups: next };
    }),
}));
