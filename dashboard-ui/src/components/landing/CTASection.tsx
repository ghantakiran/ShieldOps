import { Link } from "react-router-dom";
import { Play, ArrowRight } from "lucide-react";

export default function CTASection() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-3xl rounded-2xl border border-gray-800 bg-gray-900 p-12 text-center">
        <h2 className="text-3xl font-bold text-gray-50">
          See ShieldOps on your incidents
        </h2>
        <p className="mt-4 text-gray-400">
          Start with a live demo using sample data, or book a walkthrough with our team
          to see it on your infrastructure.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            to="/app?demo=true"
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white transition-all hover:bg-brand-500"
          >
            <Play className="h-4 w-4" />
            Try the Live Demo
          </Link>
          <a
            href="mailto:founders@shieldops.io"
            className="inline-flex items-center gap-2 text-sm font-medium text-gray-400 transition-colors hover:text-white"
          >
            Contact Sales
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>
        <p className="mt-6 text-xs text-gray-600">
          No sign-up required. Currently onboarding select design partners.
        </p>
      </div>
    </section>
  );
}
