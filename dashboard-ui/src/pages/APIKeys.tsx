import { useState, useCallback } from "react";
import {
  Key,
  Plus,
  Copy,
  Check,
  X,
  AlertTriangle,
  Trash2,
  Info,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";

import { DEMO_API_KEYS, type APIKey } from "../demo/apiKeyData";

const SCOPES = [
  { value: "read", label: "Read", description: "Read access to all resources" },
  { value: "write", label: "Write", description: "Create and update resources" },
  { value: "admin", label: "Admin", description: "Full administrative access" },
  {
    value: "agent_execute",
    label: "Agent Execute",
    description: "Execute agent actions",
  },
] as const;

const EXPIRY_OPTIONS = [
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "1y", label: "1 year" },
  { value: "never", label: "Never" },
] as const;

// ── Status Badge ─────────────────────────────────────────

function KeyStatusBadge({ status }: { status: APIKey["status"] }) {
  const styles: Record<APIKey["status"], string> = {
    active: "bg-green-500/20 text-green-400",
    revoked: "bg-red-500/20 text-red-400",
    expired: "bg-yellow-500/20 text-yellow-400",
  };

  return (
    <span
      className={clsx(
        "rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        styles[status],
      )}
    >
      {status}
    </span>
  );
}

// ── Revoke Confirmation Dialog ───────────────────────────

