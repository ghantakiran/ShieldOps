import { ShieldCheck, RotateCcw, UserCheck } from "lucide-react";

const PILLARS = [
  {
    icon: ShieldCheck,
    title: "OPA Policy Gates",
    description:
      "Every agent action is evaluated against Open Policy Agent rules before execution. Define blast-radius limits, environment restrictions, and change windows.",
  },
  {
    icon: RotateCcw,
    title: "Snapshot Rollback",
    description:
      "Pre-remediation snapshots are taken automatically. One-click rollback if anything goes wrong. Full audit trail for every change.",
  },
  {
    icon: UserCheck,
    title: "Human-in-the-Loop",
    description:
      "High-risk actions require human approval. Configurable risk thresholds let you decide what runs automatically and what needs a review.",
  },
];

export default function SafetySection() {
  return (
    <section id="safety" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-50">
            Built for security-first enterprises
          </h2>
          <p className="mt-3 text-gray-400">
            Autonomous doesn't mean uncontrolled. Every action is governed.
          </p>
        </div>
        <div className="mt-12 grid gap-8 lg:grid-cols-3">
          {PILLARS.map((pillar) => (
            <div
              key={pillar.title}
              className="rounded-xl border border-gray-800 bg-gray-900/50 p-8"
            >
              <pillar.icon className="h-8 w-8 text-emerald-400" />
              <h3 className="mt-5 text-lg font-semibold text-gray-100">
                {pillar.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-gray-400">
                {pillar.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
