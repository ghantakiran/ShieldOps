import { useMemo } from "react";
import { useAuthStore } from "../store/auth";

export type UserRole = "admin" | "operator" | "viewer";
export type Resource =
  | "investigations"
  | "remediations"
  | "security"
  | "playbooks"
  | "agents"
  | "billing"
  | "settings"
  | "users"
  | "organizations"
  | "api_keys"
  | "webhooks"
  | "marketplace";

export type Action = "view" | "create" | "edit" | "delete" | "execute" | "export";

// Permission matrix: role -> resource -> allowed actions
const PERMISSION_MATRIX: Record<UserRole, Record<Resource, Action[]>> = {
  admin: {
    investigations: ["view", "create", "edit", "delete", "execute", "export"],
    remediations: ["view", "create", "edit", "delete", "execute", "export"],
    security: ["view", "create", "edit", "delete", "execute", "export"],
    playbooks: ["view", "create", "edit", "delete", "execute", "export"],
    agents: ["view", "create", "edit", "delete", "execute"],
    billing: ["view", "create", "edit", "delete"],
    settings: ["view", "create", "edit", "delete"],
    users: ["view", "create", "edit", "delete"],
    organizations: ["view", "create", "edit", "delete"],
    api_keys: ["view", "create", "delete"],
    webhooks: ["view", "create", "edit", "delete"],
    marketplace: ["view", "create", "execute"],
  },
  operator: {
    investigations: ["view", "create", "edit", "execute", "export"],
    remediations: ["view", "create", "edit", "execute", "export"],
    security: ["view", "create", "execute", "export"],
    playbooks: ["view", "create", "edit", "execute"],
    agents: ["view", "create", "edit", "execute"],
    billing: ["view"],
    settings: ["view", "edit"],
    users: ["view"],
    organizations: ["view"],
    api_keys: ["view", "create", "delete"],
    webhooks: ["view", "create", "edit"],
    marketplace: ["view", "execute"],
  },
  viewer: {
    investigations: ["view"],
    remediations: ["view"],
    security: ["view"],
    playbooks: ["view"],
    agents: ["view"],
    billing: ["view"],
    settings: ["view"],
    users: [],
    organizations: [],
    api_keys: ["view"],
    webhooks: ["view"],
    marketplace: ["view"],
  },
};

export interface PermissionsHook {
  role: UserRole;
  can: (resource: Resource, action: Action) => boolean;
  canAny: (resource: Resource, actions: Action[]) => boolean;
  canAll: (resource: Resource, actions: Action[]) => boolean;
  isAdmin: boolean;
  isOperator: boolean;
  isViewer: boolean;
}

export function usePermissions(): PermissionsHook {
  const user = useAuthStore((s) => s.user);
  const role = (user?.role as UserRole) || "viewer";

  return useMemo(() => {
    const rolePerms = PERMISSION_MATRIX[role] || PERMISSION_MATRIX.viewer;

    const can = (resource: Resource, action: Action): boolean => {
      const allowed = rolePerms[resource];
      return allowed ? allowed.includes(action) : false;
    };

    const canAny = (resource: Resource, actions: Action[]): boolean =>
      actions.some((a) => can(resource, a));

    const canAll = (resource: Resource, actions: Action[]): boolean =>
      actions.every((a) => can(resource, a));

    return {
      role,
      can,
      canAny,
      canAll,
      isAdmin: role === "admin",
      isOperator: role === "operator",
      isViewer: role === "viewer",
    };
  }, [role]);
}
