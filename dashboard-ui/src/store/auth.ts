import { create } from "zustand";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isDemoMode: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isDemoMode: false,

  setAuth: (token, user) => {
    localStorage.setItem("shieldops_token", token);
    localStorage.setItem("shieldops_user", JSON.stringify(user));
    const isDemo = localStorage.getItem("shieldops_demo") === "true";
    set({ token, user, isAuthenticated: true, isDemoMode: isDemo });
  },

  logout: () => {
    localStorage.removeItem("shieldops_token");
    localStorage.removeItem("shieldops_user");
    localStorage.removeItem("shieldops_demo");
    set({ token: null, user: null, isAuthenticated: false, isDemoMode: false });
  },

  hydrate: () => {
    const token = localStorage.getItem("shieldops_token");
    const raw = localStorage.getItem("shieldops_user");
    const isDemo = localStorage.getItem("shieldops_demo") === "true";
    if (token && raw) {
      try {
        const user = JSON.parse(raw) as User;
        set({ token, user, isAuthenticated: true, isDemoMode: isDemo });
      } catch {
        localStorage.removeItem("shieldops_token");
        localStorage.removeItem("shieldops_user");
      }
    }
  },
}));
