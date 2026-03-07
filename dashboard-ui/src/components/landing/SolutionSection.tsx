import { Search, Wrench, Brain } from "lucide-react";

const CAPABILITIES = [
  {
    icon: Search,
    title: "Investigate",
    description:
      "AI agents correlate logs, metrics, and traces across your entire stack. Root cause identified in minutes, not hours.",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
  },
  {
    icon: Wrench,
    title: "Remediate",
    description:
      "Agents execute infrastructure changes — rollbacks, scaling, patches — with OPA policy gates and human approval for high-risk actions.",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
  },
  {
    icon: Brain,
    title: "Learn",
    description:
      "Every incident makes the system smarter. Agents update playbooks, refine thresholds, and build institutional knowledge.",
    color: "text-violet-400",
    bg: "bg-violet-500/10",
  },
];

export default function SolutionSection() {
  return (
    <section id="solution" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-50">
            An AI SRE that actually takes action
          </h2>
          <p className="mt-3 text-gray-400">
            Not just monitoring. Not just alerting. Autonomous resolution.
          </p>
        </div>
        <div className="mt-12 grid gap-8 lg:grid-cols-3">
          {CAPABILITIES.map((cap) => (
            <div
              key={cap.title}
              className="rounded-xl border border-gray-800 bg-gray-900/50 p-8"
            >
              <div
                className={`inline-flex rounded-lg p-3 ${cap.bg}`}
              >
                <cap.icon className={`h-6 w-6 ${cap.color}`} />
              </div>
              <h3 className="mt-5 text-xl font-semibold text-gray-100">
                {cap.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-gray-400">
                {cap.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
