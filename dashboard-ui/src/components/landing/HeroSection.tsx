import { Link } from "react-router-dom";
import { ArrowRight, Play } from "lucide-react";

export default function HeroSection() {
  return (
    <section className="relative overflow-hidden px-6 pb-20 pt-32">
      {/* Background gradient */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-brand-950/40 via-transparent to-transparent" />

      <div className="relative mx-auto max-w-4xl text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-4 py-1.5 text-sm text-brand-400">
          <span className="h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
          Now in Private Beta
        </div>

        <h1 className="text-4xl font-bold leading-tight tracking-tight text-gray-50 sm:text-5xl lg:text-6xl">
          Stop firefighting incidents.
          <br />
          <span className="text-brand-400">Let an AI SRE handle them.</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-gray-400">
          ShieldOps deploys autonomous AI agents that investigate alerts, identify root causes,
          execute remediations, and learn from outcomes — across AWS, GCP, Azure, and on-prem.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            to="/app?demo=true"
            className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
          >
            <Play className="h-4 w-4" />
            Try the Live Demo
          </Link>
          <a
            href="mailto:founders@shieldops.io"
            className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
          >
            Book a Demo
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          Trusted by SRE teams managing 500+ production services
        </p>
      </div>
    </section>
  );
}
