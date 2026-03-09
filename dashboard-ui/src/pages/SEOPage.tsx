import { useParams, Navigate, Link } from "react-router-dom";
import { useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowRight,
  Zap,
  Eye,
  Search,
  LinkIcon,
} from "lucide-react";
import clsx from "clsx";
import { getSEOPageBySlug, SEO_PAGES } from "../config/seo-pages";
import type { SEOSeverity } from "../config/seo-pages";
import AnimatedSection from "../components/landing/AnimatedSection";

const SEVERITY_STYLES: Record<SEOSeverity, { bg: string; text: string; label: string }> = {
  critical: { bg: "bg-red-500/10 border-red-500/30", text: "text-red-400", label: "Critical" },
  high: { bg: "bg-amber-500/10 border-amber-500/30", text: "text-amber-400", label: "High" },
  medium: {
    bg: "bg-yellow-500/10 border-yellow-500/30",
    text: "text-yellow-400",
    label: "Medium",
  },
};

export default function SEOPage() {
  const { slug } = useParams<{ slug: string }>();
  const page = slug ? getSEOPageBySlug(slug) : undefined;

  useEffect(() => {
    if (page) {
      document.title = `${page.title} | ShieldOps`;
      const meta = document.querySelector('meta[name="description"]');
      if (meta) {
        meta.setAttribute("content", page.metaDescription);
      } else {
        const newMeta = document.createElement("meta");
        newMeta.name = "description";
        newMeta.content = page.metaDescription;
        document.head.appendChild(newMeta);
      }
    }
    return () => {
      document.title = "ShieldOps";
    };
  }, [page]);

  if (!page) {
    return <Navigate to="/solutions" replace />;
  }

  const severity = SEVERITY_STYLES[page.severity];
  const relatedPages = page.relatedPages
    .map((s) => SEO_PAGES.find((p) => p.slug === s))
    .filter(Boolean);

  return (
    <div className="pt-24">
      {/* Hero */}
      <section className="px-6 pb-12 pt-12">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <div className="mb-6 flex flex-wrap items-center gap-3">
              <span
                className={clsx(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                  severity.bg,
                  severity.text,
                )}
              >
                <AlertTriangle className="h-3 w-3" />
                {severity.label} Severity
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-800/50 px-3 py-1 text-xs font-medium text-gray-400">
                {page.category.charAt(0).toUpperCase() + page.category.slice(1)}
              </span>
            </div>

            <h1 className="text-3xl font-bold leading-tight tracking-tight text-gray-50 sm:text-4xl lg:text-5xl">
              {page.title}
            </h1>

            <p className="mt-6 text-lg text-gray-400">{page.metaDescription}</p>

            <div className="mt-8 flex items-center gap-3 rounded-lg border border-brand-500/30 bg-brand-500/10 px-5 py-3">
              <Zap className="h-5 w-5 shrink-0 text-brand-400" />
              <p className="text-sm text-brand-300">
                <span className="font-semibold text-brand-200">ShieldOps fixes this in {page.agentTime}</span>{" "}
                — fully automated, no manual intervention needed.
              </p>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* Symptoms */}
      <section className="border-t border-gray-800 px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/10">
                <Eye className="h-5 w-5 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold text-gray-50">Symptoms</h2>
            </div>
            <p className="mb-6 text-gray-400">
              How you will recognize this issue in your environment:
            </p>
            <ul className="space-y-3">
              {page.symptoms.map((symptom, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-red-400" />
                  <span className="text-gray-300">{symptom}</span>
                </li>
              ))}
            </ul>
          </AnimatedSection>
        </div>
      </section>

      {/* Common Causes */}
      <section className="border-t border-gray-800 bg-gray-900/30 px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10">
                <Search className="h-5 w-5 text-amber-400" />
              </div>
              <h2 className="text-2xl font-bold text-gray-50">Common Causes</h2>
            </div>
            <p className="mb-6 text-gray-400">
              The most frequent root causes we see across production environments:
            </p>
            <ol className="space-y-4">
              {page.causes.map((cause, i) => (
                <li key={i} className="flex items-start gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-sm font-semibold text-amber-400">
                    {i + 1}
                  </span>
                  <span className="pt-0.5 text-gray-300">{cause}</span>
                </li>
              ))}
            </ol>
          </AnimatedSection>
        </div>
      </section>

      {/* Manual Fix Steps */}
      <section className="border-t border-gray-800 px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-700/50">
                <Clock className="h-5 w-5 text-gray-400" />
              </div>
              <h2 className="text-2xl font-bold text-gray-50">Manual Fix Steps</h2>
            </div>
            <p className="mb-6 text-gray-400">
              The traditional way to diagnose and resolve this issue:
            </p>
            <ol className="space-y-4">
              {page.manualSteps.map((step, i) => (
                <li key={i} className="flex items-start gap-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-gray-700 text-sm font-medium text-gray-500">
                    {i + 1}
                  </span>
                  <div className="pt-0.5 text-gray-300">
                    <ManualStepContent text={step} />
                  </div>
                </li>
              ))}
            </ol>
          </AnimatedSection>
        </div>
      </section>

      {/* Agent Fix CTA */}
      <section className="border-t border-gray-800 bg-gray-900/30 px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <div className="overflow-hidden rounded-2xl border border-brand-500/20 bg-gradient-to-br from-brand-500/5 to-brand-600/5">
              <div className="border-b border-brand-500/20 bg-brand-500/10 px-6 py-4 sm:px-8">
                <div className="flex items-center gap-3">
                  <Zap className="h-6 w-6 text-brand-400" />
                  <h2 className="text-xl font-bold text-gray-50 sm:text-2xl">
                    Fix it Automatically with ShieldOps
                  </h2>
                </div>
              </div>
              <div className="px-6 py-8 sm:px-8">
                <div className="mb-6 flex items-center gap-4">
                  <div className="flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5">
                    <Clock className="h-4 w-4 text-emerald-400" />
                    <span className="text-sm font-semibold text-emerald-400">{page.agentTime}</span>
                  </div>
                  <span className="text-sm text-gray-500">Average resolution time</span>
                </div>

                <p className="mb-8 text-gray-300 leading-relaxed">{page.agentFix}</p>

                <div className="mb-8 grid gap-3 sm:grid-cols-2">
                  {[
                    "Automatic root cause detection",
                    "Policy-gated remediation",
                    "Full audit trail",
                    "Rollback on failure",
                  ].map((feature) => (
                    <div key={feature} className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 shrink-0 text-emerald-400" />
                      <span className="text-sm text-gray-400">{feature}</span>
                    </div>
                  ))}
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <Link
                    to="/login"
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-500"
                  >
                    Start Free Trial
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    to="/pricing"
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
                  >
                    View Pricing
                  </Link>
                </div>
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* Related Issues */}
      {relatedPages.length > 0 && (
        <section className="border-t border-gray-800 px-6 py-16">
          <div className="mx-auto max-w-3xl">
            <AnimatedSection>
              <div className="mb-6 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/10">
                  <LinkIcon className="h-5 w-5 text-brand-400" />
                </div>
                <h2 className="text-2xl font-bold text-gray-50">Related Issues</h2>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {relatedPages.map((related) => {
                  if (!related) return null;
                  const relSev = SEVERITY_STYLES[related.severity];
                  return (
                    <Link
                      key={related.slug}
                      to={`/solutions/${related.slug}`}
                      className="group rounded-xl border border-gray-800 bg-gray-900/50 p-4 transition-colors hover:border-gray-700 hover:bg-gray-900"
                    >
                      <span
                        className={clsx(
                          "mb-3 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
                          relSev.bg,
                          relSev.text,
                        )}
                      >
                        {relSev.label}
                      </span>
                      <h3 className="text-sm font-medium text-gray-200 group-hover:text-white">
                        {related.title}
                      </h3>
                    </Link>
                  );
                })}
              </div>
            </AnimatedSection>
          </div>
        </section>
      )}

      {/* Bottom CTA */}
      <section className="border-t border-gray-800 bg-gradient-to-b from-gray-900/50 to-gray-950 px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <AnimatedSection>
            <h2 className="text-2xl font-bold text-gray-50 sm:text-3xl">
              Stop firefighting. Let AI agents handle it.
            </h2>
            <p className="mt-4 text-gray-400">
              ShieldOps autonomous agents investigate, diagnose, and remediate incidents across your
              entire infrastructure — in seconds, not hours.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                to="/login"
                className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-500"
              >
                Start Free Trial
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/solutions"
                className="inline-flex items-center gap-2 text-sm font-medium text-gray-400 transition-colors hover:text-white"
              >
                Browse all solutions
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </AnimatedSection>
        </div>
      </section>
    </div>
  );
}

/** Renders manual step text, highlighting inline code blocks wrapped in backticks. */
function ManualStepContent({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("`") && part.endsWith("`") ? (
          <code
            key={i}
            className="rounded bg-gray-800 px-1.5 py-0.5 text-sm font-mono text-brand-300"
          >
            {part.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
