import { useEffect, useState } from "react";
import { HardDrive, AlertTriangle, CheckCircle, Clock } from "lucide-react";

interface CapacityRisk {
  resource: string;
  current_usage_pct: number;
  projected_usage_pct: number;
  days_until_breach: number;
  confidence: number;
}

export default function CapacityForecast() {
  const [risks, setRisks] = useState<CapacityRisk[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/capacity/risks")
      .then((r) => r.json())
      .then((data) => setRisks(data.risks || []))
      .catch(() => setRisks([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Clock className="mr-2 h-5 w-5 animate-spin text-gray-400" />
        <span className="text-gray-400">Loading capacity forecasts...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <HardDrive className="h-6 w-6 text-brand-400" />
        <h1 className="text-2xl font-semibold">Capacity Planning</h1>
      </div>

      <p className="text-sm text-gray-400">
        Resource usage forecasts and capacity breach predictions.
      </p>

      {risks.length === 0 ? (
        <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-8 text-center">
          <CheckCircle className="mx-auto mb-3 h-10 w-10 text-green-400" />
          <p className="text-gray-300">All resources within healthy capacity thresholds.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {risks.map((risk) => (
            <div
              key={risk.resource}
              className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
            >
              <div className="mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-orange-400" />
                <h3 className="font-medium text-gray-200">{risk.resource}</h3>
              </div>
              <div className="space-y-2 text-sm text-gray-400">
                <div className="flex justify-between">
                  <span>Current</span>
                  <span className="text-gray-200">{risk.current_usage_pct.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between">
                  <span>Projected</span>
                  <span className="text-orange-300">{risk.projected_usage_pct.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between">
                  <span>Days to breach</span>
                  <span className="text-red-300">{risk.days_until_breach}d</span>
                </div>
                {/* Usage bar */}
                <div className="h-2 rounded-full bg-gray-700">
                  <div
                    className="h-2 rounded-full bg-orange-500"
                    style={{ width: `${Math.min(risk.current_usage_pct, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
