import clsx from "clsx";

interface SecurityScoreGaugeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

export default function SecurityScoreGauge({
  score,
  size = "md",
}: SecurityScoreGaugeProps) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const circumference = 2 * Math.PI * 45;
  const dashOffset = circumference * (1 - clampedScore / 100);

  const dimensions: Record<string, number> = { sm: 80, md: 120, lg: 160 };
  const dim = dimensions[size];

  const textSize = { sm: "text-lg", md: "text-2xl", lg: "text-4xl" }[size];
  const labelSize = { sm: "text-[10px]", md: "text-xs", lg: "text-sm" }[size];

  function scoreColor(): string {
    if (clampedScore >= 90) return "#22c55e";
    if (clampedScore >= 70) return "#eab308";
    if (clampedScore >= 50) return "#f97316";
    return "#ef4444";
  }

  function scoreLabel(): string {
    if (clampedScore >= 90) return "Excellent";
    if (clampedScore >= 70) return "Good";
    if (clampedScore >= 50) return "Fair";
    if (clampedScore >= 30) return "Poor";
    return "Critical";
  }

  return (
    <div className="relative flex flex-col items-center">
      <svg width={dim} height={dim} viewBox="0 0 100 100">
        {/* Background circle */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="#374151"
          strokeWidth="8"
        />
        {/* Score arc */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke={scoreColor()}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          transform="rotate(-90 50 50)"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      {/* Centered label overlay */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center"
        style={{ width: dim, height: dim }}
      >
        <span className={clsx("font-bold text-gray-100", textSize)}>
          {clampedScore.toFixed(0)}
        </span>
        <span className={clsx("text-gray-500", labelSize)}>{scoreLabel()}</span>
      </div>
    </div>
  );
}
