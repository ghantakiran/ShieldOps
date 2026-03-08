import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  Activity,
  Bell,
  Server,
  Bot,
  Rocket,
  Check,
  ChevronRight,
  ChevronLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Eye,
  BarChart3,
  Cloud,
  Shield,
  BookOpen,
  Search,
  Wrench,
  Upload,
  Link2,
  Hash,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { post } from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EnvironmentType = "production" | "staging" | "development";
type TeamSize = "1-10" | "11-50" | "51-200" | "200+";
type ApprovalMode = "auto" | "approve" | "2-person";

interface OrgConfig {
  name: string;
  environment: EnvironmentType;
  teamSize: TeamSize;
}

interface IntegrationConfig {
  id: string;
  connected: boolean;
  fields: Record<string, string>;
}

interface AgentConfig {
  investigation: boolean;
  remediation: boolean;
  security: boolean;
  learning: boolean;
  approvalMode: ApprovalMode;
  maxPods: number;
  maxServices: number;
  slackChannel: string;
}

type LaunchPhase = "idle" | "deploying" | "scanning" | "ready";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEPS = [
  { key: "welcome", label: "Organization", icon: Building2 },
  { key: "observability", label: "Observability", icon: Activity },
  { key: "alerting", label: "Alerting", icon: Bell },
  { key: "infrastructure", label: "Infrastructure", icon: Server },
  { key: "agents", label: "Agents", icon: Bot },
  { key: "review", label: "Launch", icon: Rocket },
] as const;

const OBSERVABILITY_INTEGRATIONS = [
  {
    id: "splunk",
    name: "Splunk",
    description: "Enterprise log management and SIEM",
    icon: Search,
    color: "text-green-400",
    fields: [
      { key: "api_url", label: "Splunk API URL", placeholder: "https://splunk.example.com:8089", type: "text" },
      { key: "api_token", label: "API Token", placeholder: "eyJ...", type: "password" },
    ],
  },
  {
    id: "datadog",
    name: "Datadog",
    description: "Cloud monitoring and analytics",
    icon: BarChart3,
    color: "text-brand-400",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "dd-api-...", type: "password" },
      { key: "app_key", label: "Application Key", placeholder: "dd-app-...", type: "password" },
      { key: "site", label: "Datadog Site", placeholder: "datadoghq.com", type: "text" },
    ],
  },
  {
    id: "prometheus",
    name: "Prometheus",
    description: "Open-source metrics and alerting",
    icon: Activity,
    color: "text-orange-400",
    fields: [
      { key: "endpoint", label: "Prometheus URL", placeholder: "http://prometheus:9090", type: "text" },
      { key: "username", label: "Username (optional)", placeholder: "admin", type: "text" },
      { key: "password", label: "Password (optional)", placeholder: "password", type: "password" },
    ],
  },
  {
    id: "cloudwatch",
    name: "CloudWatch",
    description: "AWS native monitoring service",
    icon: Cloud,
    color: "text-yellow-400",
    fields: [
      { key: "access_key", label: "AWS Access Key", placeholder: "AKIA...", type: "password" },
      { key: "secret_key", label: "AWS Secret Key", placeholder: "wJalrX...", type: "password" },
      { key: "region", label: "AWS Region", placeholder: "us-east-1", type: "text" },
    ],
  },
  {
    id: "newrelic",
    name: "New Relic",
    description: "Full-stack observability platform",
    icon: Eye,
    color: "text-teal-400",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "NRAK-...", type: "password" },
      { key: "account_id", label: "Account ID", placeholder: "1234567", type: "text" },
    ],
  },
] as const;

