// Test the permission logic directly (no React hooks needed)
type UserRole = "admin" | "operator" | "viewer";
type Action = "view" | "create" | "edit" | "delete" | "execute" | "export";

const PERMISSION_MATRIX: Record<UserRole, Record<string, Action[]>> = {
  admin: {
    investigations: ["view", "create", "edit", "delete", "execute", "export"],
    remediations: ["view", "create", "edit", "delete", "execute", "export"],
    security: ["view", "create", "edit", "delete", "execute", "export"],
    playbooks: ["view", "create", "edit", "delete", "execute", "export"],
    billing: ["view", "create", "edit", "delete"],
    settings: ["view", "create", "edit", "delete"],
    users: ["view", "create", "edit", "delete"],
    organizations: ["view", "create", "edit", "delete"],
  },
  operator: {
    investigations: ["view", "create", "edit", "execute", "export"],
    remediations: ["view", "create", "edit", "execute", "export"],
    security: ["view", "create", "execute", "export"],
    playbooks: ["view", "create", "edit", "execute"],
    billing: ["view"],
    settings: ["view", "edit"],
    users: ["view"],
    organizations: ["view"],
  },
  viewer: {
    investigations: ["view"],
    remediations: ["view"],
    security: ["view"],
    playbooks: ["view"],
    billing: ["view"],
    settings: ["view"],
    users: [],
    organizations: [],
  },
};

function can(role: UserRole, resource: string, action: Action): boolean {
  const perms = PERMISSION_MATRIX[role]?.[resource];
  return perms ? perms.includes(action) : false;
}

describe("Role-based Permission Matrix", () => {
  describe("Admin role", () => {
    it("has full access to investigations", () => {
      expect(can("admin", "investigations", "view")).toBe(true);
      expect(can("admin", "investigations", "create")).toBe(true);
      expect(can("admin", "investigations", "delete")).toBe(true);
      expect(can("admin", "investigations", "execute")).toBe(true);
    });

    it("can manage billing", () => {
      expect(can("admin", "billing", "edit")).toBe(true);
      expect(can("admin", "billing", "delete")).toBe(true);
    });

    it("can manage users", () => {
      expect(can("admin", "users", "create")).toBe(true);
      expect(can("admin", "users", "delete")).toBe(true);
    });
  });

  describe("Operator role", () => {
    it("can view and create investigations", () => {
      expect(can("operator", "investigations", "view")).toBe(true);
      expect(can("operator", "investigations", "create")).toBe(true);
      expect(can("operator", "investigations", "execute")).toBe(true);
    });

    it("cannot delete investigations", () => {
      expect(can("operator", "investigations", "delete")).toBe(false);
    });

    it("can only view billing", () => {
      expect(can("operator", "billing", "view")).toBe(true);
      expect(can("operator", "billing", "edit")).toBe(false);
      expect(can("operator", "billing", "delete")).toBe(false);
    });

    it("can view but not manage users", () => {
      expect(can("operator", "users", "view")).toBe(true);
      expect(can("operator", "users", "create")).toBe(false);
    });

    it("can edit settings", () => {
      expect(can("operator", "settings", "edit")).toBe(true);
    });
  });

  describe("Viewer role", () => {
    it("can only view investigations", () => {
      expect(can("viewer", "investigations", "view")).toBe(true);
      expect(can("viewer", "investigations", "create")).toBe(false);
      expect(can("viewer", "investigations", "edit")).toBe(false);
      expect(can("viewer", "investigations", "delete")).toBe(false);
    });

    it("cannot access users at all", () => {
      expect(can("viewer", "users", "view")).toBe(false);
    });

    it("cannot access organizations", () => {
      expect(can("viewer", "organizations", "view")).toBe(false);
    });

    it("can view billing read-only", () => {
      expect(can("viewer", "billing", "view")).toBe(true);
      expect(can("viewer", "billing", "edit")).toBe(false);
    });

    it("no escalation — cannot create/delete/execute anything", () => {
      const resources = Object.keys(PERMISSION_MATRIX.viewer);
      for (const resource of resources) {
        expect(can("viewer", resource, "create")).toBe(false);
        expect(can("viewer", resource, "delete")).toBe(false);
        expect(can("viewer", resource, "execute")).toBe(false);
      }
    });
  });

  describe("Edge cases", () => {
    it("unknown resource returns false", () => {
      expect(can("admin", "nonexistent", "view")).toBe(false);
    });
  });
});
