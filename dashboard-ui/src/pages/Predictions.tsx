import { useEffect, useState } from "react";
import { TrendingUp, AlertTriangle, CheckCircle, Clock } from "lucide-react";

interface Prediction {
  id: string;
  service: string;
  predicted_issue: string;
  severity: string;
  confidence: number;
  predicted_at: string;
  predicted_time: string;
  status: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-600",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-blue-500",
};

export default function Predictions() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/predictions/active")
      .then((r) => r.json())
      .then((data) => setPredictions(data.predictions || []))
      .catch(() => setPredictions([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Clock className="mr-2 h-5 w-5 animate-spin text-gray-400" />
        <span className="text-gray-400">Loading predictions...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-6 w-6 text-brand-400" />
        <h1 className="text-2xl font-semibold">Predictive Incident Detection</h1>
      </div>

      <p className="text-sm text-gray-400">
        AI-powered predictions of potential incidents before they trigger alerts.
      </p>

      {predictions.length === 0 ? (
        <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-8 text-center">
          <CheckCircle className="mx-auto mb-3 h-10 w-10 text-green-400" />
          <p className="text-gray-300">No active predictions — all systems nominal.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {predictions.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 p-4"
            >
              <div className="flex items-center gap-3">
                <AlertTriangle className="h-5 w-5 text-yellow-400" />
                <div>
                  <p className="font-medium text-gray-200">{p.predicted_issue}</p>
                  <p className="text-sm text-gray-400">
                    Service: {p.service} &middot; Predicted: {p.predicted_time}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium text-white ${SEVERITY_COLORS[p.severity] || "bg-gray-600"}`}
                >
                  {p.severity}
                </span>
                <span className="text-sm text-gray-400">
                  {(p.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
