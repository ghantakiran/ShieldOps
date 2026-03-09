import { Link } from "react-router-dom";
import {
  ArrowRight,
  Server,
  Shield,
  DollarSign,
  FileCheck,
  Code,
  Store,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

interface UseCase {
  icon: LucideIcon;
  color: string;
  borderHover: string;
  title: string;
  description: string;
  link: string;
  tag: string;
  tagColor: string;
}

const USE_CASES: UseCase[] = [
  {
    icon: Server,
    color: "text-brand-400",
    borderHover: "hover:border-brand-500/40",
    title: "Managed SRE as a Service",
    description:
      "We operate ShieldOps for you — a virtual SRE team that monitors, investigates, and remediates 24/7. Perfect for teams that can't staff a dedicated SRE function.",
    link: "/products/sre",
    tag: "MSP Model",
    tagColor: "text-brand-400 bg-brand-500/10",
  },
  {
    icon: Shield,
    color: "text-red-400",
    borderHover: "hover:border-red-500/40",
    title: "Autonomous SOC Platform",
    description:
      "AI-first SOC that triages alerts, correlates telemetry, runs threat hunts, and triggers SOAR playbooks. Deploy in-house or through MSSP partners.",
    link: "/products/soc",
    tag: "Security",
    tagColor: "text-red-400 bg-red-500/10",
  },
  {
    icon: DollarSign,
    color: "text-emerald-400",
    borderHover: "hover:border-emerald-500/40",
    title: "FinOps Cost Intelligence",
    description:
      "Detect cost anomalies, optimize reserved instances, enforce tag governance, and forecast budgets with ML-powered accuracy.",
    link: "/products/finops",
    tag: "FinOps",
    tagColor: "text-emerald-400 bg-emerald-500/10",
  },
  {
    icon: FileCheck,
    color: "text-amber-400",
    borderHover: "hover:border-amber-500/40",
    title: "Compliance Automation",
    description:
      "Continuous SOC 2, PCI-DSS, HIPAA, and GDPR compliance. Automated evidence collection, gap analysis, and audit-ready reporting.",
    link: "/products/compliance",
    tag: "Compliance",
    tagColor: "text-amber-400 bg-amber-500/10",
  },
  {
    icon: Code,
    color: "text-sky-400",
    borderHover: "hover:border-sky-500/40",
    title: "Developer API Platform",
    description:
      "Expose ShieldOps capabilities as metered APIs. Tool vendors and platform teams embed investigations, remediations, and analytics into their own products.",
    link: "/products/api",
    tag: "Platform",
    tagColor: "text-sky-400 bg-sky-500/10",
  },
  {
    icon: Store,
    color: "text-orange-400",
    borderHover: "hover:border-orange-500/40",
    title: "Agent Marketplace",
    description:
      "Discover community-built agents, connectors, and industry playbooks. Publish your own and earn revenue through the ecosystem.",
    link: "/products/marketplace",
    tag: "Ecosystem",
    tagColor: "text-orange-400 bg-orange-500/10",
  },
];

export default function UseCasesSection() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-gray-50">
            Built for every ops team
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-400">
            From SRE to SOC to FinOps — deploy the right agents for your use
            case.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {USE_CASES.map((uc) => {
            const Icon = uc.icon;
            return (
              <Link
                key={uc.title}
                to={uc.link}
                className={clsx(
                  "group flex flex-col rounded-xl border border-gray-800 bg-gray-900 p-6 transition-all hover:border-gray-600 hover:shadow-lg hover:shadow-gray-900/50",
                  uc.borderHover,
                )}
              >
                <span
                  className={clsx(
                    "mb-4 inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-medium",
                    uc.tagColor,
                  )}
                >
                  {uc.tag}
                </span>
                <div className="mb-3 flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-800/60">
                    <Icon className={clsx("h-5 w-5", uc.color)} />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-100">
                    {uc.title}
                  </h3>
                </div>
                <p className="flex-1 text-sm leading-relaxed text-gray-400">
                  {uc.description}
                </p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-gray-500 transition-colors group-hover:text-brand-400">
                  Learn more
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
