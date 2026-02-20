import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CreditCard,
  Check,
  Zap,
  Building2,
  Users,
  Globe,
  ArrowUpRight,
} from "lucide-react";
import clsx from "clsx";
import { get, post, ApiError } from "../api/client";
import type {
  BillingPlan,
  BillingSubscription,
  BillingUsage,
  CheckoutResponse,
} from "../api/types";
import LoadingSpinner from "../components/LoadingSpinner";

// ── Plan icon mapping ─────────────────────────────────────────────────

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: <Users className="h-6 w-6" />,
  pro: <Zap className="h-6 w-6" />,
  enterprise: <Building2 className="h-6 w-6" />,
};

const PLAN_COLORS: Record<string, string> = {
  free: "border-gray-700",
  pro: "border-brand-500 ring-1 ring-brand-500/30",
  enterprise: "border-amber-500 ring-1 ring-amber-500/30",
};

// ── Progress bar component ────────────────────────────────────────────

function UsageMeter({
  label,
  used,
  limit,
  percent,
}: {
  label: string;
  used: number;
  limit: number;
  percent: number;
}) {
  const isUnlimited = limit < 0;
  const displayLimit = isUnlimited ? "Unlimited" : limit.toLocaleString();
  const barPercent = isUnlimited ? 0 : Math.min(percent, 100);
  const barColor =
    barPercent > 90
      ? "bg-red-500"
      : barPercent > 70
        ? "bg-yellow-500"
        : "bg-brand-500";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-gray-300">{label}</span>
        <span className="tabular-nums text-gray-400">
          {used.toLocaleString()} / {displayLimit}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-800">
        {!isUnlimited && (
          <div
            className={clsx("h-full rounded-full transition-all", barColor)}
            style={{ width: `${barPercent}%` }}
          />
        )}
        {isUnlimited && (
          <div className="h-full w-full rounded-full bg-brand-500/30" />
        )}
      </div>
      {!isUnlimited && percent > 80 && (
        <p className="mt-1 text-xs text-yellow-400">
          {percent > 100 ? "Limit exceeded" : "Approaching limit"}
        </p>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────

export default function Billing() {
  const queryClient = useQueryClient();

  // Fetch plans
  const { data: plansData, isLoading: plansLoading } = useQuery<{
    plans: BillingPlan[];
  }>({
    queryKey: ["billing", "plans"],
    queryFn: () => get("/billing/plans"),
    retry: (count, err) => {
      if (err instanceof ApiError && err.status === 503) return false;
      return count < 2;
    },
  });

  // Fetch current subscription
  const { data: subscription, isLoading: subLoading } =
    useQuery<BillingSubscription>({
      queryKey: ["billing", "subscription"],
      queryFn: () => get("/billing/subscription"),
      retry: (count, err) => {
        if (err instanceof ApiError && err.status === 503) return false;
        return count < 2;
      },
    });

  // Fetch usage
  const { data: usage, isLoading: usageLoading } = useQuery<BillingUsage>({
    queryKey: ["billing", "usage"],
    queryFn: () => get("/billing/usage"),
    retry: (count, err) => {
      if (err instanceof ApiError && err.status === 503) return false;
      return count < 2;
    },
  });

  // Checkout mutation
  const checkoutMutation = useMutation<CheckoutResponse, ApiError, string>({
    mutationFn: (plan: string) =>
      post<CheckoutResponse>("/billing/checkout", { plan }),
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url;
      }
    },
  });

  // Cancel mutation
  const cancelMutation = useMutation<unknown, ApiError>({
    mutationFn: () => post("/billing/cancel", { reason: "" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing"] });
    },
  });

  const isLoading = plansLoading || subLoading || usageLoading;

  if (isLoading) {
    return <LoadingSpinner size="lg" className="mt-32" />;
  }

  const plans = plansData?.plans ?? [];
  const currentPlan = subscription?.plan ?? "free";

  // Format renewal date
  const renewalDate = subscription?.current_period_end
    ? new Date(subscription.current_period_end * 1000).toLocaleDateString(
        "en-US",
        { year: "numeric", month: "long", day: "numeric" },
      )
    : null;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">
          Billing & Subscription
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Manage your subscription plan and monitor usage
        </p>
      </div>

      {/* Current Plan Summary */}
      <section className="rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-gray-400">Current Plan</p>
            <p className="mt-1 text-2xl font-bold text-gray-100">
              {subscription?.plan_name ?? "Free"}
            </p>
            {renewalDate && (
              <p className="mt-1 text-sm text-gray-500">
                {subscription?.cancel_at_period_end
                  ? `Cancels on ${renewalDate}`
                  : `Renews on ${renewalDate}`}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span
              className={clsx(
                "rounded-full px-3 py-1 text-xs font-medium",
                subscription?.status === "active"
                  ? "bg-green-500/10 text-green-400"
                  : "bg-yellow-500/10 text-yellow-400",
              )}
            >
              {subscription?.status ?? "active"}
            </span>
            {subscription?.stripe_subscription_id &&
              !subscription?.cancel_at_period_end && (
                <button
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                  className="rounded-lg border border-red-800 px-3 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-900/20 disabled:opacity-50"
                >
                  {cancelMutation.isPending ? "Cancelling..." : "Cancel Plan"}
                </button>
              )}
          </div>
        </div>
      </section>

      {/* Usage Meters */}
      {usage && (
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-5 text-lg font-semibold text-gray-100">
            Current Usage
          </h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <UsageMeter
              label="Agents"
              used={usage.agents_used}
              limit={usage.agents_limit}
              percent={usage.agents_percent}
            />
            <UsageMeter
              label="API Calls"
              used={usage.api_calls_used}
              limit={usage.api_calls_limit}
              percent={usage.api_calls_percent}
            />
          </div>
        </section>
      )}

      {/* Plan Comparison Cards */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-100">
          Available Plans
        </h2>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {plans.map((plan) => {
            const isCurrent = plan.key === currentPlan;
            const isUpgrade =
              !isCurrent &&
              plan.has_price &&
              (currentPlan === "free" ||
                (currentPlan === "pro" && plan.key === "enterprise"));
            const isDowngrade =
              !isCurrent &&
              !isUpgrade &&
              plan.key !== currentPlan;

            return (
              <div
                key={plan.key}
                className={clsx(
                  "relative flex flex-col rounded-xl border bg-gray-900 p-6",
                  isCurrent
                    ? PLAN_COLORS[plan.key] ?? "border-brand-500"
                    : "border-gray-800",
                )}
              >
                {isCurrent && (
                  <span className="absolute -top-3 left-4 rounded-full bg-brand-600 px-3 py-0.5 text-xs font-medium text-white">
                    Current Plan
                  </span>
                )}

                <div className="mb-4 flex items-center gap-3">
                  <div
                    className={clsx(
                      "rounded-lg p-2",
                      isCurrent
                        ? "bg-brand-500/20 text-brand-400"
                        : "bg-gray-800 text-gray-400",
                    )}
                  >
                    {PLAN_ICONS[plan.key] ?? (
                      <Globe className="h-6 w-6" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-100">
                      {plan.name}
                    </h3>
                    <p className="text-xs text-gray-500">
                      {plan.agent_limit < 0
                        ? "Unlimited"
                        : plan.agent_limit}{" "}
                      agents |{" "}
                      {plan.api_calls_limit < 0
                        ? "Unlimited"
                        : plan.api_calls_limit.toLocaleString()}{" "}
                      API calls
                    </p>
                  </div>
                </div>

                <ul className="mb-6 flex-1 space-y-2">
                  {plan.features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-2 text-sm text-gray-300"
                    >
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-400" />
                      {feature}
                    </li>
                  ))}
                </ul>

                {isCurrent ? (
                  <div className="rounded-lg bg-gray-800 px-4 py-2.5 text-center text-sm font-medium text-gray-400">
                    Your current plan
                  </div>
                ) : isUpgrade ? (
                  <button
                    onClick={() => checkoutMutation.mutate(plan.key)}
                    disabled={checkoutMutation.isPending}
                    className="flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
                  >
                    <ArrowUpRight className="h-4 w-4" />
                    {checkoutMutation.isPending
                      ? "Redirecting..."
                      : `Upgrade to ${plan.name}`}
                  </button>
                ) : isDowngrade && plan.key === "free" ? (
                  <div className="rounded-lg border border-gray-700 px-4 py-2.5 text-center text-sm font-medium text-gray-500">
                    Cancel to downgrade
                  </div>
                ) : (
                  <button
                    onClick={() => checkoutMutation.mutate(plan.key)}
                    disabled={checkoutMutation.isPending || !plan.has_price}
                    className="rounded-lg border border-gray-700 px-4 py-2.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 disabled:opacity-50"
                  >
                    {plan.has_price ? "Select Plan" : "Contact Sales"}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {checkoutMutation.isError && (
          <p className="mt-3 text-sm text-red-400">
            {checkoutMutation.error?.message ?? "Failed to create checkout session"}
          </p>
        )}
      </section>

      {/* Billing History (placeholder) */}
      <section className="rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center gap-2">
          <CreditCard className="h-5 w-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-100">
            Billing History
          </h2>
        </div>
        <div className="mt-6 flex flex-col items-center py-8 text-center">
          <CreditCard className="h-10 w-10 text-gray-700" />
          <p className="mt-3 text-sm text-gray-500">
            No billing history yet. Your invoices will appear here after your
            first payment.
          </p>
        </div>
      </section>
    </div>
  );
}
