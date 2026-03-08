import { Link } from "react-router-dom";
import { ArrowRight, Play } from "lucide-react";

export default function HeroSection() {
  return (
    <section className="relative px-6 pb-20 pt-32">
      <div className="relative mx-auto max-w-4xl text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-600/40 bg-brand-950/60 px-4 py-1.5 text-sm text-brand-300">
          <span className="h-2 w-2 rounded-full bg-brand-400" />
          Now in Private Beta
        </div>

        <h1 className="text-4xl font-bold leading-tight tracking-tight text-gray-50 sm:text-5xl lg:text-6xl">
          Autonomous SRE agents that
          <br />
          <span className="text-brand-400">investigate, fix, and learn.</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-gray-400">
          ShieldOps deploys AI agents that respond to incidents in minutes — analyzing logs,
          identifying root causes, executing remediations, and improving over time.
          For SRE teams running production across AWS, GCP, Azure, and on-prem.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            to="/app?demo=true"
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-900/30 transition-all hover:bg-brand-500 hover:shadow-brand-900/50"
          >
            <Play className="h-4 w-4" />
            Try the Live Demo
          </Link>
          <a
            href="mailto:founders@shieldops.io"
            className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-all hover:border-gray-500 hover:bg-gray-900 hover:text-white"
          >
            Contact Sales
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>

        <p className="mt-8 text-sm text-gray-600">
          No sign-up required for demo. Currently onboarding design partners.
        </p>
      </div>
    </section>
  );
}
