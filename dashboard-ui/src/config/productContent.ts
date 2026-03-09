import type { ProductId } from "./products";

interface Feature {
  title: string;
  description: string;
}

interface Metric {
  label: string;
  value: string;
}

interface ProductContent {
  hero: string;
  features: Feature[];
  metrics: Metric[];
  integrations: string[];
}

export const PRODUCT_CONTENT: Record<Exclude<ProductId, "platform">, ProductContent> = {
  sre: {
    hero: "Autonomous agents that investigate alerts, identify root causes, execute remediations, and learn from every incident.",
    features: [
      {
        title: "Fleet Overview",
        description:
          "Real-time visibility into all services, agents, and infrastructure health across your entire fleet.",
      },
      {
        title: "AI Investigation",
        description:
          "Agents autonomously correlate logs, metrics, and traces to identify root causes in minutes, not hours.",
      },
      {
        title: "Auto-Remediation",
        description:
          "Execute remediations with built-in safety rails — rollback, blast-radius limits, and policy gates.",
      },
      {
        title: "Predictive Analytics",
        description:
          "ML-powered predictions for capacity, incidents, and SLO breaches before they happen.",
      },
      {
        title: "Capacity Forecasting",
        description:
          "Forecast resource demand across compute, storage, and network with confidence intervals.",
      },
      {
        title: "Learning Engine",
        description:
          "Agents learn from past incidents to refine playbooks, thresholds, and response strategies.",
      },
    ],
    metrics: [
      { label: "MTTR Reduction", value: "73%" },
      { label: "Auto-resolved Incidents", value: "85%" },
      { label: "False Positive Reduction", value: "91%" },
      { label: "Coverage", value: "500+ services" },
    ],
    integrations: [
      "AWS",
      "GCP",
      "Azure",
      "Kubernetes",
      "Datadog",
      "PagerDuty",
      "Splunk",
      "Prometheus",
    ],
  },
  soc: {
    hero: "AI-powered security operations — from threat hunting and vulnerability management to automated incident response.",
    features: [
      {
        title: "Threat Detection",
        description:
          "Real-time threat hunting with MITRE ATT&CK mapping, IOC sweeps, and behavioral analysis.",
      },
      {
        title: "Vulnerability Management",
        description:
          "Automated vulnerability lifecycle — scan, prioritize, patch, and verify across all environments.",
      },
      {
        title: "Incident Correlation",
        description:
          "Cross-signal correlation engine linking alerts, logs, and network flows into attack stories.",
      },
      {
        title: "Playbook Automation",
        description:
          "Visual playbook editor with conditional logic, approval gates, and automated execution.",
      },
      {
        title: "Attack Surface Monitoring",
        description:
          "Continuous external asset discovery, shadow IT detection, and exposure scoring.",
      },
      {
        title: "Compliance Integration",
        description:
          "Map security controls to compliance frameworks — SOC 2, ISO 27001, NIST, PCI DSS.",
      },
    ],
    metrics: [
      { label: "Alert Triage Time", value: "-89%" },
      { label: "Threat Detection", value: "< 5 min" },
      { label: "Vuln Remediation", value: "3x faster" },
      { label: "SOC Efficiency", value: "+67%" },
    ],
    integrations: [
      "CrowdStrike",
      "Sentinel",
      "Splunk SIEM",
      "VirusTotal",
      "MITRE ATT&CK",
      "Snyk",
      "Qualys",
      "Tenable",
    ],
  },
  finops: {
    hero: "Intelligent cloud cost optimization — anomaly detection, forecasting, and resource right-sizing across all providers.",
    features: [
      {
        title: "Cost Analytics",
        description:
          "Real-time cost breakdowns by service, team, environment, and tag across all cloud providers.",
      },
      {
        title: "Anomaly Detection",
        description:
          "ML-powered spend anomaly detection with root cause analysis and automated alerts.",
      },
      {
        title: "Budget Forecasting",
        description:
          "Accurate budget forecasts with confidence intervals and trend analysis.",
      },
      {
        title: "Resource Right-Sizing",
        description:
          "AI recommendations for instance types, reserved instances, and savings plans.",
      },
      {
        title: "Tag Governance",
        description:
          "Automated tag enforcement, orphan resource detection, and cost allocation validation.",
      },
      {
        title: "Billing Intelligence",
        description:
          "Invoice reconciliation, commitment tracking, and unit economics analysis.",
      },
    ],
    metrics: [
      { label: "Cost Savings", value: "35%" },
      { label: "Forecast Accuracy", value: "94%" },
      { label: "Waste Detected", value: "$2.4M/yr" },
      { label: "ROI", value: "12x" },
    ],
    integrations: [
      "AWS Cost Explorer",
      "GCP Billing",
      "Azure Cost Mgmt",
      "Spot.io",
      "CloudHealth",
      "Kubecost",
    ],
  },
  compliance: {
    hero: "Continuous compliance monitoring, automated evidence collection, and real-time audit readiness across your infrastructure.",
    features: [
      {
        title: "Compliance Dashboard",
        description:
          "Real-time compliance posture across SOC 2, ISO 27001, HIPAA, PCI DSS, and GDPR.",
      },
      {
        title: "Evidence Automation",
        description:
          "Automated evidence collection, chain-of-custody tracking, and freshness monitoring.",
      },
      {
        title: "Audit Trail",
        description:
          "Immutable audit logs for every configuration change, access event, and policy decision.",
      },
      {
        title: "Policy Enforcement",
        description:
          "OPA-based policy engine ensuring infrastructure changes comply with regulations.",
      },
      {
        title: "Gap Analysis",
        description:
          "Continuous compliance gap detection with prioritized remediation recommendations.",
      },
      {
        title: "Regulatory Tracking",
        description:
          "Track regulatory changes and automatically assess impact on your compliance posture.",
      },
    ],
    metrics: [
      { label: "Audit Prep Time", value: "-80%" },
      { label: "Control Coverage", value: "98%" },
      { label: "Evidence Auto-collected", value: "92%" },
      { label: "Compliance Drift", value: "< 2 hrs" },
    ],
    integrations: [
      "AWS Config",
      "Azure Policy",
      "GCP Org Policy",
      "OPA",
      "Vanta",
      "Drata",
      "ServiceNow",
      "Jira",
    ],
  },
  api: {
    hero: "Embed ShieldOps intelligence into your own tools. Metered APIs for investigations, remediations, cost analysis, and security operations — with full OpenAPI documentation.",
    features: [
      {
        title: "RESTful Agent APIs",
        description:
          "Trigger investigations, remediations, and scans programmatically with versioned REST endpoints.",
      },
      {
        title: "Metered Usage",
        description:
          "Pay-per-execution pricing — per investigation, per remediation, per 1K analytics queries.",
      },
      {
        title: "Webhook Events",
        description:
          "Real-time webhook delivery for agent completions, alerts, and status changes.",
      },
      {
        title: "SDK Libraries",
        description:
          "Official Python, TypeScript, and Go SDKs with type-safe clients and retry logic.",
      },
      {
        title: "Rate Limiting & Auth",
        description:
          "JWT authentication, API key management, and configurable rate limits per tenant.",
      },
      {
        title: "OpenAPI Documentation",
        description:
          "Auto-generated interactive API docs with request/response examples and testing sandbox.",
      },
    ],
    metrics: [
      { label: "API Uptime", value: "99.95%" },
      { label: "Avg Latency", value: "< 200ms" },
      { label: "Endpoints", value: "120+" },
      { label: "SDKs", value: "3 languages" },
    ],
    integrations: [
      "REST API",
      "GraphQL",
      "Webhooks",
      "Python SDK",
      "TypeScript SDK",
      "Go SDK",
      "Terraform Provider",
      "GitHub Actions",
    ],
  },
  marketplace: {
    hero: "The app store for SRE, SOC, and FinOps agents. Discover community-built agents, connectors, and industry-specific playbooks — or publish your own.",
    features: [
      {
        title: "Agent Registry",
        description:
          "Browse and deploy pre-built agents for specific use cases — SAP monitoring, SIEM integration, compliance frameworks.",
      },
      {
        title: "Connector Hub",
        description:
          "Community connectors for niche monitoring tools, ticketing systems, and cloud services.",
      },
      {
        title: "Playbook Library",
        description:
          "Industry-specific playbooks for FinServ, Healthcare, Gaming, and regulated industries.",
      },
      {
        title: "Revenue Sharing",
        description:
          "Publish paid plugins and earn revenue. Enterprise customers get private marketplace governance.",
      },
      {
        title: "Version Management",
        description:
          "Semantic versioning, automatic updates, and rollback support for all marketplace items.",
      },
      {
        title: "Security Scanning",
        description:
          "Every marketplace submission undergoes automated security scanning and manual review.",
      },
    ],
    metrics: [
      { label: "Published Agents", value: "200+" },
      { label: "Connectors", value: "85+" },
      { label: "Playbooks", value: "150+" },
      { label: "Contributors", value: "500+" },
    ],
    integrations: [
      "GitHub",
      "GitLab",
      "npm Registry",
      "PyPI",
      "Docker Hub",
      "Helm Charts",
    ],
  },
};
