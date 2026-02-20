import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Save,
  CheckCircle,
  XCircle,
  Trash2,
  Play,
  Plus,
  ArrowLeft,
  FileText,
  Tag,
  AlertTriangle,
} from "lucide-react";
import clsx from "clsx";
import { get, post, put, del } from "../api/client";

// ── Types ──────────────────────────────────────────────────

interface PlaybookData {
  id: string;
  name: string;
  description: string;
  content: string;
  tags: string[];
  source: "builtin" | "custom";
  is_valid: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface PlaybookListResponse {
  playbooks: PlaybookData[];
  total: number;
  custom_count: number;
  builtin_count: number;
}

interface ValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

interface DryRunStep {
  action: string;
  target: string;
  params: Record<string, unknown>;
}

interface DryRunResult {
  playbook_name: string;
  total_steps: number;
  steps: DryRunStep[];
  warnings: string[];
}

// ── Playbook File List (Left Pane) ─────────────────────────

function PlaybookFileList({
  playbooks,
  selectedId,
  onSelect,
  onNew,
}: {
  playbooks: PlaybookData[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const custom = playbooks.filter(
    (p) => p.source === "custom"
  );
  const builtin = playbooks.filter(
    (p) => p.source === "builtin"
  );

  return (
    <div className="flex h-full flex-col border-r border-gray-800 bg-gray-900">
      {/* New Playbook Button */}
      <div className="border-b border-gray-800 p-3">
        <button
          onClick={onNew}
          className={clsx(
            "flex w-full items-center justify-center gap-2",
            "rounded-lg border border-dashed border-gray-600",
            "px-3 py-2 text-sm text-gray-400",
            "transition-colors hover:border-brand-500",
            "hover:text-brand-400"
          )}
        >
          <Plus className="h-4 w-4" />
          New Playbook
        </button>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto">
        {custom.length > 0 && (
          <div className="px-3 pt-3">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Custom ({custom.length})
            </p>
            {custom.map((pb) => (
              <button
                key={pb.id}
                onClick={() => onSelect(pb.id)}
                className={clsx(
                  "flex w-full items-center gap-2 rounded-lg",
                  "px-3 py-2 text-left text-sm",
                  "transition-colors",
                  selectedId === pb.id
                    ? "bg-brand-600/20 text-brand-400"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                )}
              >
                <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="truncate">
                  {pb.name}
                </span>
                {pb.is_valid ? (
                  <CheckCircle className="ml-auto h-3 w-3 flex-shrink-0 text-green-500" />
                ) : (
                  <XCircle className="ml-auto h-3 w-3 flex-shrink-0 text-red-500" />
                )}
              </button>
            ))}
          </div>
        )}

        {builtin.length > 0 && (
          <div className="px-3 pt-3">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Built-in ({builtin.length})
            </p>
            {builtin.map((pb) => (
              <button
                key={pb.id}
                onClick={() => onSelect(pb.id)}
                className={clsx(
                  "flex w-full items-center gap-2 rounded-lg",
                  "px-3 py-2 text-left text-sm",
                  "transition-colors",
                  selectedId === pb.id
                    ? "bg-brand-600/20 text-brand-400"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                )}
              >
                <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="truncate">
                  {pb.name}
                </span>
                <span className="ml-auto text-[10px] text-gray-600">
                  read-only
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tag Input ──────────────────────────────────────────────

function TagInput({
  tags,
  onChange,
  disabled,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  disabled?: boolean;
}) {
  const [input, setInput] = useState("");

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput("");
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag));
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className={clsx(
            "flex items-center gap-1 rounded-full",
            "bg-brand-600/20 px-2.5 py-0.5",
            "text-xs font-medium text-brand-400"
          )}
        >
          <Tag className="h-2.5 w-2.5" />
          {tag}
          {!disabled && (
            <button
              onClick={() => removeTag(tag)}
              className="ml-0.5 text-brand-400/60 hover:text-brand-400"
            >
              x
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addTag();
            }
          }}
          placeholder="Add tag..."
          className={clsx(
            "rounded border-none bg-transparent",
            "px-1 py-0.5 text-xs text-gray-300",
            "placeholder-gray-600 outline-none",
            "w-24"
          )}
        />
      )}
    </div>
  );
}

// ── Main Editor Component ──────────────────────────────────

export default function PlaybookEditor() {
  const { id: paramId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // State
  const [selectedId, setSelectedId] = useState<
    string | null
  >(paramId ?? null);
  const [isNew, setIsNew] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [validation, setValidation] =
    useState<ValidationResult | null>(null);
  const [dryRun, setDryRun] =
    useState<DryRunResult | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  // Queries
  const { data: listData, isLoading: listLoading } =
    useQuery({
      queryKey: ["playbooks-crud"],
      queryFn: () =>
        get<PlaybookListResponse>(
          "/playbooks/custom?include_builtin=true"
        ),
    });

  const {
    data: selectedPlaybook,
    isLoading: detailLoading,
  } = useQuery({
    queryKey: ["playbook-crud-detail", selectedId],
    queryFn: () =>
      get<PlaybookData>(
        `/playbooks/custom/${selectedId}`
      ),
    enabled: !!selectedId && !isNew,
  });

  // Load playbook data into editor
  useEffect(() => {
    if (selectedPlaybook && !isNew) {
      setName(selectedPlaybook.name);
      setDescription(selectedPlaybook.description);
      setContent(selectedPlaybook.content);
      setTags(selectedPlaybook.tags);
      setValidation(null);
      setDryRun(null);
      setIsDirty(false);
    }
  }, [selectedPlaybook, isNew]);

  const isReadOnly =
    selectedId?.startsWith("builtin-") ?? false;

  // Mutations
  const createMutation = useMutation({
    mutationFn: (payload: {
      name: string;
      description: string;
      content: string;
      tags: string[];
    }) =>
      post<PlaybookData>(
        "/playbooks/custom",
        payload
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ["playbooks-crud"],
      });
      setSelectedId(data.id);
      setIsNew(false);
      setIsDirty(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (payload: {
      name?: string;
      description?: string;
      content?: string;
      tags?: string[];
    }) =>
      put<PlaybookData>(
        `/playbooks/custom/${selectedId}`,
        payload
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["playbooks-crud"],
      });
      queryClient.invalidateQueries({
        queryKey: [
          "playbook-crud-detail",
          selectedId,
        ],
      });
      setIsDirty(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () =>
      del(`/playbooks/custom/${selectedId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["playbooks-crud"],
      });
      setSelectedId(null);
      setName("");
      setDescription("");
      setContent("");
      setTags([]);
    },
  });

  const validateMutation = useMutation({
    mutationFn: () =>
      post<ValidationResult>(
        "/playbooks/validate",
        { name, description, content, tags }
      ),
    onSuccess: (data) => setValidation(data),
  });

  const dryRunMutation = useMutation({
    mutationFn: () =>
      post<DryRunResult>(
        `/playbooks/custom/${selectedId}/dry-run`
      ),
    onSuccess: (data) => setDryRun(data),
  });

  // Handlers
  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId(id);
      setIsNew(false);
      setValidation(null);
      setDryRun(null);
    },
    []
  );

  const handleNew = useCallback(() => {
    setSelectedId(null);
    setIsNew(true);
    setName("");
    setDescription("");
    setContent(DEFAULT_PLAYBOOK_TEMPLATE);
    setTags([]);
    setValidation(null);
    setDryRun(null);
    setIsDirty(true);
  }, []);

  const handleSave = () => {
    if (isNew) {
      createMutation.mutate({
        name,
        description,
        content,
        tags,
      });
    } else if (selectedId) {
      updateMutation.mutate({
        name,
        description,
        content,
        tags,
      });
    }
  };

  const handleDelete = () => {
    if (
      selectedId &&
      window.confirm(
        "Are you sure you want to delete this playbook?"
      )
    ) {
      deleteMutation.mutate();
    }
  };

  const handleContentChange = (value: string) => {
    setContent(value);
    setIsDirty(true);
    setValidation(null);
  };

  const playbooks = listData?.playbooks ?? [];
  const isSaving =
    createMutation.isPending ||
    updateMutation.isPending;
  const saveError =
    createMutation.error || updateMutation.error;

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/playbooks")}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-gray-200"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-100">
              Playbook Editor
            </h1>
            <p className="text-xs text-gray-500">
              Create and edit remediation playbooks
            </p>
          </div>
        </div>
        {isDirty && (
          <span className="text-xs text-amber-400">
            Unsaved changes
          </span>
        )}
      </div>

      {/* Split Pane */}
      <div className="mt-4 flex flex-1 overflow-hidden rounded-xl border border-gray-800">
        {/* Left Pane: File List */}
        <div className="w-64 flex-shrink-0">
          {listLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-600 border-t-brand-500" />
            </div>
          ) : (
            <PlaybookFileList
              playbooks={playbooks}
              selectedId={selectedId}
              onSelect={handleSelect}
              onNew={handleNew}
            />
          )}
        </div>

        {/* Right Pane: Editor */}
        <div className="flex flex-1 flex-col overflow-hidden bg-gray-950">
          {!selectedId && !isNew ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <FileText className="mx-auto h-12 w-12 text-gray-700" />
                <p className="mt-3 text-sm text-gray-500">
                  Select a playbook or create a new
                  one
                </p>
              </div>
            </div>
          ) : detailLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-brand-500" />
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="flex items-center gap-2 border-b border-gray-800 px-4 py-2">
                <button
                  onClick={handleSave}
                  disabled={
                    isSaving || isReadOnly || !isDirty
                  }
                  className={clsx(
                    "flex items-center gap-1.5 rounded-lg",
                    "px-3 py-1.5 text-xs font-medium",
                    "transition-colors",
                    isSaving || isReadOnly || !isDirty
                      ? "bg-gray-800 text-gray-600"
                      : "bg-brand-600 text-white hover:bg-brand-700"
                  )}
                >
                  <Save className="h-3.5 w-3.5" />
                  {isSaving ? "Saving..." : "Save"}
                </button>

                <button
                  onClick={() =>
                    validateMutation.mutate()
                  }
                  disabled={
                    validateMutation.isPending
                  }
                  className={clsx(
                    "flex items-center gap-1.5 rounded-lg",
                    "border border-gray-700 px-3 py-1.5",
                    "text-xs font-medium text-gray-300",
                    "transition-colors hover:bg-gray-800"
                  )}
                >
                  <CheckCircle className="h-3.5 w-3.5" />
                  Validate
                </button>

                {selectedId && !isNew && (
                  <button
                    onClick={() =>
                      dryRunMutation.mutate()
                    }
                    disabled={
                      dryRunMutation.isPending ||
                      isReadOnly
                    }
                    className={clsx(
                      "flex items-center gap-1.5 rounded-lg",
                      "border border-gray-700 px-3 py-1.5",
                      "text-xs font-medium text-gray-300",
                      "transition-colors hover:bg-gray-800"
                    )}
                  >
                    <Play className="h-3.5 w-3.5" />
                    Dry Run
                  </button>
                )}

                <div className="flex-1" />

                {selectedId &&
                  !isNew &&
                  !isReadOnly && (
                    <button
                      onClick={handleDelete}
                      disabled={
                        deleteMutation.isPending
                      }
                      className={clsx(
                        "flex items-center gap-1.5 rounded-lg",
                        "px-3 py-1.5 text-xs font-medium",
                        "text-red-400",
                        "transition-colors hover:bg-red-500/10"
                      )}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  )}
              </div>

              {/* Metadata Fields */}
              <div className="space-y-3 border-b border-gray-800 px-4 py-3">
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-gray-500">
                      Name
                    </label>
                    <input
                      value={name}
                      onChange={(e) => {
                        setName(e.target.value);
                        setIsDirty(true);
                      }}
                      disabled={isReadOnly}
                      className={clsx(
                        "w-full rounded-lg border border-gray-700",
                        "bg-gray-900 px-3 py-1.5 text-sm",
                        "text-gray-200",
                        "focus:border-brand-500 focus:outline-none",
                        "disabled:opacity-50"
                      )}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-gray-500">
                      Description
                    </label>
                    <input
                      value={description}
                      onChange={(e) => {
                        setDescription(e.target.value);
                        setIsDirty(true);
                      }}
                      disabled={isReadOnly}
                      className={clsx(
                        "w-full rounded-lg border border-gray-700",
                        "bg-gray-900 px-3 py-1.5 text-sm",
                        "text-gray-200",
                        "focus:border-brand-500 focus:outline-none",
                        "disabled:opacity-50"
                      )}
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-gray-500">
                    Tags
                  </label>
                  <TagInput
                    tags={tags}
                    onChange={(t) => {
                      setTags(t);
                      setIsDirty(true);
                    }}
                    disabled={isReadOnly}
                  />
                </div>
              </div>

              {/* YAML Editor */}
              <div className="flex-1 overflow-hidden">
                <textarea
                  value={content}
                  onChange={(e) =>
                    handleContentChange(
                      e.target.value
                    )
                  }
                  disabled={isReadOnly}
                  spellCheck={false}
                  className={clsx(
                    "h-full w-full resize-none",
                    "bg-gray-950 p-4",
                    "font-mono text-sm leading-relaxed",
                    "text-gray-300",
                    "focus:outline-none",
                    "disabled:opacity-60"
                  )}
                  placeholder="# Enter your playbook YAML here..."
                />
              </div>

              {/* Validation / Dry Run Results */}
              {(validation ||
                dryRun ||
                saveError) && (
                <div className="max-h-48 overflow-y-auto border-t border-gray-800 p-4">
                  {/* Save Error */}
                  {saveError && (
                    <div className="mb-3 flex items-start gap-2 rounded-lg bg-red-500/10 p-3">
                      <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
                      <div>
                        <p className="text-sm font-medium text-red-400">
                          Save Failed
                        </p>
                        <p className="mt-0.5 text-xs text-red-300/80">
                          {saveError.message}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Validation Results */}
                  {validation && (
                    <div
                      className={clsx(
                        "mb-3 rounded-lg p-3",
                        validation.is_valid
                          ? "bg-green-500/10"
                          : "bg-red-500/10"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        {validation.is_valid ? (
                          <CheckCircle className="h-4 w-4 text-green-400" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-400" />
                        )}
                        <p
                          className={clsx(
                            "text-sm font-medium",
                            validation.is_valid
                              ? "text-green-400"
                              : "text-red-400"
                          )}
                        >
                          {validation.is_valid
                            ? "Valid playbook"
                            : "Validation failed"}
                        </p>
                      </div>
                      {validation.errors.length >
                        0 && (
                        <ul className="mt-2 space-y-1">
                          {validation.errors.map(
                            (err, i) => (
                              <li
                                key={i}
                                className="text-xs text-red-300"
                              >
                                - {err}
                              </li>
                            )
                          )}
                        </ul>
                      )}
                      {validation.warnings.length >
                        0 && (
                        <ul className="mt-2 space-y-1">
                          {validation.warnings.map(
                            (w, i) => (
                              <li
                                key={i}
                                className="flex items-center gap-1 text-xs text-amber-300"
                              >
                                <AlertTriangle className="h-3 w-3" />
                                {w}
                              </li>
                            )
                          )}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* Dry Run Results */}
                  {dryRun && (
                    <div className="rounded-lg bg-blue-500/10 p-3">
                      <p className="text-sm font-medium text-blue-400">
                        Dry Run: {dryRun.playbook_name}{" "}
                        ({dryRun.total_steps} steps)
                      </p>
                      <div className="mt-2 space-y-1.5">
                        {dryRun.steps.map(
                          (step, i) => (
                            <div
                              key={i}
                              className="rounded bg-gray-900 px-3 py-1.5 text-xs"
                            >
                              <span className="text-gray-500">
                                {i + 1}.
                              </span>{" "}
                              <span className="font-medium text-blue-300">
                                {step.action}
                              </span>{" "}
                              <span className="text-gray-400">
                                on {step.target}
                              </span>
                            </div>
                          )
                        )}
                      </div>
                      {dryRun.warnings.length >
                        0 && (
                        <ul className="mt-2 space-y-1">
                          {dryRun.warnings.map(
                            (w, i) => (
                              <li
                                key={i}
                                className="flex items-center gap-1 text-xs text-amber-300"
                              >
                                <AlertTriangle className="h-3 w-3" />
                                {w}
                              </li>
                            )
                          )}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Default Template ───────────────────────────────────────

const DEFAULT_PLAYBOOK_TEMPLATE = `name: my-playbook
description: "Describe what this playbook does"
trigger:
  alert_type: "AlertName"
  severity:
    - critical
    - warning
steps:
  - action: check_status
    target: service-name
    params:
      timeout: 30
  - action: restart_service
    target: service-name
    params:
      grace_period: 10
`;