function RevokeDialog({
  keyItem,
  onConfirm,
  onCancel,
}: {
  keyItem: APIKey;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-sm rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-400" />
          <h3 className="font-semibold text-gray-100">Revoke API Key</h3>
        </div>
        <p className="mt-3 text-sm text-gray-400">
          Are you sure you want to revoke{" "}
          <span className="font-medium text-gray-200">{keyItem.name}</span>?
          This action cannot be undone. Any integrations using this key will
          stop working immediately.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className={clsx(
              "rounded-lg border border-gray-700 px-4 py-2",
              "text-sm text-gray-300",
              "transition-colors hover:bg-gray-800",
            )}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
          >
            Revoke Key
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Create Key Modal ─────────────────────────────────────

function CreateKeyModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (key: APIKey, rawKey: string) => void;
}) {
  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["read"]);
  const [expiry, setExpiry] = useState("90d");
  const [error, setError] = useState<string | null>(null);

  const toggleScope = useCallback((scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope)
        ? prev.filter((s) => s !== scope)
        : [...prev, scope],
    );
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (selectedScopes.length === 0) {
      setError("Select at least one scope");
      return;
    }

    // Simulate key creation
    const prefix = `sk_${name.slice(0, 4).toLowerCase().replace(/[^a-z]/g, "x")}_${Math.random().toString(36).slice(2, 4)}`;
    const rawKey = `${prefix}_${crypto.randomUUID().replace(/-/g, "")}`;

    let expiresAt: string | null = null;
    if (expiry !== "never") {
      const days = expiry === "30d" ? 30 : expiry === "90d" ? 90 : 365;
      const d = new Date();
      d.setDate(d.getDate() + days);
      expiresAt = d.toISOString();
    }

    const newKey: APIKey = {
      key_id: `key_${Date.now()}`,
      name: name.trim(),
      prefix: rawKey.slice(0, 8),
      scopes: selectedScopes,
      status: "active",
      rate_limit_per_minute: 1000,
      created_at: new Date().toISOString(),
      expires_at: expiresAt,
      last_used_at: null,
    };

    onCreated(newKey, rawKey);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-md rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">
            Create New API Key
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          {/* Name */}
          <div>
            <label className="mb-1 block text-sm text-gray-400">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={clsx(
                "w-full rounded-lg border border-gray-700",
                "bg-gray-800 px-3 py-2 text-sm",
                "text-gray-200 placeholder-gray-500",
                "focus:border-brand-500 focus:outline-none",
              )}
              placeholder="e.g. Production CI/CD"
            />
          </div>

          {/* Scopes */}
          <div>
            <label className="mb-2 block text-sm text-gray-400">Scopes</label>
            <div className="space-y-2">
              {SCOPES.map((scope) => (
                <label
                  key={scope.value}
                  className="flex items-start gap-3 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedScopes.includes(scope.value)}
                    onChange={() => toggleScope(scope.value)}
                    className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-700 text-brand-500 focus:ring-brand-500"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-200">
                      {scope.label}
                    </span>
                    <p className="text-xs text-gray-500">
                      {scope.description}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Expiry */}
          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Expiration
            </label>
            <select
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className={clsx(
                "w-full rounded-lg border border-gray-700",
                "bg-gray-800 px-3 py-2 text-sm text-gray-200",
              )}
            >
              {EXPIRY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
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
                "transition-colors hover:bg-gray-800",
              )}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={clsx(
                "rounded-lg bg-brand-600 px-4 py-2",
                "text-sm font-medium text-white",
                "transition-colors hover:bg-brand-500",
              )}
            >
              Create Key
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Key Created Modal (shows raw key once) ───────────────

function KeyCreatedModal({
  rawKey,
  onClose,
}: {
  rawKey: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copyKey() {
    try {
      await navigator.clipboard.writeText(rawKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may fail in non-secure contexts
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-lg rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center gap-3">
          <Check className="h-5 w-5 text-green-400" />
          <h3 className="font-semibold text-gray-100">API Key Created</h3>
        </div>

        <div className="mt-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2">
          <p className="text-sm text-yellow-300">
            This key will not be shown again. Copy it now and store it securely.
          </p>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <div className="flex-1 overflow-x-auto rounded-lg border border-gray-700 bg-gray-800 px-3 py-2">
            <code className="whitespace-nowrap text-sm text-gray-200">
              {rawKey}
            </code>
          </div>
          <button
            onClick={copyKey}
            className="flex items-center gap-1.5 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-green-400" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy
              </>
            )}
          </button>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────

export default function APIKeys() {
  const [keys, setKeys] = useState<APIKey[]>(DEMO_API_KEYS);
  const [showCreate, setShowCreate] = useState(false);
  const [createdRawKey, setCreatedRawKey] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<APIKey | null>(null);

  const handleCreated = (newKey: APIKey, rawKey: string) => {
    setKeys((prev) => [newKey, ...prev]);
    setShowCreate(false);
    setCreatedRawKey(rawKey);
  };

  const handleRevoke = (keyItem: APIKey) => {
    setKeys((prev) =>
      prev.map((k) =>
        k.key_id === keyItem.key_id ? { ...k, status: "revoked" as const } : k,
      ),
    );
    setRevokeTarget(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">API Keys</h1>
          <p className="mt-1 text-sm text-gray-400">
            Manage authentication keys for the ShieldOps API
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className={clsx(
            "flex items-center gap-2 rounded-lg",
            "bg-brand-600 px-4 py-2 text-sm font-medium",
            "text-white transition-colors hover:bg-brand-500",
          )}
        >
          <Plus className="h-4 w-4" />
          Create New Key
        </button>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-500" />
        <p className="text-sm text-gray-400">
          Use API keys to authenticate requests to the ShieldOps API. Keys are
          shown only once at creation. Store them securely and rotate them
          regularly.
        </p>
      </div>

      {/* Keys Table */}
      <div className="overflow-hidden rounded-xl border border-gray-800 bg-gray-900">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs uppercase tracking-wider text-gray-500">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Key Prefix</th>
                <th className="px-4 py-3">Scopes</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Rate Limit</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Last Used</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {keys.map((k) => (
                <tr
                  key={k.key_id}
                  className="transition-colors hover:bg-gray-800/50"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-100">{k.name}</span>
                  </td>
                  <td className="px-4 py-3">
                    <code className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-300">
                      {k.prefix}...
                    </code>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {k.scopes.map((scope) => (
                        <span
                          key={scope}
                          className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400"
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <KeyStatusBadge status={k.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {k.rate_limit_per_minute.toLocaleString()}/min
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {formatDistanceToNow(new Date(k.created_at), {
                      addSuffix: true,
                    })}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {k.last_used_at
                      ? formatDistanceToNow(new Date(k.last_used_at), {
                          addSuffix: true,
                        })
                      : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    {k.status === "active" && (
                      <button
                        onClick={() => setRevokeTarget(k)}
                        className={clsx(
                          "flex items-center gap-1.5 rounded-lg border px-3 py-1",
                          "border-red-700 text-xs font-medium text-red-400",
                          "transition-colors hover:bg-red-500/10",
                        )}
                      >
                        <Trash2 className="h-3 w-3" />
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {keys.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-4 py-12 text-center text-gray-500"
                  >
                    <Key className="mx-auto h-8 w-8 text-gray-600" />
                    <p className="mt-2">No API keys yet.</p>
                    <button
                      onClick={() => setShowCreate(true)}
                      className="mt-3 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
                    >
                      <Plus className="h-4 w-4" />
                      Create Your First Key
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modals */}
      {showCreate && (
        <CreateKeyModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}

      {createdRawKey && (
        <KeyCreatedModal
          rawKey={createdRawKey}
          onClose={() => setCreatedRawKey(null)}
        />
      )}

      {revokeTarget && (
        <RevokeDialog
          keyItem={revokeTarget}
          onConfirm={() => handleRevoke(revokeTarget)}
          onCancel={() => setRevokeTarget(null)}
        />
      )}
    </div>
  );
}
