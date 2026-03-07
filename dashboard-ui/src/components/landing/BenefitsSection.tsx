import { Clock, BellOff, Target, Zap } from "lucide-react";

const BENEFITS = [
  {
    icon: Clock,
    metric: "7 min",
    label: "Mean Time to Resolve",
    description: "Down from 45 minutes with manual triage",
  },
  {
    icon: BellOff,
    metric: "72%",
    label: "Auto-Resolved",
    description: "Incidents resolved without human intervention",
  },
  {
    icon: Target,
    metric: "99.95%",
    label: "SLO Compliance",
    description: "Error budgets preserved with proactive remediation",
  },
  {
    icon: Zap,
    metric: "3x",
    label: "Engineering Velocity",
    description: "Less firefighting, more building features",
  },
];

export default function BenefitsSection() {
  return (
    <section id="benefits" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-50">
            Measurable impact from day one
          </h2>
          <p className="mt-3 text-gray-400">
            Real results from teams running ShieldOps in production.
          </p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {BENEFITS.map((b) => (
            <div
              key={b.label}
              className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-center"
            >
              <b.icon className="mx-auto h-8 w-8 text-brand-400" />
              <p className="mt-4 text-3xl font-bold text-brand-400">
                {b.metric}
              </p>
              <h3 className="mt-2 text-sm font-semibold text-gray-100">
                {b.label}
              </h3>
              <p className="mt-1 text-xs text-gray-500">
                {b.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
