const INTEGRATIONS = [
  "Kubernetes",
  "AWS",
  "GCP",
  "Azure",
  "Prometheus",
  "Datadog",
  "Splunk",
  "Grafana",
  "PagerDuty",
  "Slack",
  "OPA",
  "Terraform",
  "GitHub Actions",
  "Jira",
  "PostgreSQL",
  "Redis",
];

export default function IntegrationsSection() {
  return (
    <section id="integrations" className="bg-gray-900/30 px-6 py-20">
      <div className="mx-auto max-w-4xl text-center">
        <h2 className="text-3xl font-bold text-gray-50">
          Works with your stack
        </h2>
        <p className="mt-3 text-gray-400">
          Plug into the tools you already use. No rip-and-replace.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {INTEGRATIONS.map((name) => (
            <span
              key={name}
              className="rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-2 text-sm font-medium text-gray-300"
            >
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
