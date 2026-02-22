import { Code, Copy } from "lucide-react";

const TF_EXAMPLE = `# ShieldOps Terraform Provider — Example Configuration
resource "shieldops_agent" "investigation" {
  name = "investigation"
  config = {
    confidence_threshold = 0.85
    max_time_seconds     = 600
    environment          = "production"
  }
}

resource "shieldops_playbook" "restart_service" {
  name = "restart-service"
  config = {
    trigger   = "high_cpu"
    action    = "restart"
    cooldown  = 300
    max_blast = 1
  }
}

resource "shieldops_policy" "prod_safety" {
  name = "production-safety"
  config = {
    require_approval  = true
    max_blast_radius  = 3
    deny_destructive  = true
  }
}

resource "shieldops_webhook_subscription" "slack_alerts" {
  name = "slack-incident-alerts"
  config = {
    url    = "https://hooks.slack.com/services/T00/B00/XXX"
    events = ["incident.created", "incident.resolved"]
  }
}`;

export default function InfraAsCode() {
  const handleCopy = () => {
    navigator.clipboard.writeText(TF_EXAMPLE);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Code className="h-6 w-6 text-brand-400" />
        <h1 className="text-2xl font-semibold">Infrastructure as Code</h1>
      </div>

      <p className="text-sm text-gray-400">
        Manage ShieldOps configuration with Terraform. Use the provider below to declare agents,
        playbooks, policies, and webhook subscriptions as code.
      </p>

      <div className="rounded-lg border border-gray-700 bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2">
          <span className="text-sm font-medium text-gray-300">main.tf</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-800 hover:text-gray-200"
          >
            <Copy className="h-3 w-3" /> Copy
          </button>
        </div>
        <pre className="overflow-x-auto p-4 text-sm text-gray-300">
          <code>{TF_EXAMPLE}</code>
        </pre>
      </div>

      <div className="space-y-3">
        <h2 className="text-lg font-medium">API Endpoints</h2>
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-800/50">
              <tr>
                <th className="px-4 py-2 text-left text-gray-400">Resource</th>
                <th className="px-4 py-2 text-left text-gray-400">Endpoints</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              <tr>
                <td className="px-4 py-2 text-gray-300">Agents</td>
                <td className="px-4 py-2 font-mono text-xs text-gray-400">
                  GET/POST/PUT/DELETE /api/v1/terraform/agents/:name
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 text-gray-300">Playbooks</td>
                <td className="px-4 py-2 font-mono text-xs text-gray-400">
                  GET/POST/PUT/DELETE /api/v1/terraform/playbooks/:name
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 text-gray-300">Policies</td>
                <td className="px-4 py-2 font-mono text-xs text-gray-400">
                  GET/POST/PUT/DELETE /api/v1/terraform/policies/:name
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 text-gray-300">Webhook Subs</td>
                <td className="px-4 py-2 font-mono text-xs text-gray-400">
                  GET/POST/PUT/DELETE /api/v1/terraform/webhook-subscriptions/:id
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 text-gray-300">State</td>
                <td className="px-4 py-2 font-mono text-xs text-gray-400">
                  GET/POST/DELETE /api/v1/terraform/state/:workspace
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
