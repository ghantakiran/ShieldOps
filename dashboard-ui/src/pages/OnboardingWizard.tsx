import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Cloud,
  Bot,
  BookOpen,
  Play,
  Check,
  ChevronRight,
  ChevronLeft,
  SkipForward,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Server,
} from "lucide-react";
import clsx from "clsx";
import { get, post } from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StepStatus {
  step_name: string;
  status: "pending" | "completed" | "skipped";
  metadata: Record<string, unknown>;
  completed_at: string | null;
}

interface OnboardingState {
  org_id: string;
  steps: StepStatus[];
  current_step: string;
  completed: boolean;
}

interface CloudValidationResponse {
  success: boolean;
  provider: string;
  message: string;
  services_discovered: string[];
}

interface DeployAgentResponse {
  success: boolean;
  agent_id: string;
  agent_type: string;
  environment: string;
  message: string;
}

interface TriggerDemoResponse {
  success: boolean;
  investigation_id: string;
  scenario: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEPS = [
  {
    key: "create_org",
    label: "Organization Setup",
    icon: Building2,
    description: "Set up your organization profile",
  },
  {
    key: "connect_cloud",
    label: "Connect Cloud",
    icon: Cloud,
    description: "Connect your cloud infrastructure",
  },
  {
    key: "deploy_agent",
    label: "Deploy Agent",
    icon: Bot,
    description: "Deploy your first AI agent",
  },
  {
    key: "configure_playbook",
    label: "Configure Playbook",
    icon: BookOpen,
    description: "Select a remediation playbook",
  },
  {
    key: "run_demo",
    label: "Run Demo",
    icon: Play,
    description: "See ShieldOps in action",
  },
] as const;

const AGENT_TYPES = [
  {
    type: "investigation",
    label: "Investigation",
    description: "Root cause analysis from alerts, logs, and metrics",
  },
  {
    type: "remediation",
    label: "Remediation",
    description: "Execute infrastructure changes with policy gates",
  },
  {
    type: "security",
    label: "Security",
    description: "CVE patching, credential rotation, compliance",
  },
  {
    type: "cost",
    label: "Cost",
    description: "Cloud cost monitoring and anomaly detection",
  },
] as const;

const PLAYBOOK_TEMPLATES = [
  {
    id: "auto-scale",
    name: "Auto-Scale on High CPU",
    description:
      "Automatically scale services when CPU exceeds 80% for 5 minutes",
    tags: ["kubernetes", "scaling"],
  },
  {
    id: "restart-unhealthy",
    name: "Restart Unhealthy Pods",
    description: "Restart pods that fail health checks for 3 consecutive cycles",
    tags: ["kubernetes", "health"],
  },
  {
    id: "rotate-creds",
    name: "Credential Rotation",
    description:
      "Rotate expiring credentials and update dependent services",
    tags: ["security", "credentials"],
  },
  {
    id: "patch-critical",
    name: "Critical CVE Patching",
    description:
      "Auto-patch critical CVEs with CVSS >= 9.0 in non-production",
    tags: ["security", "cve"],
  },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: onboardingState,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["onboarding", "status"],
    queryFn: () => get<OnboardingState>("/onboarding/status"),
  });

  // Determine active step index from server state
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (!onboardingState) return;
    if (onboardingState.completed) {
      navigate("/", { replace: true });
      return;
    }
    const idx = STEPS.findIndex(
      (s) => s.key === onboardingState.current_step,
    );
    if (idx >= 0) setActiveStep(idx);
  }, [onboardingState, navigate]);

  const isStepDone = useCallback(
    (key: string): boolean => {
      if (!onboardingState) return false;
      const step = onboardingState.steps.find((s) => s.step_name === key);
      return step?.status === "completed" || step?.status === "skipped";
    },
    [onboardingState],
  );

  // -- Generic step completion mutation --------------------------------
  const stepMutation = useMutation({
    mutationFn: async ({
      stepName,
      status,
      metadata,
    }: {
      stepName: string;
      status: "completed" | "skipped";
      metadata?: Record<string, unknown>;
    }) => {
      return post<OnboardingState>(
        `/onboarding/step/${stepName}`,
        { status, metadata: metadata ?? {} },
      );
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["onboarding", "status"], data);
      if (data.completed) {
        navigate("/", { replace: true });
      } else {
        const nextIdx = STEPS.findIndex(
          (s) => s.key === data.current_step,
        );
        if (nextIdx >= 0) setActiveStep(nextIdx);
      }
    },
  });

  const goNext = () => {
    if (activeStep < STEPS.length - 1) setActiveStep(activeStep + 1);
  };
  const goBack = () => {
    if (activeStep > 0) setActiveStep(activeStep - 1);
  };

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto mt-16 max-w-xl rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
        <AlertCircle className="mx-auto h-8 w-8 text-red-400" />
        <p className="mt-3 text-sm text-red-400">
          Failed to load onboarding status. Please try again.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">
          Welcome to ShieldOps
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Let's get your autonomous SRE platform up and running in a few
          steps.
        </p>
      </div>

      {/* Progress bar */}
      <div className="flex items-center gap-2">
        {STEPS.map((step, idx) => {
          const done = isStepDone(step.key);
          const active = idx === activeStep;
          return (
            <div key={step.key} className="flex flex-1 items-center gap-2">
              <button
                onClick={() => setActiveStep(idx)}
                className={clsx(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-medium transition-colors",
                  done
                    ? "bg-green-500/20 text-green-400"
                    : active
                      ? "bg-brand-500/20 text-brand-400 ring-2 ring-brand-500/50"
                      : "bg-gray-800 text-gray-500",
                )}
                aria-label={step.label}
              >
                {done ? <Check className="h-4 w-4" /> : idx + 1}
              </button>
              {idx < STEPS.length - 1 && (
                <div
                  className={clsx(
                    "h-0.5 flex-1 rounded",
                    done ? "bg-green-500/40" : "bg-gray-800",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Step label */}
      <div className="text-center">
        <p className="text-lg font-semibold text-gray-100">
          {STEPS[activeStep].label}
        </p>
        <p className="text-sm text-gray-500">
          {STEPS[activeStep].description}
        </p>
      </div>

      {/* Step content */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
        {activeStep === 0 && (
          <OrganizationStep
            done={isStepDone("create_org")}
            onComplete={(meta) =>
              stepMutation.mutate({
                stepName: "create_org",
                status: "completed",
                metadata: meta,
              })
            }
            isPending={stepMutation.isPending}
          />
        )}
        {activeStep === 1 && (
          <CloudStep
            done={isStepDone("connect_cloud")}
            isPending={stepMutation.isPending}
          />
        )}
        {activeStep === 2 && (
          <DeployAgentStep done={isStepDone("deploy_agent")} />
        )}
        {activeStep === 3 && (
          <PlaybookStep
            done={isStepDone("configure_playbook")}
            onComplete={(meta) =>
              stepMutation.mutate({
                stepName: "configure_playbook",
                status: "completed",
                metadata: meta,
              })
            }
            onSkip={() =>
              stepMutation.mutate({
                stepName: "configure_playbook",
                status: "skipped",
              })
            }
            isPending={stepMutation.isPending}
          />
        )}
        {activeStep === 4 && (
          <DemoStep done={isStepDone("run_demo")} />
        )}
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between">
        <button
          onClick={goBack}
          disabled={activeStep === 0}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
            activeStep === 0
              ? "cursor-not-allowed bg-gray-800 text-gray-600"
              : "bg-gray-800 text-gray-300 hover:bg-gray-700",
          )}
        >
          <ChevronLeft className="h-4 w-4" />
          Back
        </button>

        <div className="flex gap-3">
          {activeStep < STEPS.length - 1 &&
            !isStepDone(STEPS[activeStep].key) && (
              <button
                onClick={() =>
                  stepMutation.mutate({
                    stepName: STEPS[activeStep].key,
                    status: "skipped",
                  })
                }
                disabled={stepMutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-700 hover:text-gray-200"
              >
                <SkipForward className="h-4 w-4" />
                Skip
              </button>
            )}

          {activeStep < STEPS.length - 1 && (
            <button
              onClick={goNext}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Mutation error */}
      {stepMutation.isError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to save progress. Please try again.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1 -- Organization Setup
// ---------------------------------------------------------------------------

function OrganizationStep({
  done,
  onComplete,
  isPending,
}: {
  done: boolean;
  onComplete: (meta: Record<string, unknown>) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [teamSize, setTeamSize] = useState("");

  if (done) {
    return <DoneMessage message="Organization setup complete." />;
  }

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Organization Name *
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Acme Corp"
          className="mt-1.5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Industry
        </label>
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="mt-1.5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">Select industry...</option>
          <option value="fintech">Fintech</option>
          <option value="healthcare">Healthcare</option>
          <option value="saas">SaaS</option>
          <option value="ecommerce">E-Commerce</option>
          <option value="gaming">Gaming</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Team Size
        </label>
        <select
          value={teamSize}
          onChange={(e) => setTeamSize(e.target.value)}
          className="mt-1.5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">Select team size...</option>
          <option value="1-10">1-10</option>
          <option value="11-50">11-50</option>
          <option value="51-200">51-200</option>
          <option value="201-1000">201-1000</option>
          <option value="1000+">1000+</option>
        </select>
      </div>

      <button
        onClick={() =>
          onComplete({ name, industry, team_size: teamSize })
        }
        disabled={!name.trim() || isPending}
        className={clsx(
          "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors",
          name.trim()
            ? "bg-brand-500 text-white hover:bg-brand-600"
            : "cursor-not-allowed bg-gray-800 text-gray-500",
        )}
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Check className="h-4 w-4" />
        )}
        Save Organization
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2 -- Connect Cloud
// ---------------------------------------------------------------------------

function CloudStep({
  done,
}: {
  done: boolean;
  isPending: boolean;
}) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<"aws" | "gcp" | "azure">("aws");
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [validationResult, setValidationResult] =
    useState<CloudValidationResponse | null>(null);

  const validateMutation = useMutation({
    mutationFn: (data: { provider: string; credentials: Record<string, string> }) =>
      post<CloudValidationResponse>("/onboarding/validate-cloud", data),
    onSuccess: (data) => {
      setValidationResult(data);
      if (data.success) {
        queryClient.invalidateQueries({ queryKey: ["onboarding", "status"] });
      }
    },
  });

  const PROVIDER_FIELDS: Record<string, { key: string; label: string; placeholder: string }[]> = {
    aws: [
      { key: "access_key_id", label: "Access Key ID", placeholder: "AKIA..." },
      { key: "secret_access_key", label: "Secret Access Key", placeholder: "wJalrX..." },
    ],
    gcp: [
      { key: "project_id", label: "Project ID", placeholder: "my-project-123" },
      { key: "service_account_key", label: "Service Account Key (JSON)", placeholder: '{"type": "service_account"...}' },
    ],
    azure: [
      { key: "subscription_id", label: "Subscription ID", placeholder: "xxxxxxxx-xxxx-..." },
      { key: "tenant_id", label: "Tenant ID", placeholder: "xxxxxxxx-xxxx-..." },
      { key: "client_id", label: "Client ID", placeholder: "xxxxxxxx-xxxx-..." },
    ],
  };

  if (done) {
    return <DoneMessage message="Cloud connection established." />;
  }

  const fields = PROVIDER_FIELDS[provider] || [];

  return (
    <div className="space-y-5">
      {/* Provider tabs */}
      <div className="flex gap-2">
        {(["aws", "gcp", "azure"] as const).map((p) => (
          <button
            key={p}
            onClick={() => {
              setProvider(p);
              setCreds({});
              setValidationResult(null);
            }}
            className={clsx(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              provider === p
                ? "bg-brand-500/20 text-brand-400"
                : "bg-gray-800 text-gray-400 hover:text-gray-200",
            )}
          >
            {p.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Credential fields */}
      {fields.map((field) => (
        <div key={field.key}>
          <label className="block text-sm font-medium text-gray-300">
            {field.label}
          </label>
          <input
            type={field.key.includes("secret") || field.key.includes("key") ? "password" : "text"}
            value={creds[field.key] || ""}
            onChange={(e) =>
              setCreds((prev) => ({ ...prev, [field.key]: e.target.value }))
            }
            placeholder={field.placeholder}
            className="mt-1.5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      ))}

      {/* Validation result */}
      {validationResult && (
        <div
          className={clsx(
            "rounded-lg border px-4 py-3 text-sm",
            validationResult.success
              ? "border-green-500/20 bg-green-500/10 text-green-400"
              : "border-red-500/20 bg-red-500/10 text-red-400",
          )}
        >
          <p className="font-medium">{validationResult.message}</p>
          {validationResult.success &&
            validationResult.services_discovered.length > 0 && (
              <p className="mt-1 text-xs text-green-500">
                Services discovered:{" "}
                {validationResult.services_discovered.join(", ")}
              </p>
            )}
        </div>
      )}

      {/* Test Connection button */}
      <button
        onClick={() =>
          validateMutation.mutate({
            provider,
            credentials: creds,
          })
        }
        disabled={
          validateMutation.isPending ||
          !fields.every((f) => creds[f.key]?.trim())
        }
        className={clsx(
          "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors",
          fields.every((f) => creds[f.key]?.trim())
            ? "bg-brand-500 text-white hover:bg-brand-600"
            : "cursor-not-allowed bg-gray-800 text-gray-500",
        )}
      >
        {validateMutation.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Cloud className="h-4 w-4" />
        )}
        Test Connection
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3 -- Deploy First Agent
// ---------------------------------------------------------------------------

function DeployAgentStep({ done }: { done: boolean }) {
  const queryClient = useQueryClient();
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const deployMutation = useMutation({
    mutationFn: (data: { agent_type: string; environment: string }) =>
      post<DeployAgentResponse>("/onboarding/deploy-agent", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", "status"] });
    },
  });

  if (done) {
    return <DoneMessage message="Agent deployed successfully." />;
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-400">
        Choose an agent type to deploy. You can add more agents later from
        the Fleet Overview.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {AGENT_TYPES.map((agent) => (
          <button
            key={agent.type}
            onClick={() => setSelectedType(agent.type)}
            className={clsx(
              "rounded-xl border p-4 text-left transition-colors",
              selectedType === agent.type
                ? "border-brand-500 bg-brand-500/10"
                : "border-gray-700 bg-gray-800 hover:border-gray-600",
            )}
          >
            <div className="flex items-center gap-3">
              <Server className="h-5 w-5 text-gray-400" />
              <span className="font-medium text-gray-100">
                {agent.label}
              </span>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              {agent.description}
            </p>
          </button>
        ))}
      </div>

      {/* Deploy result */}
      {deployMutation.isSuccess && deployMutation.data && (
        <div className="rounded-lg border border-green-500/20 bg-green-500/10 px-4 py-3 text-sm text-green-400">
          <p className="font-medium">{deployMutation.data.message}</p>
          <p className="mt-1 text-xs text-green-500">
            Agent ID: {deployMutation.data.agent_id}
          </p>
        </div>
      )}

      {deployMutation.isError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to deploy agent. Please try again.
        </div>
      )}

      <button
        onClick={() => {
          if (selectedType) {
            deployMutation.mutate({
              agent_type: selectedType,
              environment: "development",
            });
          }
        }}
        disabled={!selectedType || deployMutation.isPending}
        className={clsx(
          "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors",
          selectedType
            ? "bg-brand-500 text-white hover:bg-brand-600"
            : "cursor-not-allowed bg-gray-800 text-gray-500",
        )}
      >
        {deployMutation.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Bot className="h-4 w-4" />
        )}
        Deploy Agent
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 4 -- Configure Playbook
// ---------------------------------------------------------------------------

function PlaybookStep({
  done,
  onComplete,
  onSkip,
  isPending,
}: {
  done: boolean;
  onComplete: (meta: Record<string, unknown>) => void;
  onSkip: () => void;
  isPending: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  if (done) {
    return <DoneMessage message="Playbook configured." />;
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-400">
        Select a pre-built playbook template to get started, or skip this
        step and configure playbooks later.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {PLAYBOOK_TEMPLATES.map((pb) => (
          <button
            key={pb.id}
            onClick={() => setSelected(pb.id)}
            className={clsx(
              "rounded-xl border p-4 text-left transition-colors",
              selected === pb.id
                ? "border-brand-500 bg-brand-500/10"
                : "border-gray-700 bg-gray-800 hover:border-gray-600",
            )}
          >
            <p className="font-medium text-gray-100">{pb.name}</p>
            <p className="mt-1 text-xs text-gray-500">{pb.description}</p>
            <div className="mt-2 flex gap-1.5">
              {pb.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-400"
                >
                  {tag}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => {
            if (selected) {
              const template = PLAYBOOK_TEMPLATES.find(
                (p) => p.id === selected,
              );
              onComplete({
                playbook_id: selected,
                playbook_name: template?.name ?? selected,
              });
            }
          }}
          disabled={!selected || isPending}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors",
            selected
              ? "bg-brand-500 text-white hover:bg-brand-600"
              : "cursor-not-allowed bg-gray-800 text-gray-500",
          )}
        >
          {isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <BookOpen className="h-4 w-4" />
          )}
          Apply Playbook
        </button>
        <button
          onClick={onSkip}
          disabled={isPending}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-400 hover:bg-gray-700 hover:text-gray-200"
        >
          <SkipForward className="h-4 w-4" />
          Skip for Now
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 5 -- Run Demo
// ---------------------------------------------------------------------------

function DemoStep({ done }: { done: boolean }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const demoMutation = useMutation({
    mutationFn: (data: { scenario: string }) =>
      post<TriggerDemoResponse>("/onboarding/trigger-demo", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", "status"] });
    },
  });

  if (done) {
    return (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-green-400" />
        <h3 className="text-lg font-semibold text-gray-100">
          Setup Complete!
        </h3>
        <p className="text-sm text-gray-400">
          Your ShieldOps platform is ready. Head to the Fleet Overview to
          start monitoring.
        </p>
        <button
          onClick={() => navigate("/", { replace: true })}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-600"
        >
          Go to Fleet Overview
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-400">
        Trigger a demo investigation to see how ShieldOps agents analyze
        alerts, correlate data, and recommend actions.
      </p>

      <div className="rounded-xl border border-gray-700 bg-gray-800 p-4">
        <p className="font-medium text-gray-100">
          Demo Scenario: High CPU Alert
        </p>
        <p className="mt-1 text-xs text-gray-500">
          Simulates a critical CPU spike on a production Kubernetes pod.
          The investigation agent will analyze logs, metrics, and traces to
          identify the root cause and recommend remediation.
        </p>
      </div>

      {demoMutation.isSuccess && demoMutation.data && (
        <div className="rounded-lg border border-green-500/20 bg-green-500/10 px-4 py-3 text-sm text-green-400">
          <p className="font-medium">{demoMutation.data.message}</p>
          <p className="mt-1 text-xs text-green-500">
            Investigation ID: {demoMutation.data.investigation_id}
          </p>
        </div>
      )}

      {demoMutation.isError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to trigger demo. Please try again.
        </div>
      )}

      <button
        onClick={() =>
          demoMutation.mutate({ scenario: "high_cpu_alert" })
        }
        disabled={demoMutation.isPending}
        className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-600"
      >
        {demoMutation.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Play className="h-4 w-4" />
        )}
        Start Demo Investigation
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared done state
// ---------------------------------------------------------------------------

function DoneMessage({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-green-500/20 bg-green-500/10 px-4 py-3">
      <CheckCircle2 className="h-5 w-5 text-green-400" />
      <span className="text-sm text-green-400">{message}</span>
    </div>
  );
}