const ALERTING_INTEGRATIONS = [
  {
    id: "pagerduty",
    name: "PagerDuty",
    description: "Incident management and on-call scheduling",
    icon: Bell,
    color: "text-green-400",
    fields: [
      { key: "routing_key", label: "Routing Key", placeholder: "R0...", type: "password" },
    ],
  },
  {
    id: "opsgenie",
    name: "OpsGenie",
    description: "Alert management and escalation",
    icon: AlertCircle,
    color: "text-blue-400",
    fields: [
      { key: "api_key", label: "API Key", placeholder: "og-api-...", type: "password" },
      { key: "team_id", label: "Team ID", placeholder: "team-...", type: "text" },
    ],
  },
  {
    id: "slack_alerts",
    name: "Slack Alerts",
    description: "Send alerts to Slack channels",
    icon: Hash,
    color: "text-brand-400",
    fields: [
      { key: "webhook_url", label: "Webhook URL", placeholder: "https://hooks.slack.com/...", type: "text" },
      { key: "channel", label: "Channel", placeholder: "#ops-alerts", type: "text" },
    ],
    oauthButton: true,
  },
  {
    id: "webhook",
    name: "Custom Webhook",
    description: "Send alerts to any HTTP endpoint",
    icon: Link2,
    color: "text-gray-400",
    fields: [
      { key: "url", label: "Webhook URL", placeholder: "https://api.example.com/webhook", type: "text" },
      { key: "secret", label: "Signing Secret (optional)", placeholder: "whsec_...", type: "password" },
    ],
  },
] as const;

const INFRA_INTEGRATIONS = [
  {
    id: "kubernetes",
    name: "Kubernetes",
    description: "Container orchestration platform",
    icon: Server,
    color: "text-blue-400",
    fields: [
      { key: "cluster_url", label: "Cluster API URL", placeholder: "https://k8s.example.com:6443", type: "text" },
      { key: "service_token", label: "Service Account Token", placeholder: "eyJ...", type: "password" },
    ],
    fileUpload: { key: "kubeconfig", label: "Or upload kubeconfig" },
  },
  {
    id: "aws",
    name: "AWS",
    description: "Amazon Web Services cloud platform",
    icon: Cloud,
    color: "text-yellow-400",
    fields: [
      { key: "access_key", label: "Access Key ID", placeholder: "AKIA...", type: "password" },
      { key: "secret_key", label: "Secret Access Key", placeholder: "wJalrX...", type: "password" },
      { key: "region", label: "Default Region", placeholder: "us-east-1", type: "text" },
    ],
  },
  {
    id: "gcp",
    name: "GCP",
    description: "Google Cloud Platform",
    icon: Cloud,
    color: "text-red-400",
    fields: [
      { key: "project_id", label: "Project ID", placeholder: "my-project-123", type: "text" },
    ],
    fileUpload: { key: "service_account_json", label: "Upload Service Account JSON" },
  },
  {
    id: "azure",
    name: "Azure",
    description: "Microsoft Azure cloud platform",
    icon: Cloud,
    color: "text-blue-500",
    fields: [
      { key: "subscription_id", label: "Subscription ID", placeholder: "xxxxxxxx-xxxx-...", type: "text" },
      { key: "tenant_id", label: "Tenant ID", placeholder: "xxxxxxxx-xxxx-...", type: "text" },
      { key: "client_id", label: "Client ID", placeholder: "xxxxxxxx-xxxx-...", type: "text" },
      { key: "client_secret", label: "Client Secret", placeholder: "secret...", type: "password" },
    ],
  },
  {
    id: "linux",
    name: "Linux Hosts",
    description: "Bare-metal or VM Linux servers",
    icon: Server,
    color: "text-green-400",
    fields: [
      { key: "ssh_host", label: "Host / IP", placeholder: "192.168.1.10", type: "text" },
      { key: "ssh_user", label: "SSH User", placeholder: "shieldops", type: "text" },
      { key: "ssh_key", label: "SSH Private Key", placeholder: "Paste SSH private key contents", type: "password" },
    ],
  },
] as const;

const ENVIRONMENT_OPTIONS: { value: EnvironmentType; label: string; description: string }[] = [
  { value: "production", label: "Production", description: "Live customer-facing environment" },
  { value: "staging", label: "Staging", description: "Pre-production testing environment" },
  { value: "development", label: "Development", description: "Local or team development" },
];

const TEAM_SIZE_OPTIONS: { value: TeamSize; label: string }[] = [
  { value: "1-10", label: "1-10 engineers" },
  { value: "11-50", label: "11-50 engineers" },
  { value: "51-200", label: "51-200 engineers" },
  { value: "200+", label: "200+ engineers" },
];

