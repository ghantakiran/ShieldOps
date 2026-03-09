import { Bell, Clock, Users, TrendingDown } from "lucide-react";

const PAIN_POINTS = [
  {
    icon: Bell,
    title: "Alert Fatigue",
    description: "Hundreds of alerts daily, most noise. Your team is burnt out triaging false positives.",
  },
  {
    icon: Clock,
    title: "Slow MTTR",
    description: "Root cause analysis takes hours. Engineers context-switch across dashboards, logs, and metrics.",
  },
  {
    icon: Users,
    title: "On-Call Burnout",
    description: "Rotating on-call is a morale killer. Senior engineers spend nights restarting pods.",
  },
  {
    icon: TrendingDown,
    title: "Missed SLOs",
    description: "Incidents snowball before anyone responds. Error budgets burn while humans sleep.",
  },
];

export default function ProblemSection() {
  return (
    <section id="problem" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-50">
            Your on-call team is drowning
          </h2>
          <p className="mt-3 text-gray-400">
            Manual incident response doesn't scale.
          </p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PAIN_POINTS.map((point) => (
            <div
              key={point.title}
              className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 transition-all hover:border-red-500/30 hover:shadow-lg hover:shadow-gray-900/50"
            >
              <point.icon className="h-8 w-8 text-red-400" />
              <h3 className="mt-4 text-lg font-semibold text-gray-100">
                {point.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-gray-400">
                {point.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
