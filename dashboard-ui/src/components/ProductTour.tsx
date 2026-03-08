import { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { X, ChevronRight, ChevronLeft, Sparkles } from "lucide-react";
import clsx from "clsx";
import { isDemoMode } from "../demo/config";

// ── Tour steps ───────────────────────────────────────────────────

interface TourStep {
  title: string;
  description: string;
  path: string;
  highlight?: string; // CSS selector to highlight
  position: "center" | "bottom-right" | "top-center";
}

const TOUR_STEPS: TourStep[] = [
  {
    title: "Welcome to ShieldOps",
    description:
      "The autonomous SRE agent platform that doesn't just analyze — it acts. Let's take a quick tour of the key features.",
    path: "/app",
    position: "center",
  },
  {
    title: "Agent Factory",
    description:
      "Describe any SRE task in natural language. Our AI agents will investigate, diagnose, and fix issues autonomously — with your approval at every step.",
    path: "/app",
    position: "bottom-right",
  },
  {
    title: "War Rooms",
    description:
      "When critical incidents happen, ShieldOps auto-creates war rooms — coordinating on-call teams, posting investigation results, and executing remediations in real-time.",
    path: "/app/war-room",
    position: "bottom-right",
  },
  {
    title: "Investigations",
    description:
      "AI agents perform root cause analysis across logs, metrics, and traces — correlating signals from Splunk, Datadog, CloudWatch, and more.",
    path: "/app/investigations",
    position: "bottom-right",
  },
  {
    title: "Remediations",
    description:
      "Not just analysis — execution. Agents restart pods, rollback deployments, scale resources, and rotate credentials. Every action passes OPA policy gates.",
    path: "/app/remediations",
    position: "bottom-right",
  },
  {
    title: "Security Operations",
    description:
      "CVE scanning, secret detection, certificate monitoring, and automated credential rotation — all handled by autonomous security agents.",
    path: "/app/security",
    position: "bottom-right",
  },
  {
    title: "Analytics & Performance",
    description:
      "Track MTTR reduction, auto-resolution rates, and agent accuracy. See the impact of autonomous operations on your team's velocity.",
    path: "/app/analytics",
    position: "bottom-right",
  },
  {
    title: "You're All Set!",
    description:
      "Explore the full platform — try submitting a prompt in Agent Factory, browse playbooks, or check the compliance dashboard. Questions? Use the AI chat in the bottom right.",
    path: "/app",
    position: "center",
  },
];

const TOUR_KEY = "shieldops_tour_complete";

// ── Component ────────────────────────────────────────────────────

export default function ProductTour() {
  const [step, setStep] = useState(0);
  const [isActive, setIsActive] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Auto-start tour for first-time demo visitors
  useEffect(() => {
    if (isDemoMode() && !localStorage.getItem(TOUR_KEY)) {
      const timer = setTimeout(() => setIsActive(true), 800);
      return () => clearTimeout(timer);
    }
  }, []);

  const currentStep = TOUR_STEPS[step];

  const goNext = useCallback(() => {
    if (step < TOUR_STEPS.length - 1) {
      const nextStep = TOUR_STEPS[step + 1];
      if (nextStep.path !== location.pathname) {
        navigate(nextStep.path);
      }
      setStep((s) => s + 1);
    } else {
      localStorage.setItem(TOUR_KEY, "true");
      setIsActive(false);
    }
  }, [step, location.pathname, navigate]);

  const goPrev = useCallback(() => {
    if (step > 0) {
      const prevStep = TOUR_STEPS[step - 1];
      if (prevStep.path !== location.pathname) {
        navigate(prevStep.path);
      }
      setStep((s) => s - 1);
    }
  }, [step, location.pathname, navigate]);

  const dismiss = useCallback(() => {
    localStorage.setItem(TOUR_KEY, "true");
    setIsActive(false);
  }, []);

  // Keyboard navigation
  useEffect(() => {
    if (!isActive) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === "Escape") {
        dismiss();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isActive, goNext, goPrev, dismiss]);

  if (!isActive || !currentStep) return null;

  const isFirst = step === 0;
  const isLast = step === TOUR_STEPS.length - 1;
  const progress = ((step + 1) / TOUR_STEPS.length) * 100;

  return (
    <div className="fixed inset-0 z-[60]">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Tour card */}
      <div
        className={clsx(
          "absolute z-10 w-full max-w-md",
          currentStep.position === "center" &&
            "left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
          currentStep.position === "bottom-right" &&
            "bottom-8 right-8",
          currentStep.position === "top-center" &&
            "left-1/2 top-24 -translate-x-1/2",
        )}
      >
        <div className="overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
          {/* Progress bar */}
          <div className="h-1 bg-gray-800">
            <div
              className="h-full bg-brand-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="p-5">
            {/* Header */}
            <div className="mb-3 flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-brand-400" />
                <h3 className="text-lg font-semibold text-gray-100">
                  {currentStep.title}
                </h3>
              </div>
              <button
                onClick={dismiss}
                className="rounded p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <p className="mb-5 text-sm leading-relaxed text-gray-400">
              {currentStep.description}
            </p>

            {/* Footer */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-600">
                {step + 1} / {TOUR_STEPS.length}
              </span>

              <div className="flex items-center gap-2">
                {!isFirst && (
                  <button
                    onClick={goPrev}
                    className="flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back
                  </button>
                )}
                {isFirst && (
                  <button
                    onClick={dismiss}
                    className="rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:text-gray-300"
                  >
                    Skip tour
                  </button>
                )}
                <button
                  onClick={goNext}
                  className="flex items-center gap-1 rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-600"
                >
                  {isLast ? "Get Started" : "Next"}
                  {!isLast && <ChevronRight className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
