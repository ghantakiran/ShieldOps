import { useState } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import {
  Users,
  UserPlus,
  X,
  AlertTriangle,
} from "lucide-react";
import clsx from "clsx";
import { get, post, put } from "../api/client";
import { useAuthStore } from "../store/auth";
import LoadingSpinner from "../components/LoadingSpinner";

interface UserItem {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

interface UsersResponse {
  items: UserItem[];
  total: number;
  limit: number;
  offset: number;
}

const ROLES = ["admin", "operator", "viewer"] as const;

// ── Invite User Modal ───────────────────────────────────
function InviteModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<string>("viewer");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      post("/auth/register", {
        email,
        name,
        password,
        role,
      }),
    onSuccess: () => {
      onSuccess();
      onClose();
    },
    onError: (err: Error) => {
      setError(err.message || "Failed to create user");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !name || !password) {
      setError("All fields are required");
      return;
    }
    mutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-md rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">
            Invite User
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={clsx(
                "w-full rounded-lg border border-gray-700",
                "bg-gray-800 px-3 py-2 text-sm",
                "text-gray-200 placeholder-gray-500",
                "focus:border-brand-500 focus:outline-none"
              )}
              placeholder="Jane Doe"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={clsx(
                "w-full rounded-lg border border-gray-700",
                "bg-gray-800 px-3 py-2 text-sm",
                "text-gray-200 placeholder-gray-500",
                "focus:border-brand-500 focus:outline-none"
              )}
              placeholder="jane@company.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={clsx(
                "w-full rounded-lg border border-gray-700",
                "bg-gray-800 px-3 py-2 text-sm",
                "text-gray-200 placeholder-gray-500",
                "focus:border-brand-500 focus:outline-none"
              )}
              placeholder="Minimum 8 characters"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Role
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className={clsx(
                "w-full rounded-lg border border-gray-700",
                "bg-gray-800 px-3 py-2 text-sm text-gray-200"
              )}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className={clsx(
                "rounded-lg border border-gray-700 px-4 py-2",
                "text-sm text-gray-300",
                "transition-colors hover:bg-gray-800"
              )}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className={clsx(
                "rounded-lg bg-brand-600 px-4 py-2",
                "text-sm font-medium text-white",
                "transition-colors hover:bg-brand-500",
                "disabled:opacity-50"
              )}
            >
              {mutation.isPending
                ? "Creating..."
                : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Deactivation Confirmation Dialog ────────────────────
function ConfirmDialog({
  user,
  action,
  onConfirm,
  onCancel,
}: {
  user: UserItem;
  action: "activate" | "deactivate";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-sm rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-400" />
          <h3 className="font-semibold text-gray-100">
            Confirm {action === "deactivate"
              ? "Deactivation"
              : "Activation"}
          </h3>
        </div>
        <p className="mt-3 text-sm text-gray-400">
          Are you sure you want to {action}{" "}
          <span className="font-medium text-gray-200">
            {user.name}
          </span>{" "}
          ({user.email})?
          {action === "deactivate" &&
            " They will no longer be able to log in."}
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className={clsx(
              "rounded-lg border border-gray-700 px-4 py-2",
              "text-sm text-gray-300",
              "transition-colors hover:bg-gray-800"
            )}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={clsx(
              "rounded-lg px-4 py-2 text-sm font-medium text-white",
              action === "deactivate"
                ? "bg-red-600 hover:bg-red-500"
                : "bg-green-600 hover:bg-green-500"
            )}
          >
            {action === "deactivate"
              ? "Deactivate"
              : "Activate"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────
export default function UserManagement() {
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [showInvite, setShowInvite] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<{
    user: UserItem;
    action: "activate" | "deactivate";
  } | null>(null);

  const isAdmin = currentUser?.role === "admin";

  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => get<UsersResponse>("/users"),
    enabled: isAdmin,
  });

  const roleMutation = useMutation({
    mutationFn: ({
      userId,
      role,
    }: {
      userId: string;
      role: string;
    }) => put(`/users/${userId}/role`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const activeMutation = useMutation({
    mutationFn: ({
      userId,
      isActive,
    }: {
      userId: string;
      isActive: boolean;
    }) =>
      put(`/users/${userId}/active`, {
        is_active: isActive,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setConfirmTarget(null);
    },
  });

  // Redirect non-admins (after all hooks)
  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  const handleToggleActive = (user: UserItem) => {
    const action = user.is_active ? "deactivate" : "activate";
    if (action === "deactivate") {
      setConfirmTarget({ user, action });
    } else {
      activeMutation.mutate({
        userId: user.id,
        isActive: true,
      });
    }
  };

  const users = data?.items ?? [];

  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            User Management
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            Manage users, roles, and access
          </p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className={clsx(
            "flex items-center gap-2 rounded-lg",
            "bg-brand-600 px-4 py-2 text-sm font-medium",
            "text-white transition-colors hover:bg-brand-500"
          )}
        >
          <UserPlus className="h-4 w-4" />
          Invite User
        </button>
      </div>

      {/* Users Table */}
      <div className="overflow-hidden rounded-xl border border-gray-800 bg-gray-900">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-xs uppercase tracking-wider text-gray-500">
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {users.map((u) => (
              <tr
                key={u.id}
                className="transition-colors hover:bg-gray-800/50"
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-100">
                    {u.name}
                  </div>
                  <div className="text-xs text-gray-500">
                    {u.email}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    onChange={(e) =>
                      roleMutation.mutate({
                        userId: u.id,
                        role: e.target.value,
                      })
                    }
                    disabled={u.id === currentUser?.id}
                    className={clsx(
                      "rounded-lg border border-gray-700",
                      "bg-gray-800 px-2 py-1 text-xs",
                      "text-gray-200",
                      "disabled:opacity-50"
                    )}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r.charAt(0).toUpperCase() +
                          r.slice(1)}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={clsx(
                      "rounded-full px-2.5 py-0.5",
                      "text-xs font-medium",
                      u.is_active
                        ? "bg-green-500/20 text-green-400"
                        : "bg-red-500/20 text-red-400"
                    )}
                  >
                    {u.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {u.created_at
                    ? new Date(
                        u.created_at
                      ).toLocaleDateString()
                    : "--"}
                </td>
                <td className="px-4 py-3">
                  {u.id !== currentUser?.id && (
                    <button
                      onClick={() => handleToggleActive(u)}
                      className={clsx(
                        "rounded-lg border px-3 py-1",
                        "text-xs font-medium transition-colors",
                        u.is_active
                          ? "border-red-700 text-red-400 hover:bg-red-500/10"
                          : "border-green-700 text-green-400 hover:bg-green-500/10"
                      )}
                    >
                      {u.is_active
                        ? "Deactivate"
                        : "Activate"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-12 text-center text-gray-500"
                >
                  <Users className="mx-auto h-8 w-8 text-gray-600" />
                  <p className="mt-2">
                    No users found.
                  </p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Invite Modal */}
      {showInvite && (
        <InviteModal
          onClose={() => setShowInvite(false)}
          onSuccess={() =>
            queryClient.invalidateQueries({
              queryKey: ["users"],
            })
          }
        />
      )}

      {/* Deactivation Confirm Dialog */}
      {confirmTarget && (
        <ConfirmDialog
          user={confirmTarget.user}
          action={confirmTarget.action}
          onConfirm={() =>
            activeMutation.mutate({
              userId: confirmTarget.user.id,
              isActive:
                confirmTarget.action === "activate",
            })
          }
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  );
}
