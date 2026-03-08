import { Bell, Search, Target, ShieldCheck, CheckCircle } from "lucide-react";

const STEPS = [
  { icon: Bell, label: "Alert Fires", description: "PagerDuty, Prometheus, CloudWatch" },
  { icon: Search, label: "AI Investigates", description: "Logs, metrics, traces correlated" },
  { icon: Target, label: "Root Cause Found", description: "91% confidence in minutes" },
  { icon: ShieldCheck, label: "Policy Check", description: "OPA validates remediation" },
  { icon: CheckCircle, label: "Auto-Resolve", description: "Rollback, scale, or patch" },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-gray-900/30 px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-50">
            How it works
          </h2>
          <p className="mt-3 text-gray-400">
            From alert to resolution in minutes, not hours.
          </p>
        </div>

        {/* Steps */}
        <div className="mt-12 flex flex-col items-center gap-4 lg:flex-row lg:gap-0">
          {STEPS.map((step, idx) => (
            <div key={step.label} className="flex items-center">
              <div className="flex flex-col items-center text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-gray-700 bg-gray-800/80">
                  <step.icon className="h-7 w-7 text-brand-400" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-gray-100">
                  {step.label}
                </h3>
                <p className="mt-1 w-36 text-xs text-gray-500">
                  {step.description}
                </p>
              </div>
              {idx < STEPS.length - 1 && (
                <div className="mx-4 hidden h-px w-12 bg-gray-700 lg:block" />
              )}
            </div>
          ))}
        </div>

        {/* Code snippet */}
        <div className="mx-auto mt-16 max-w-2xl rounded-xl border border-gray-800 bg-gray-950 p-6">
          <div className="mb-3 flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-500" />
            <span className="h-3 w-3 rounded-full bg-yellow-500" />
            <span className="h-3 w-3 rounded-full bg-green-500" />
            <span className="ml-2 text-xs text-gray-500">investigation-agent.log</span>
          </div>
          <pre className="overflow-x-auto text-xs leading-relaxed text-gray-400">
            <code>{`[14:23:01] Alert received: KubePodCrashLooping on payment-service
[14:23:04] Analyzing pod logs... found 47 OOMKilled events
[14:23:08] Correlating metrics: memory usage 2.1Gi (limit: 1.5Gi)
[14:23:12] Checking recent deployments: v2.3.1 deployed 2h ago
[14:23:15] Root cause: Redis connection pool leak in v2.3.1
[14:23:15] Confidence: 91% | Recommended: rollback to v2.3.0
[14:23:18] OPA policy check: PASS (rollback_deployment allowed)
[14:23:20] Awaiting approval for production rollback...`}</code>
          </pre>
        </div>
      </div>
    </section>
  );
}
