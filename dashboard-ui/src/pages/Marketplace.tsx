import { useState, useMemo } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Store,
  Search,
  Filter,
  X,
  Rocket,
  Eye,
  Clock,
  Shield,
  Server,
  Cloud,
  Terminal,
  DollarSign,
  AlertTriangle,
  CheckCircle,
  Star,
  ChevronDown,
} from "lucide-react";
import clsx from "clsx";
import { get, post } from "../api/client";
import LoadingSpinner from "../components/LoadingSpinner";

// ── Types ───────────────────────────────────────────────────────

interface TemplateParameter {
  name: string;
  type: string;
  required: boolean;
  default: unknown;
  description: string;
}

interface TemplateStep {
  name: string;
  action: string;
  config: Record<string, unknown>;
}

interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  cloud_providers: string[];
  agent_type: string;
  risk_level: string;
  tags: string[];
  estimated_setup_minutes: number;
  featured: boolean;
  parameters: TemplateParameter[];
  steps: TemplateStep[];
}

interface TemplatesResponse {
  templates: AgentTemplate[];
  total: number;
}

interface CategoriesResponse {
  categories: { category: string; count: number }[];
  total: number;
}

interface DeployResponse {
  deployment_id: string;
  template_id: string;
  template_name: string;
  status: string;
}

// ── Helpers ─────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<
  string,
  { label: string; color: string; icon: typeof Shield }
> = {
  remediation: {
    label: "Remediation",
    color: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    icon: Server,
  },
  security: {
    label: "Security",
    color: "bg-red-500/20 text-red-400 border-red-500/30",
    icon: Shield,
  },
  cost: {
    label: "Cost",
    color: "bg-green-500/20 text-green-400 border-green-500/30",
    icon: DollarSign,
  },
  investigation: {
    label: "Investigation",
    color: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    icon: Search,
  },
};

const CLOUD_CONFIG: Record<string, { label: string; color: string }> = {
  aws: { label: "AWS", color: "bg-orange-500/20 text-orange-400" },
  gcp: { label: "GCP", color: "bg-blue-500/20 text-blue-400" },
  azure: { label: "Azure", color: "bg-sky-500/20 text-sky-400" },
  kubernetes: { label: "K8s", color: "bg-indigo-500/20 text-indigo-400" },
  linux: { label: "Linux", color: "bg-gray-500/20 text-gray-400" },
};

const RISK_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: "Low Risk", color: "bg-green-500/20 text-green-400" },
  medium: { label: "Medium Risk", color: "bg-yellow-500/20 text-yellow-400" },
  high: { label: "High Risk", color: "bg-red-500/20 text-red-400" },
};

// ── Sub-Components ──────────────────────────────────────────────

