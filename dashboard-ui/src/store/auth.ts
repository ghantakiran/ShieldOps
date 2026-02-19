import { create } from "zustand";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,

  setAuth: (token, user) => {
    localStorage.setItem("shieldops_token", token);
    localStorage.setItem("shieldops_user", JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("shieldops_token");
    localStorage.removeItem("shieldops_user");
    set({ token: null, user: null, isAuthenticated: false });
  },

  hydrate: () => {
    const token = localStorage.getItem("shieldops_token");
    const raw = localStorage.getItem("shieldops_user");
    if (token && raw) {
      try {
        const user = JSON.parse(raw) as User;
        set({ token, user, isAuthenticated: true });
      } catch {
        localStorage.removeItem("shieldops_token");
        localStorage.removeItem("shieldops_user");
      }
    }
  },
}));
