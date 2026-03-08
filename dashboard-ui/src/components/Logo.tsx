import clsx from "clsx";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

/** Custom ShieldOps logo mark — a layered shield with an integrated pulse line. */
export default function Logo({ size = "md", showText = true, className }: LogoProps) {
  const sizes = {
    sm: { icon: "h-5 w-5", text: "text-sm" },
    md: { icon: "h-7 w-7", text: "text-lg" },
    lg: { icon: "h-10 w-10", text: "text-2xl" },
  };

  const s = sizes[size];

  return (
    <span className={clsx("inline-flex items-center gap-2", className)}>
      <svg
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={s.icon}
        aria-hidden="true"
      >
        {/* Outer shield */}
        <path
          d="M16 2L4 8v8c0 7.18 5.12 13.9 12 16 6.88-2.1 12-8.82 12-16V8L16 2z"
          fill="#0891b2"
        />
        {/* Inner shield layer */}
        <path
          d="M16 5L7 9.5v6.5c0 5.4 3.84 10.44 9 12 5.16-1.56 9-6.6 9-12V9.5L16 5z"
          fill="#083344"
        />
        {/* Pulse/heartbeat line across shield */}
        <path
          d="M8 17h4l2-4 2.5 8L19 13l1.5 4H24"
          stroke="#22d3ee"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
      {showText && (
        <span className={clsx("font-semibold tracking-tight text-gray-100", s.text)}>
          Shield<span className="text-brand-400">Ops</span>
        </span>
      )}
    </span>
  );
}
