import type { BillingPlan, BillingSubscription, BillingUsage } from "../../api/types";

export function getBillingPlans(): BillingPlan[] {
  return [
    {
      key: "free",
      name: "Free",
      agent_limit: 2,
      api_calls_limit: 1000,
      features: ["2 agents", "Basic investigation", "Email alerts", "Community support"],
      has_price: false,
    },
    {
      key: "pro",
      name: "Professional",
      agent_limit: 10,
      api_calls_limit: 50000,
      features: [
        "10 agents",
        "Full investigation + remediation",
        "Multi-cloud support",
        "Slack & PagerDuty integration",
        "OPA policy engine",
        "Priority support",
      ],
      has_price: true,
    },
    {
      key: "enterprise",
      name: "Enterprise",
      agent_limit: -1,
      api_calls_limit: -1,
      features: [
        "Unlimited agents",
        "All agent types",
        "SSO / SAML",
        "Custom playbooks",
        "Dedicated support",
        "SLA guarantee",
        "On-premise deployment",
      ],
      has_price: true,
    },
  ];
}

export function getBillingSubscription(): BillingSubscription {
  return {
    org_id: "demo-org-001",
    plan: "pro",
    plan_name: "Professional",
    agent_limit: 10,
    api_calls_limit: 50000,
    status: "active",
    stripe_subscription_id: null,
    current_period_end: Math.floor(Date.now() / 1000) + 30 * 86400,
    cancel_at_period_end: false,
  };
}

export function getBillingUsage(): BillingUsage {
  return {
    org_id: "demo-org-001",
    plan: "pro",
    agents_used: 6,
    agents_limit: 10,
    agents_percent: 60,
    api_calls_used: 14_832,
    api_calls_limit: 50000,
    api_calls_percent: 29.7,
  };
}