function CategoryPill({
  category,
  active,
  count,
  onClick,
}: {
  category: string;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  const cfg = CATEGORY_CONFIG[category] ?? {
    label: category,
    color: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    icon: Server,
  };
  const Icon = cfg.icon;

  return (
    <button
      onClick={onClick}
      className={clsx(
        "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all",
        active
          ? "border-brand-500 bg-brand-600/20 text-brand-400"
          : "border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600 hover:text-gray-300"
      )}
    >
      <Icon className="h-4 w-4" />
      {cfg.label}
      {count !== undefined && (
        <span
          className={clsx(
            "ml-1 rounded-full px-1.5 py-0.5 text-xs",
            active ? "bg-brand-600/30" : "bg-gray-700"
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

function TemplateCard({
  template,
  onPreview,
  onDeploy,
}: {
  template: AgentTemplate;
  onPreview: (t: AgentTemplate) => void;
  onDeploy: (t: AgentTemplate) => void;
}) {
  const catCfg = CATEGORY_CONFIG[template.category] ?? {
    label: template.category,
    color: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    icon: Server,
  };
  const riskCfg = RISK_CONFIG[template.risk_level] ?? RISK_CONFIG.low;
  const CatIcon = catCfg.icon;

  return (
    <div
      className={clsx(
        "group flex flex-col rounded-xl border border-gray-800 bg-gray-900",
        "transition-all hover:border-gray-700 hover:shadow-lg hover:shadow-black/20"
      )}
    >
      {/* Header */}
      <div className="flex-1 p-5">
        <div className="flex items-start justify-between gap-3">
          <div
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-lg",
              catCfg.color
            )}
          >
            <CatIcon className="h-5 w-5" />
          </div>
          <div className="flex items-center gap-1.5">
            {template.featured && (
              <span className="flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-400">
                <Star className="h-3 w-3" />
                Featured
              </span>
            )}
            <span
              className={clsx(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                riskCfg.color
              )}
            >
              {riskCfg.label}
            </span>
          </div>
        </div>

        <h3 className="mt-3 text-base font-semibold text-gray-100">
          {template.name}
        </h3>
        <p className="mt-1.5 line-clamp-2 text-sm text-gray-400">
          {template.description}
        </p>

        {/* Tags */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {template.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-gray-700 px-2 py-0.5 text-xs text-gray-500"
            >
              {tag}
            </span>
          ))}
          {template.tags.length > 4 && (
            <span className="rounded-full px-2 py-0.5 text-xs text-gray-600">
              +{template.tags.length - 4}
            </span>
          )}
        </div>

        {/* Cloud providers */}
        <div className="mt-3 flex items-center gap-2">
          {template.cloud_providers.map((cp) => {
            const cloudCfg = CLOUD_CONFIG[cp];
            return (
              <span
                key={cp}
                className={clsx(
                  "rounded px-1.5 py-0.5 text-xs font-medium",
                  cloudCfg?.color ?? "bg-gray-700 text-gray-400"
                )}
              >
                {cloudCfg?.label ?? cp}
              </span>
            );
          })}
        </div>

        {/* Meta */}
        <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {template.estimated_setup_minutes} min setup
          </span>
          <span className="flex items-center gap-1">
            <Terminal className="h-3.5 w-3.5" />
            {template.steps.length} steps
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 border-t border-gray-800 p-3">
        <button
          onClick={() => onPreview(template)}
          className={clsx(
            "flex flex-1 items-center justify-center gap-1.5 rounded-lg",
            "border border-gray-700 py-2 text-sm font-medium text-gray-400",
            "transition-colors hover:border-gray-600 hover:text-gray-300"
          )}
        >
          <Eye className="h-4 w-4" />
          Preview
        </button>
        <button
          onClick={() => onDeploy(template)}
          className={clsx(
            "flex flex-1 items-center justify-center gap-1.5 rounded-lg",
            "bg-brand-600 py-2 text-sm font-medium text-white",
            "transition-colors hover:bg-brand-700"
          )}
        >
          <Rocket className="h-4 w-4" />
          Deploy
        </button>
      </div>
    </div>
  );
}

function DeployModal({
  template,
  onClose,
}: {
  template: AgentTemplate;
  onClose: () => void;
}) {
  const [params, setParams] = useState<Record<string, unknown>>(() => {
    const defaults: Record<string, unknown> = {};
    for (const p of template.parameters) {
      defaults[p.name] = p.default ?? "";
    }
    return defaults;
  });
  const [environment, setEnvironment] = useState("production");
  const [deployResult, setDeployResult] = useState<DeployResponse | null>(null);

  const deployMutation = useMutation({
    mutationFn: (body: {
      template_id: string;
      environment: string;
      parameters: Record<string, unknown>;
    }) => post<DeployResponse>("/marketplace/deploy", body),
    onSuccess: (data) => setDeployResult(data),
  });

  const handleDeploy = () => {
    deployMutation.mutate({
      template_id: template.id,
      environment,
      parameters: params,
    });
  };

  const handleParamChange = (name: string, value: string, type: string) => {
    let parsed: unknown = value;
    if (type === "integer") {
      parsed = parseInt(value, 10) || 0;
    } else if (type === "boolean") {
      parsed = value === "true";
    }
    setParams((prev) => ({ ...prev, [name]: parsed }));
  };

  const riskCfg = RISK_CONFIG[template.risk_level] ?? RISK_CONFIG.low;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-gray-700 bg-gray-900">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-800 p-6">
          <div>
            <h2 className="text-xl font-bold text-gray-100">
              {deployResult ? "Deployment Successful" : `Deploy: ${template.name}`}
            </h2>
            <p className="mt-1 text-sm text-gray-400">
              {deployResult
                ? `Template deployed as ${deployResult.deployment_id}`
                : template.description}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {deployResult ? (
          /* Success state */
          <div className="p-6">
            <div className="flex items-center gap-3 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
              <CheckCircle className="h-6 w-6 text-green-400" />
              <div>
                <p className="font-medium text-green-400">
                  Template deployed successfully
                </p>
                <p className="mt-0.5 text-sm text-gray-400">
                  Deployment ID: {deployResult.deployment_id}
                </p>
              </div>
            </div>
            <div className="mt-4 rounded-lg bg-gray-800 p-4">
              <pre className="text-sm text-gray-300">
                {JSON.stringify(deployResult, null, 2)}
              </pre>
            </div>
            <button
              onClick={onClose}
              className="mt-4 w-full rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Close
            </button>
          </div>
        ) : (
          /* Configuration form */
          <div className="p-6">
            {/* Risk warning */}
            {template.risk_level === "high" && (
              <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                <AlertTriangle className="h-5 w-5 shrink-0 text-red-400" />
                <p className="text-sm text-red-400">
                  This template has a high risk level. Actions will require
                  approval before execution.
                </p>
              </div>
            )}

            {/* Environment */}
            <div className="mb-4">
              <label className="mb-1.5 block text-sm font-medium text-gray-300">
                Environment
              </label>
              <select
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
                className={clsx(
                  "w-full rounded-lg border border-gray-700 bg-gray-800",
                  "px-3 py-2 text-sm text-gray-200",
                  "focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                )}
              >
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="development">Development</option>
              </select>
            </div>

            {/* Risk & Info badges */}
            <div className="mb-4 flex items-center gap-3">
              <span
                className={clsx(
                  "rounded-full px-2.5 py-1 text-xs font-medium",
                  riskCfg.color
                )}
              >
                {riskCfg.label}
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Clock className="h-3.5 w-3.5" />
                {template.estimated_setup_minutes} min setup
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Terminal className="h-3.5 w-3.5" />
                {template.steps.length} steps
              </span>
            </div>

            {/* Parameters */}
            {template.parameters.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-gray-300">
                  Parameters
                </h3>
                {template.parameters.map((p) => (
                  <div key={p.name}>
                    <label className="mb-1 flex items-center gap-2 text-sm text-gray-400">
                      {p.name}
                      {p.required && (
                        <span className="text-xs text-red-400">*</span>
                      )}
                    </label>
                    <p className="mb-1 text-xs text-gray-500">
                      {p.description}
                    </p>
                    {p.type === "boolean" ? (
                      <select
                        value={String(params[p.name])}
                        onChange={(e) =>
                          handleParamChange(p.name, e.target.value, p.type)
                        }
                        className={clsx(
                          "w-full rounded-lg border border-gray-700 bg-gray-800",
                          "px-3 py-2 text-sm text-gray-200",
                          "focus:border-brand-500 focus:outline-none"
                        )}
                      >
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    ) : (
                      <input
                        type={p.type === "integer" ? "number" : "text"}
                        value={String(params[p.name] ?? "")}
                        onChange={(e) =>
                          handleParamChange(p.name, e.target.value, p.type)
                        }
                        className={clsx(
                          "w-full rounded-lg border border-gray-700 bg-gray-800",
                          "px-3 py-2 text-sm text-gray-200 placeholder-gray-600",
                          "focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                        )}
                        placeholder={
                          p.default !== null && p.default !== undefined
                            ? String(p.default)
                            : `Enter ${p.name}`
                        }
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Steps preview */}
            <details className="mt-4">
              <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-400 hover:text-gray-300">
                <ChevronDown className="h-4 w-4" />
                Execution Steps ({template.steps.length})
              </summary>
              <ol className="mt-2 space-y-2 border-l border-gray-700 pl-4">
                {template.steps.map((step, idx) => (
                  <li key={step.name} className="text-sm">
                    <span className="text-gray-500">{idx + 1}.</span>{" "}
                    <span className="font-medium text-gray-300">
                      {step.name}
                    </span>
                    <span className="ml-2 text-xs text-gray-500">
                      ({step.action})
                    </span>
                  </li>
                ))}
              </ol>
            </details>

            {/* Deploy button */}
            <button
              onClick={handleDeploy}
              disabled={deployMutation.isPending}
              className={clsx(
                "mt-6 flex w-full items-center justify-center gap-2 rounded-lg",
                "bg-brand-600 py-2.5 text-sm font-medium text-white",
                "transition-colors hover:bg-brand-700",
                "disabled:opacity-50"
              )}
            >
              <Rocket className="h-4 w-4" />
              {deployMutation.isPending ? "Deploying..." : "Deploy Now"}
            </button>

            {deployMutation.isError && (
              <p className="mt-2 text-center text-sm text-red-400">
                Deployment failed. Please check parameters and try again.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function PreviewModal({
  template,
  onClose,
  onDeploy,
}: {
  template: AgentTemplate;
  onClose: () => void;
  onDeploy: (t: AgentTemplate) => void;
}) {
  const catCfg = CATEGORY_CONFIG[template.category] ?? {
    label: template.category,
    color: "bg-gray-500/20 text-gray-400",
    icon: Server,
  };
  const riskCfg = RISK_CONFIG[template.risk_level] ?? RISK_CONFIG.low;
  const CatIcon = catCfg.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-gray-700 bg-gray-900">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-800 p-6">
          <div className="flex items-start gap-4">
            <div
              className={clsx(
                "flex h-12 w-12 items-center justify-center rounded-lg",
                catCfg.color
              )}
            >
              <CatIcon className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-100">
                {template.name}
              </h2>
              <div className="mt-1 flex items-center gap-2">
                <span
                  className={clsx(
                    "rounded-full border px-2 py-0.5 text-xs font-medium",
                    catCfg.color
                  )}
                >
                  {catCfg.label}
                </span>
                <span
                  className={clsx(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    riskCfg.color
                  )}
                >
                  {riskCfg.label}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-6 p-6">
          {/* Description */}
          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Description
            </h3>
            <p className="text-sm text-gray-300">{template.description}</p>
          </div>

          {/* Cloud providers */}
          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Supported Platforms
            </h3>
            <div className="flex flex-wrap gap-2">
              {template.cloud_providers.map((cp) => {
                const cloudCfg = CLOUD_CONFIG[cp];
                return (
                  <span
                    key={cp}
                    className={clsx(
                      "flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm font-medium",
                      cloudCfg?.color ?? "bg-gray-700 text-gray-400"
                    )}
                  >
                    <Cloud className="h-3.5 w-3.5" />
                    {cloudCfg?.label ?? cp}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Tags */}
          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Tags
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {template.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-gray-700 px-2.5 py-0.5 text-xs text-gray-400"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Parameters */}
          {template.parameters.length > 0 && (
            <div>
              <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Parameters ({template.parameters.length})
              </h3>
              <div className="space-y-2">
                {template.parameters.map((p) => (
                  <div
                    key={p.name}
                    className="rounded-lg border border-gray-800 bg-gray-800/50 p-3"
                  >
                    <div className="flex items-center gap-2">
                      <code className="text-sm font-medium text-brand-400">
                        {p.name}
                      </code>
                      <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">
                        {p.type}
                      </span>
                      {p.required && (
                        <span className="text-xs text-red-400">required</span>
                      )}
                      {p.default !== null && p.default !== undefined && (
                        <span className="text-xs text-gray-500">
                          default: {String(p.default)}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {p.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Steps */}
          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Execution Steps ({template.steps.length})
            </h3>
            <ol className="space-y-2">
              {template.steps.map((step, idx) => (
                <li
                  key={step.name}
                  className="flex items-start gap-3 rounded-lg border border-gray-800 bg-gray-800/50 p-3"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-700 text-xs font-medium text-gray-300">
                    {idx + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-200">
                      {step.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      Action: {step.action}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 border-t border-gray-800 p-6">
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-gray-700 py-2 text-sm font-medium text-gray-400 hover:border-gray-600 hover:text-gray-300"
          >
            Close
          </button>
          <button
            onClick={() => onDeploy(template)}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            <Rocket className="h-4 w-4" />
            Deploy
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Filter Sidebar ──────────────────────────────────────────────

function FilterSidebar({
  categories,
  selectedCategories,
  onToggleCategory,
  selectedClouds,
  onToggleCloud,
  selectedRisk,
  onToggleRisk,
  onClearAll,
}: {
  categories: { category: string; count: number }[];
  selectedCategories: Set<string>;
  onToggleCategory: (cat: string) => void;
  selectedClouds: Set<string>;
  onToggleCloud: (cloud: string) => void;
  selectedRisk: Set<string>;
  onToggleRisk: (risk: string) => void;
  onClearAll: () => void;
}) {
  const hasFilters =
    selectedCategories.size > 0 ||
    selectedClouds.size > 0 ||
    selectedRisk.size > 0;

  return (
    <div className="w-56 shrink-0 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-300">
          <Filter className="h-4 w-4" />
          Filters
        </h3>
        {hasFilters && (
          <button
            onClick={onClearAll}
            className="text-xs text-brand-400 hover:text-brand-300"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Category */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
          Category
        </h4>
        <div className="space-y-1">
          {categories.map(({ category, count }) => (
            <label
              key={category}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-gray-800"
            >
              <input
                type="checkbox"
                checked={selectedCategories.has(category)}
                onChange={() => onToggleCategory(category)}
                className="rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
              />
              <span className="text-gray-400">
                {CATEGORY_CONFIG[category]?.label ?? category}
              </span>
              <span className="ml-auto text-xs text-gray-600">{count}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Cloud provider */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
          Cloud Provider
        </h4>
        <div className="space-y-1">
          {Object.entries(CLOUD_CONFIG).map(([key, cfg]) => (
            <label
              key={key}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-gray-800"
            >
              <input
                type="checkbox"
                checked={selectedClouds.has(key)}
                onChange={() => onToggleCloud(key)}
                className="rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
              />
              <span className="text-gray-400">{cfg.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Risk level */}
      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
          Risk Level
        </h4>
        <div className="space-y-1">
          {Object.entries(RISK_CONFIG).map(([key, cfg]) => (
            <label
              key={key}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-gray-800"
            >
              <input
                type="checkbox"
                checked={selectedRisk.has(key)}
                onChange={() => onToggleRisk(key)}
                className="rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
              />
              <span className="text-gray-400">{cfg.label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────

export default function Marketplace() {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    new Set()
  );
  const [selectedClouds, setSelectedClouds] = useState<Set<string>>(new Set());
  const [selectedRisk, setSelectedRisk] = useState<Set<string>>(new Set());
  const [previewTemplate, setPreviewTemplate] = useState<AgentTemplate | null>(
    null
  );
  const [deployTemplate, setDeployTemplate] = useState<AgentTemplate | null>(
    null
  );

  // Fetch templates
  const { data: templatesData, isLoading } = useQuery({
    queryKey: ["marketplace-templates"],
    queryFn: () => get<TemplatesResponse>("/marketplace/templates"),
  });

  // Fetch categories
  const { data: categoriesData } = useQuery({
    queryKey: ["marketplace-categories"],
    queryFn: () => get<CategoriesResponse>("/marketplace/categories"),
  });

  const allTemplates = useMemo(() => templatesData?.templates ?? [], [templatesData]);
  const categories = categoriesData?.categories ?? [];

  // Client-side filtering for real-time search and sidebar filters
  const filtered = useMemo(() => {
    let results = allTemplates;

    // Category pill filter
    if (activeCategory) {
      results = results.filter((t) => t.category === activeCategory);
    }

    // Sidebar category checkboxes
    if (selectedCategories.size > 0 && !activeCategory) {
      results = results.filter((t) => selectedCategories.has(t.category));
    }

    // Cloud provider filter
    if (selectedClouds.size > 0) {
      results = results.filter((t) =>
        t.cloud_providers.some((cp) => selectedClouds.has(cp))
      );
    }

    // Risk filter
    if (selectedRisk.size > 0) {
      results = results.filter((t) => selectedRisk.has(t.risk_level));
    }

    // Text search
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      results = results.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q) ||
          t.tags.some((tag) => tag.toLowerCase().includes(q))
      );
    }

    return results;
  }, [
    allTemplates,
    activeCategory,
    selectedCategories,
    selectedClouds,
    selectedRisk,
    searchTerm,
  ]);

  const toggleSet = (
    setter: React.Dispatch<React.SetStateAction<Set<string>>>,
    value: string
  ) => {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const clearAllFilters = () => {
    setSelectedCategories(new Set());
    setSelectedClouds(new Set());
    setSelectedRisk(new Set());
    setActiveCategory(null);
    setSearchTerm("");
  };

  const handleStartDeploy = (t: AgentTemplate) => {
    setPreviewTemplate(null);
    setDeployTemplate(t);
  };

  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900 via-gray-900 to-brand-950/30 p-8">
        <div className="flex items-center gap-3">
          <Store className="h-8 w-8 text-brand-400" />
          <h1 className="text-2xl font-bold text-gray-100">
            Agent Marketplace
          </h1>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-gray-400">
          Browse pre-built agent templates for common SRE scenarios. Deploy
          remediation, security, cost, and investigation agents in minutes
          with configurable parameters and approval workflows.
        </p>

        {/* Search bar */}
        <div className="relative mt-5 max-w-xl">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search templates by name, description, or tags..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={clsx(
              "w-full rounded-lg border border-gray-700 bg-gray-800",
              "py-2.5 pl-10 pr-4 text-sm text-gray-200 placeholder-gray-500",
              "focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            )}
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Category pills */}
        <div className="mt-4 flex flex-wrap gap-2">
          <CategoryPill
            category="all"
            active={activeCategory === null}
            onClick={() => setActiveCategory(null)}
          />
          {categories.map(({ category, count }) => (
            <CategoryPill
              key={category}
              category={category}
              active={activeCategory === category}
              count={count}
              onClick={() =>
                setActiveCategory(
                  activeCategory === category ? null : category
                )
              }
            />
          ))}
        </div>
      </div>

      {/* Content: Sidebar + Grid */}
      <div className="flex gap-6">
        <FilterSidebar
          categories={categories}
          selectedCategories={selectedCategories}
          onToggleCategory={(cat) => toggleSet(setSelectedCategories, cat)}
          selectedClouds={selectedClouds}
          onToggleCloud={(cloud) => toggleSet(setSelectedClouds, cloud)}
          selectedRisk={selectedRisk}
          onToggleRisk={(risk) => toggleSet(setSelectedRisk, risk)}
          onClearAll={clearAllFilters}
        />

        {/* Template grid */}
        <div className="flex-1">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-gray-800 bg-gray-900 py-16">
              <Store className="h-10 w-10 text-gray-600" />
              <p className="mt-3 text-gray-400">
                {searchTerm || selectedCategories.size > 0
                  ? "No templates match your filters."
                  : "No templates available."}
              </p>
              {(searchTerm ||
                selectedCategories.size > 0 ||
                selectedClouds.size > 0) && (
                <button
                  onClick={clearAllFilters}
                  className="mt-2 text-sm text-brand-400 hover:text-brand-300"
                >
                  Clear all filters
                </button>
              )}
            </div>
          ) : (
            <>
              <p className="mb-3 text-sm text-gray-500">
                Showing {filtered.length} of {allTemplates.length} templates
              </p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {filtered.map((t) => (
                  <TemplateCard
                    key={t.id}
                    template={t}
                    onPreview={setPreviewTemplate}
                    onDeploy={handleStartDeploy}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Modals */}
      {previewTemplate && (
        <PreviewModal
          template={previewTemplate}
          onClose={() => setPreviewTemplate(null)}
          onDeploy={handleStartDeploy}
        />
      )}
      {deployTemplate && (
        <DeployModal
          template={deployTemplate}
          onClose={() => setDeployTemplate(null)}
        />
      )}
    </div>
  );
}
