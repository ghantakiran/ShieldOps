import { Shield, Clock, Zap, Users, type LucideIcon } from "lucide-react";

interface Stat {
  icon: LucideIcon;
  value: string;
  label: string;
}

const STATS: Stat[] = [
  { icon: Shield, value: "99.95%", label: "Platform Uptime" },
  { icon: Clock, value: "< 3 min", label: "Avg Response Time" },
  { icon: Zap, value: "85%", label: "Incidents Auto-Resolved" },
  { icon: Users, value: "200+", label: "Engineering Teams" },
];

const TRUSTED_BY = [
  "Fortune 500 FinTech",
  "Top 10 Healthcare System",
  "Global SaaS Platform",
  "Leading Cloud Provider",
  "Enterprise Retailer",
];

export default function SocialProofSection() {
  return (
    <section className="border-y border-gray-800 bg-gray-900/30 px-6 py-14">
      <div className="mx-auto max-w-5xl">
        {/* Stats */}
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {STATS.map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="text-center">
                <Icon className="mx-auto mb-2 h-5 w-5 text-brand-400" />
                <p className="text-3xl font-bold text-white">{stat.value}</p>
                <p className="mt-1 text-sm text-gray-500">{stat.label}</p>
              </div>
            );
          })}
        </div>

        {/* Trust logos */}
        <div className="mt-12 text-center">
          <p className="mb-4 text-xs font-medium uppercase tracking-wider text-gray-600">
            Trusted by engineering teams at
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            {TRUSTED_BY.map((name) => (
              <span
                key={name}
                className="rounded-full border border-gray-800 bg-gray-900 px-4 py-2 text-sm text-gray-400"
              >
                {name}
              </span>
            ))}
          </div>
          <p className="mt-4 text-xs text-gray-600">
            Currently onboarding design partners
          </p>
        </div>
      </div>
    </section>
  );
}