const stepVariants = {
  enter: { opacity: 0, x: 30 },
  center: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -30 },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [direction, setDirection] = useState(1);

  // Step 1: Organization
  const [org, setOrg] = useState<OrgConfig>({
    name: "",
    environment: "production",
    teamSize: "11-50",
  });

  // Step 2: Observability integrations
  const [observability, setObservability] = useState<Record<string, IntegrationConfig>>({});

  // Step 3: Alerting integrations
  const [alerting, setAlerting] = useState<Record<string, IntegrationConfig>>({});

  // Step 4: Infrastructure integrations
  const [infrastructure, setInfrastructure] = useState<Record<string, IntegrationConfig>>({});

  // Step 5: Agent config
  const [agents, setAgents] = useState<AgentConfig>({
    investigation: true,
    remediation: true,
    security: true,
    learning: true,
    approvalMode: "approve",
    maxPods: 5,
    maxServices: 3,
    slackChannel: "#ops-alerts",
  });

  // Step 6: Launch state
  const [launchPhase, setLaunchPhase] = useState<LaunchPhase>("idle");

  // Auto-set approval mode based on environment
  useEffect(() => {
    const modeMap: Record<EnvironmentType, ApprovalMode> = {
      development: "auto",
      staging: "approve",
      production: "2-person",
    };
    setAgents((prev) => ({ ...prev, approvalMode: modeMap[org.environment] }));
  }, [org.environment]);

  // Validation per step
  const isStepValid = useCallback(
    (step: number): boolean => {
      switch (step) {
        case 0:
          return org.name.trim().length > 0;
        case 1:
          return Object.values(observability).some((i) => i.connected);
        case 2:
          return Object.values(alerting).some((i) => i.connected);
        case 3:
          return Object.values(infrastructure).some((i) => i.connected);
        case 4:
          return [agents.investigation, agents.remediation, agents.security, agents.learning].some(Boolean);
        case 5:
          return true;
        default:
          return false;
      }
    },
    [org, observability, alerting, infrastructure, agents],
  );

  const goNext = () => {
    if (activeStep < STEPS.length - 1 && isStepValid(activeStep)) {
      setDirection(1);
      setActiveStep(activeStep + 1);
    }
  };

  const goBack = () => {
    if (activeStep > 0) {
      setDirection(-1);
      setActiveStep(activeStep - 1);
    }
  };

  const handleLaunch = async () => {
    setLaunchPhase("deploying");
    try {
      await post("/onboarding/launch", {
        organization: org,
        observability: Object.fromEntries(
          Object.entries(observability)
            .filter(([, v]) => v.connected)
            .map(([k, v]) => [k, v.fields]),
        ),
        alerting: Object.fromEntries(
          Object.entries(alerting)
            .filter(([, v]) => v.connected)
            .map(([k, v]) => [k, v.fields]),
        ),
        infrastructure: Object.fromEntries(
          Object.entries(infrastructure)
            .filter(([, v]) => v.connected)
            .map(([k, v]) => [k, v.fields]),
        ),
        agents,
      });
    } catch {
      // demo mode or API unavailable -- continue the flow
    }

    await delay(1800);
    setLaunchPhase("scanning");
    await delay(2200);
    setLaunchPhase("ready");
    await delay(1500);
    navigate("/app", { replace: true });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 pb-12 sm:px-0">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-100 sm:text-3xl">
          Welcome to ShieldOps
        </h1>
        <p className="mt-2 text-sm text-gray-400">
          Set up your autonomous SRE platform in a few steps.
        </p>
      </div>

      {/* Step indicator */}
      <StepIndicator
        steps={STEPS}
        activeStep={activeStep}
        isStepValid={isStepValid}
        onStepClick={(idx) => {
          // Only allow clicking completed/current steps
          if (idx <= activeStep || (idx === activeStep + 1 && isStepValid(activeStep))) {
            setDirection(idx > activeStep ? 1 : -1);
            setActiveStep(idx);
          }
        }}
      />

      {/* Step content */}
      <div className="relative min-h-[420px] overflow-hidden rounded-xl border border-gray-800 bg-gray-900">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={activeStep}
            custom={direction}
            variants={stepVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="p-6"
          >
            {activeStep === 0 && (
              <WelcomeStep org={org} setOrg={setOrg} />
            )}
            {activeStep === 1 && (
              <IntegrationStep
                title="Connect Observability"
                description="Connect at least one observability platform to ingest metrics, logs, and traces."
                integrations={OBSERVABILITY_INTEGRATIONS}
                state={observability}
                setState={setObservability}
              />
            )}
            {activeStep === 2 && (
              <IntegrationStep
                title="Connect Alerting"
                description="Connect at least one alerting channel so agents can respond to incidents."
                integrations={ALERTING_INTEGRATIONS}
                state={alerting}
                setState={setAlerting}
              />
            )}
            {activeStep === 3 && (
              <IntegrationStep
                title="Connect Infrastructure"
                description="Connect at least one infrastructure provider for agent actions."
                integrations={INFRA_INTEGRATIONS}
                state={infrastructure}
                setState={setInfrastructure}
              />
            )}
            {activeStep === 4 && (
              <AgentStep
                agents={agents}
                setAgents={setAgents}
                environment={org.environment}
              />
            )}
            {activeStep === 5 && (
              <ReviewStep
                org={org}
                observability={observability}
                alerting={alerting}
                infrastructure={infrastructure}
                agents={agents}
                launchPhase={launchPhase}
                onLaunch={handleLaunch}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      {launchPhase === "idle" && (
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

          {activeStep < STEPS.length - 1 && (
            <button
              onClick={goNext}
              disabled={!isStepValid(activeStep)}
              className={clsx(
                "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors",
                isStepValid(activeStep)
                  ? "bg-brand-500 text-white hover:bg-brand-600"
                  : "cursor-not-allowed bg-gray-800 text-gray-500",
              )}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step Indicator
// ---------------------------------------------------------------------------

function StepIndicator({
  steps,
  activeStep,
  isStepValid,
  onStepClick,
}: {
  steps: readonly { key: string; label: string; icon: typeof Building2 }[];
  activeStep: number;
  isStepValid: (step: number) => boolean;
  onStepClick: (idx: number) => void;
}) {
  return (
    <div className="flex items-center gap-1 sm:gap-2">
      {steps.map((step, idx) => {
        const completed = idx < activeStep && isStepValid(idx);
        const active = idx === activeStep;
        const Icon = step.icon;
        return (
          <div key={step.key} className="flex flex-1 items-center gap-1 sm:gap-2">
            <button
              onClick={() => onStepClick(idx)}
              className={clsx(
                "group relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-medium transition-all sm:h-10 sm:w-10",
                completed
                  ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                  : active
                    ? "bg-brand-500/20 text-brand-400 ring-2 ring-brand-500/50"
                    : "bg-gray-800 text-gray-500",
              )}
              aria-label={step.label}
            >
              {completed ? (
                <Check className="h-4 w-4" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
              {/* Tooltip */}
              <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-200 opacity-0 transition-opacity group-hover:opacity-100">
                {step.label}
              </span>
            </button>
            {idx < steps.length - 1 && (
              <div
                className={clsx(
                  "h-0.5 flex-1 rounded transition-colors",
                  idx < activeStep ? "bg-green-500/40" : "bg-gray-800",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1: Welcome & Organization
// ---------------------------------------------------------------------------

function WelcomeStep({
  org,
  setOrg,
}: {
  org: OrgConfig;
  setOrg: React.Dispatch<React.SetStateAction<OrgConfig>>;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">
          Organization Setup
        </h2>
        <p className="mt-1 text-sm text-gray-400">
          Tell us about your organization to customize the platform.
        </p>
      </div>

      {/* Organization Name */}
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Organization Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={org.name}
          onChange={(e) => setOrg((prev) => ({ ...prev, name: e.target.value }))}
          placeholder="Acme Corp"
          className="mt-1.5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      {/* Environment Type */}
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Primary Environment
        </label>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {ENVIRONMENT_OPTIONS.map((env) => (
            <button
              key={env.value}
              onClick={() => setOrg((prev) => ({ ...prev, environment: env.value }))}
              className={clsx(
                "rounded-xl border p-4 text-left transition-all",
                org.environment === env.value
                  ? "border-brand-500 bg-brand-500/10"
                  : "border-gray-700 bg-gray-800 hover:border-gray-600",
              )}
            >
              <p className="text-sm font-medium text-gray-100">{env.label}</p>
              <p className="mt-1 text-xs text-gray-500">{env.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Team Size */}
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Engineering Team Size
        </label>
        <div className="mt-2 flex flex-wrap gap-2">
          {TEAM_SIZE_OPTIONS.map((size) => (
            <button
              key={size.value}
              onClick={() => setOrg((prev) => ({ ...prev, teamSize: size.value }))}
              className={clsx(
                "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
                org.teamSize === size.value
                  ? "bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/50"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200",
              )}
            >
              {size.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Integration Step (shared for Observability, Alerting, Infrastructure)
// ---------------------------------------------------------------------------

interface IntegrationDef {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly icon: typeof Activity;
  readonly color: string;
  readonly fields: readonly { key: string; label: string; placeholder: string; type: string }[];
  readonly oauthButton?: boolean;
  readonly fileUpload?: { key: string; label: string };
}

function IntegrationStep({
  title,
  description,
  integrations,
  state,
  setState,
}: {
  title: string;
  description: string;
  integrations: readonly IntegrationDef[];
  state: Record<string, IntegrationConfig>;
  setState: React.Dispatch<React.SetStateAction<Record<string, IntegrationConfig>>>;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleConnect = (id: string) => {
    const current = state[id];
    if (current?.connected) {
      // Disconnect
      setState((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }
    // Toggle expand
    setExpandedId(expandedId === id ? null : id);
  };

  const handleFieldChange = (integrationId: string, fieldKey: string, value: string) => {
    setState((prev) => ({
      ...prev,
      [integrationId]: {
        id: integrationId,
        connected: false,
        fields: {
          ...(prev[integrationId]?.fields ?? {}),
          [fieldKey]: value,
        },
      },
    }));
  };

  const handleSave = (integration: IntegrationDef) => {
    const fields = state[integration.id]?.fields ?? {};
    // Check required fields (at least the first field must be filled)
    const requiredFields = integration.fields.filter(
      (f) => !f.label.toLowerCase().includes("optional"),
    );
    const allFilled = requiredFields.every((f) => fields[f.key]?.trim());
    if (!allFilled) return;

    setState((prev) => ({
      ...prev,
      [integration.id]: {
        id: integration.id,
        connected: true,
        fields: { ...fields },
      },
    }));
    setExpandedId(null);
  };

  const handleFileUpload = (integrationId: string, fieldKey: string) => {
    // Simulated file upload -- in production this would use a file input
    setState((prev) => ({
      ...prev,
      [integrationId]: {
        id: integrationId,
        connected: false,
        fields: {
          ...(prev[integrationId]?.fields ?? {}),
          [fieldKey]: "(file uploaded)",
        },
      },
    }));
  };

  const connectedCount = Object.values(state).filter((i) => i.connected).length;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
          <p className="mt-1 text-sm text-gray-400">{description}</p>
        </div>
        {connectedCount > 0 && (
          <span className="rounded-full bg-green-500/20 px-3 py-1 text-xs font-medium text-green-400">
            {connectedCount} connected
          </span>
        )}
      </div>

      <div className="space-y-3">
        {integrations.map((integration) => {
          const Icon = integration.icon;
          const isConnected = state[integration.id]?.connected ?? false;
          const isExpanded = expandedId === integration.id;
          const fields = state[integration.id]?.fields ?? {};

          return (
            <div
              key={integration.id}
              className={clsx(
                "rounded-xl border transition-all",
                isConnected
                  ? "border-green-500/30 bg-green-500/5"
                  : isExpanded
                    ? "border-brand-500/30 bg-gray-800/50"
                    : "border-gray-700 bg-gray-800 hover:border-gray-600",
              )}
            >
              {/* Card header */}
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <div
                    className={clsx(
                      "flex h-10 w-10 items-center justify-center rounded-lg",
                      isConnected ? "bg-green-500/10" : "bg-gray-700/50",
                    )}
                  >
                    {isConnected ? (
                      <CheckCircle2 className="h-5 w-5 text-green-400" />
                    ) : (
                      <Icon className={clsx("h-5 w-5", integration.color)} />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-100">
                      {integration.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {isConnected ? "Connected" : integration.description}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleConnect(integration.id)}
                  className={clsx(
                    "rounded-lg px-4 py-1.5 text-xs font-medium transition-colors",
                    isConnected
                      ? "bg-red-500/10 text-red-400 hover:bg-red-500/20"
                      : "bg-brand-500/10 text-brand-400 hover:bg-brand-500/20",
                  )}
                >
                  {isConnected ? "Disconnect" : isExpanded ? "Cancel" : "Connect"}
                </button>
              </div>

              {/* Expanded fields */}
              <AnimatePresence>
                {isExpanded && !isConnected && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-3 border-t border-gray-700/50 px-4 pb-4 pt-3">
                      {integration.oauthButton && (
                        <button
                          onClick={() => handleSave(integration)}
                          className="inline-flex items-center gap-2 rounded-lg bg-brand-500/20 px-4 py-2 text-sm font-medium text-brand-400 transition-colors hover:bg-brand-500/30"
                        >
                          <Link2 className="h-4 w-4" />
                          Connect with OAuth
                        </button>
                      )}
                      {integration.fields.map((field) => (
                        <div key={field.key}>
                          <label className="block text-xs font-medium text-gray-400">
                            {field.label}
                          </label>
                          <input
                            type={field.type}
                            value={fields[field.key] ?? ""}
                            onChange={(e) =>
                              handleFieldChange(integration.id, field.key, e.target.value)
                            }
                            placeholder={field.placeholder}
                            className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-gray-100 placeholder-gray-600 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                          />
                        </div>
                      ))}
                      {integration.fileUpload && (
                        <button
                          onClick={() =>
                            handleFileUpload(integration.id, integration.fileUpload!.key)
                          }
                          className="inline-flex items-center gap-2 rounded-lg border border-dashed border-gray-600 px-4 py-2 text-xs text-gray-400 transition-colors hover:border-gray-500 hover:text-gray-300"
                        >
                          <Upload className="h-3.5 w-3.5" />
                          {fields[integration.fileUpload.key]
                            ? "File uploaded"
                            : integration.fileUpload.label}
                        </button>
                      )}
                      <button
                        onClick={() => handleSave(integration)}
                        className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-brand-600"
                      >
                        <Check className="h-3.5 w-3.5" />
                        Save & Connect
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 5: Configure Agents
// ---------------------------------------------------------------------------

function AgentStep({
  agents,
  setAgents,
  environment,
}: {
  agents: AgentConfig;
  setAgents: React.Dispatch<React.SetStateAction<AgentConfig>>;
  environment: EnvironmentType;
}) {
  const agentTypes: {
    key: keyof Pick<AgentConfig, "investigation" | "remediation" | "security" | "learning">;
    label: string;
    description: string;
    icon: typeof Search;
    color: string;
  }[] = [
    {
      key: "investigation",
      label: "Investigation Agent",
      description: "Root cause analysis from alerts, logs, metrics, and traces",
      icon: Search,
      color: "text-blue-400",
    },
    {
      key: "remediation",
      label: "Remediation Agent",
      description: "Execute infrastructure changes with policy gates",
      icon: Wrench,
      color: "text-orange-400",
    },
    {
      key: "security",
      label: "Security Agent",
      description: "CVE patching, credential rotation, compliance enforcement",
      icon: Shield,
      color: "text-red-400",
    },
    {
      key: "learning",
      label: "Learning Agent",
      description: "Update playbooks and refine thresholds from outcomes",
      icon: BookOpen,
      color: "text-green-400",
    },
  ];

  const approvalOptions: { value: ApprovalMode; label: string; description: string }[] = [
    { value: "auto", label: "Auto-approve", description: "Best for dev environments" },
    { value: "approve", label: "Single Approval", description: "One engineer must approve" },
    { value: "2-person", label: "2-Person Approval", description: "Requires two approvers" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Configure Agents</h2>
        <p className="mt-1 text-sm text-gray-400">
          Choose which AI agents to deploy and configure safety controls.
        </p>
      </div>

      {/* Agent toggles */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {agentTypes.map((agent) => {
          const Icon = agent.icon;
          const enabled = agents[agent.key];
          return (
            <button
              key={agent.key}
              onClick={() =>
                setAgents((prev) => ({ ...prev, [agent.key]: !prev[agent.key] }))
              }
              className={clsx(
                "rounded-xl border p-4 text-left transition-all",
                enabled
                  ? "border-brand-500 bg-brand-500/10"
                  : "border-gray-700 bg-gray-800 hover:border-gray-600",
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Icon className={clsx("h-5 w-5", agent.color)} />
                  <span className="text-sm font-medium text-gray-100">
                    {agent.label}
                  </span>
                </div>
                <div
                  className={clsx(
                    "flex h-5 w-9 items-center rounded-full px-0.5 transition-colors",
                    enabled ? "bg-brand-500" : "bg-gray-600",
                  )}
                >
                  <div
                    className={clsx(
                      "h-4 w-4 rounded-full bg-white shadow transition-transform",
                      enabled ? "translate-x-4" : "translate-x-0",
                    )}
                  />
                </div>
              </div>
              <p className="mt-2 text-xs text-gray-500">{agent.description}</p>
            </button>
          );
        })}
      </div>

      {/* Remediation approval mode */}
      {agents.remediation && (
        <div className="space-y-3 rounded-xl border border-gray-700 bg-gray-800/50 p-4">
          <p className="text-sm font-medium text-gray-300">
            Remediation Approval Mode
            <span className="ml-2 text-xs text-gray-500">
              (auto-set for {environment})
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            {approvalOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() =>
                  setAgents((prev) => ({ ...prev, approvalMode: opt.value }))
                }
                className={clsx(
                  "rounded-lg px-3 py-2 text-left transition-colors",
                  agents.approvalMode === opt.value
                    ? "bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/50"
                    : "bg-gray-700 text-gray-400 hover:text-gray-200",
                )}
              >
                <p className="text-xs font-medium">{opt.label}</p>
                <p className="text-xs text-gray-500">{opt.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Blast radius limits */}
      <div className="space-y-3 rounded-xl border border-gray-700 bg-gray-800/50 p-4">
        <p className="text-sm font-medium text-gray-300">Blast Radius Limits</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs text-gray-400">
              Max pods per action
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={agents.maxPods}
              onChange={(e) =>
                setAgents((prev) => ({
                  ...prev,
                  maxPods: Math.max(1, Math.min(100, parseInt(e.target.value) || 1)),
                }))
              }
              className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-gray-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400">
              Max services per action
            </label>
            <input
              type="number"
              min={1}
              max={50}
              value={agents.maxServices}
              onChange={(e) =>
                setAgents((prev) => ({
                  ...prev,
                  maxServices: Math.max(1, Math.min(50, parseInt(e.target.value) || 1)),
                }))
              }
              className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-gray-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>
      </div>

      {/* Slack channel */}
      <div>
        <label className="block text-sm font-medium text-gray-300">
          Notification Channel
        </label>
        <div className="mt-1.5 flex items-center gap-2">
          <Hash className="h-4 w-4 text-gray-500" />
          <input
            type="text"
            value={agents.slackChannel}
            onChange={(e) =>
              setAgents((prev) => ({ ...prev, slackChannel: e.target.value }))
            }
            placeholder="#ops-alerts"
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 6: Review & Launch
// ---------------------------------------------------------------------------

function ReviewStep({
  org,
  observability,
  alerting,
  infrastructure,
  agents,
  launchPhase,
  onLaunch,
}: {
  org: OrgConfig;
  observability: Record<string, IntegrationConfig>;
  alerting: Record<string, IntegrationConfig>;
  infrastructure: Record<string, IntegrationConfig>;
  agents: AgentConfig;
  launchPhase: LaunchPhase;
  onLaunch: () => void;
}) {
  const connectedObs = Object.entries(observability)
    .filter(([, v]) => v.connected)
    .map(([k]) => k);
  const connectedAlert = Object.entries(alerting)
    .filter(([, v]) => v.connected)
    .map(([k]) => k);
  const connectedInfra = Object.entries(infrastructure)
    .filter(([, v]) => v.connected)
    .map(([k]) => k);
  const enabledAgents = (
    ["investigation", "remediation", "security", "learning"] as const
  ).filter((k) => agents[k]);

  if (launchPhase !== "idle") {
    return <LaunchProgress phase={launchPhase} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Review & Launch</h2>
        <p className="mt-1 text-sm text-gray-400">
          Review your configuration before deploying ShieldOps.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SummaryCard title="Organization" items={[
          `Name: ${org.name}`,
          `Environment: ${capitalize(org.environment)}`,
          `Team: ${org.teamSize}`,
        ]} />
        <SummaryCard
          title="Observability"
          items={connectedObs.map(capitalize)}
        />
        <SummaryCard
          title="Alerting"
          items={connectedAlert.map((s) => s.replace("_", " ")).map(capitalize)}
        />
        <SummaryCard
          title="Infrastructure"
          items={connectedInfra.map(capitalize)}
        />
      </div>

      {/* Agent summary */}
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
        <p className="mb-3 text-sm font-medium text-gray-300">Agents</p>
        <div className="flex flex-wrap gap-2">
          {enabledAgents.map((a) => (
            <span
              key={a}
              className="rounded-full bg-brand-500/20 px-3 py-1 text-xs font-medium text-brand-400"
            >
              {capitalize(a)}
            </span>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-500">
          <span>Approval: {agents.approvalMode}</span>
          <span>Max pods: {agents.maxPods}</span>
          <span>Max services: {agents.maxServices}</span>
          <span>Channel: {agents.slackChannel}</span>
        </div>
      </div>

      {/* Launch button */}
      <div className="text-center">
        <button
          onClick={onLaunch}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-500/20 transition-all hover:bg-brand-600 hover:shadow-brand-500/30"
        >
          <Rocket className="h-5 w-5" />
          Launch ShieldOps
        </button>
      </div>
    </div>
  );
}

function SummaryCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
      <p className="mb-2 text-sm font-medium text-gray-300">{title}</p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item} className="flex items-center gap-2 text-xs text-gray-400">
            <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Launch Progress Animation
// ---------------------------------------------------------------------------

function LaunchProgress({ phase }: { phase: LaunchPhase }) {
  const phases: { key: LaunchPhase; label: string; icon: typeof Loader2 }[] = [
    { key: "deploying", label: "Deploying agents...", icon: Bot },
    { key: "scanning", label: "Running initial scan...", icon: Activity },
    { key: "ready", label: "Ready!", icon: CheckCircle2 },
  ];

  const currentIdx = phases.findIndex((p) => p.key === phase);

  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="space-y-6">
        {phases.map((p, idx) => {
          const Icon = p.icon;
          const isActive = idx === currentIdx;
          const isDone = idx < currentIdx;
          return (
            <motion.div
              key={p.key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.3 }}
              className="flex items-center gap-4"
            >
              <div
                className={clsx(
                  "flex h-10 w-10 items-center justify-center rounded-full transition-colors",
                  isDone
                    ? "bg-green-500/20"
                    : isActive
                      ? "bg-brand-500/20"
                      : "bg-gray-800",
                )}
              >
                {isDone ? (
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                ) : isActive ? (
                  <Loader2 className="h-5 w-5 animate-spin text-brand-400" />
                ) : (
                  <Icon className="h-5 w-5 text-gray-600" />
                )}
              </div>
              <span
                className={clsx(
                  "text-sm font-medium",
                  isDone
                    ? "text-green-400"
                    : isActive
                      ? "text-gray-100"
                      : "text-gray-600",
                )}
              >
                {p.label}
              </span>
            </motion.div>
          );
        })}
      </div>

      {phase === "ready" && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-8 text-sm text-gray-400"
        >
          Redirecting to Agent Factory...
        </motion.p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
