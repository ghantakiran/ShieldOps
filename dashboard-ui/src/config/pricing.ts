export interface PricingTier {
  name: string;
  description: string;
  monthlyPrice: number | null; // null = "Contact us"
  annualPrice: number | null;
  features: string[];
  highlighted?: boolean;
  cta: string;
}

export interface ProductPricing {
  productName: string;
  tiers: PricingTier[];
}

export const PRICING: ProductPricing[] = [
  {
    productName: "SRE Intelligence",
    tiers: [
      {
        name: "Starter",
        description: "For small teams getting started with AI-driven SRE",
        monthlyPrice: 499,
        annualPrice: 399,
        features: [
          "Up to 50 services monitored",
          "5 AI investigation agents",
          "Basic auto-remediation",
          "Email notifications",
          "7-day data retention",
        ],
        cta: "Start Free Trial",
      },
      {
        name: "Pro",
        description: "For growing teams managing production at scale",
        monthlyPrice: 1499,
        annualPrice: 1199,
        features: [
          "Up to 500 services monitored",
          "Unlimited AI agents",
          "Advanced auto-remediation",
          "PagerDuty + Slack integration",
          "30-day data retention",
          "Predictive analytics",
          "Custom playbooks",
        ],
        highlighted: true,
        cta: "Start Free Trial",
      },
      {
        name: "Enterprise",
        description: "For large organizations with complex requirements",
        monthlyPrice: null,
        annualPrice: null,
        features: [
          "Unlimited services",
          "Unlimited AI agents",
          "Multi-cloud + on-prem",
          "SSO / SAML",
          "90-day data retention",
          "Dedicated support",
          "Custom integrations",
          "SLA guarantee",
        ],
        cta: "Contact Sales",
      },
    ],
  },
  {
    productName: "Security Operations",
    tiers: [
      {
        name: "Starter",
        description: "Essential security monitoring and alerting",
        monthlyPrice: 599,
        annualPrice: 479,
        features: [
          "Vulnerability scanning",
          "Basic threat detection",
          "Security dashboards",
          "Email alerts",
          "5 playbooks",
        ],
        cta: "Start Free Trial",
      },
      {
        name: "Pro",
        description: "Advanced threat hunting and response",
        monthlyPrice: 1799,
        annualPrice: 1439,
        features: [
          "Advanced threat hunting",
          "MITRE ATT&CK mapping",
          "Incident correlation",
          "Unlimited playbooks",
          "SIEM integration",
          "Attack surface monitoring",
        ],
        highlighted: true,
        cta: "Start Free Trial",
      },
      {
        name: "Enterprise",
        description: "Full SOC automation for large teams",
        monthlyPrice: null,
        annualPrice: null,
        features: [
          "Everything in Pro",
          "Autonomous SOC agents",
          "Forensics capabilities",
          "Deception technology",
          "Custom detection rules",
          "24/7 threat monitoring",
          "Compliance mapping",
        ],
        cta: "Contact Sales",
      },
    ],
  },
  {
    productName: "FinOps Intelligence",
    tiers: [
      {
        name: "Starter",
        description: "Basic cost visibility and alerts",
        monthlyPrice: 299,
        annualPrice: 239,
        features: [
          "Cost dashboards",
          "Budget alerts",
          "Tag compliance",
          "1 cloud provider",
          "Monthly reports",
        ],
        cta: "Start Free Trial",
      },
      {
        name: "Pro",
        description: "Advanced optimization and forecasting",
        monthlyPrice: 899,
        annualPrice: 719,
        features: [
          "Multi-cloud support",
          "AI cost anomaly detection",
          "Resource right-sizing",
          "Budget forecasting",
          "RI/SP optimization",
          "Custom allocation rules",
        ],
        highlighted: true,
        cta: "Start Free Trial",
      },
      {
        name: "Enterprise",
        description: "Full FinOps automation",
        monthlyPrice: null,
        annualPrice: null,
        features: [
          "Everything in Pro",
          "Chargeback engine",
          "Unit economics",
          "Executive dashboards",
          "API access",
          "Custom integrations",
        ],
        cta: "Contact Sales",
      },
    ],
  },
  {
    productName: "Compliance Automation",
    tiers: [
      {
        name: "Starter",
        description: "Basic compliance tracking",
        monthlyPrice: 399,
        annualPrice: 319,
        features: [
          "1 compliance framework",
          "Manual evidence upload",
          "Basic audit trail",
          "Compliance dashboard",
          "Quarterly reports",
        ],
        cta: "Start Free Trial",
      },
      {
        name: "Pro",
        description: "Automated compliance operations",
        monthlyPrice: 1199,
        annualPrice: 959,
        features: [
          "5 compliance frameworks",
          "Automated evidence collection",
          "Continuous monitoring",
          "Gap analysis",
          "Policy enforcement",
          "Integration support",
        ],
        highlighted: true,
        cta: "Start Free Trial",
      },
      {
        name: "Enterprise",
        description: "Enterprise-grade compliance",
        monthlyPrice: null,
        annualPrice: null,
        features: [
          "Unlimited frameworks",
          "Full evidence automation",
          "Regulatory change tracking",
          "Custom controls",
          "Auditor access portal",
          "GRC integration",
          "Dedicated CSM",
        ],
        cta: "Contact Sales",
      },
    ],
  },
  {
    productName: "API Platform",
    tiers: [
      {
        name: "Developer",
        description: "For individual developers and small projects",
        monthlyPrice: 99,
        annualPrice: 79,
        features: [
          "1,000 API calls/month",
          "3 API keys",
          "Community support",
          "OpenAPI playground",
          "Basic rate limiting",
        ],
        cta: "Start Free Trial",
      },
      {
        name: "Team",
        description: "For teams building integrations at scale",
        monthlyPrice: 499,
        annualPrice: 399,
        features: [
          "50,000 API calls/month",
          "Unlimited API keys",
          "Webhook delivery",
          "Priority support",
          "Custom rate limits",
          "SDK access",
        ],
        highlighted: true,
        cta: "Start Free Trial",
      },
      {
        name: "Enterprise",
        description: "For platform teams with custom requirements",
        monthlyPrice: null,
        annualPrice: null,
        features: [
          "Unlimited API calls",
          "Dedicated endpoints",
          "SLA guarantee",
          "Custom SDKs",
          "On-premise deployment",
          "Terraform provider",
          "Dedicated support",
        ],
        cta: "Contact Sales",
      },
    ],
  },
  {
    productName: "Agent Marketplace",
    tiers: [
      {
        name: "Free",
        description: "Access community agents and playbooks",
        monthlyPrice: 0,
        annualPrice: 0,
        features: [
          "Browse all listings",
          "Install free agents",
          "Community playbooks",
          "Basic support",
          "Public reviews",
        ],
        cta: "Get Started",
      },
      {
        name: "Publisher",
        description: "Publish and monetize your agents",
        monthlyPrice: 199,
        annualPrice: 159,
        features: [
          "Publish unlimited agents",
          "Revenue sharing (80/20)",
          "Analytics dashboard",
          "Priority review",
          "Publisher badge",
          "Promotion placement",
        ],
        highlighted: true,
        cta: "Start Publishing",
      },
      {
        name: "Enterprise",
        description: "Private marketplace for your organization",
        monthlyPrice: null,
        annualPrice: null,
        features: [
          "Private marketplace",
          "Custom approval workflows",
          "Internal-only agents",
          "Compliance scanning",
          "SSO integration",
          "Dedicated catalog",
          "Volume licensing",
        ],
        cta: "Contact Sales",
      },
    ],
  },
];

export const FAQ = [
  {
    question: "Can I try ShieldOps for free?",
    answer:
      "Yes! All Starter and Pro plans include a 14-day free trial with full access. No credit card required.",
  },
  {
    question: "What happens when I exceed my plan limits?",
    answer:
      "We'll notify you when you're approaching limits and help you choose the right plan. Service continues uninterrupted.",
  },
  {
    question: "Can I mix products from different tiers?",
    answer:
      "Absolutely. Each product is priced independently, so you can choose Starter for FinOps and Enterprise for SRE, for example.",
  },
  {
    question: "Do you offer annual discounts?",
    answer:
      "Yes, annual billing saves 20% compared to monthly billing across all products and tiers.",
  },
  {
    question: "Is there a platform bundle discount?",
    answer:
      "Yes. Organizations purchasing 3+ products receive an additional 15% bundle discount. Contact sales for details.",
  },
];
