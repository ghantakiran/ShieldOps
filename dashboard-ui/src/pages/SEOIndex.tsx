import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useEffect } from "react";
import {
  Search,
  AlertTriangle,
  ArrowRight,
  Shield,
  Server,
  Lock,
  Gauge,
  Network,
} from "lucide-react";
import clsx from "clsx";
import { SEO_PAGES, SEO_CATEGORIES } from "../config/seo-pages";
import type { SEOCategory, SEOSeverity } from "../config/seo-pages";
import AnimatedSection from "../components/landing/AnimatedSection";

const CATEGORY_ICONS: Record<SEOCategory, React.ElementType> = {
  kubernetes: Server,
  aws: Shield,
  security: Lock,
  performance: Gauge,
  networking: Network,
};

const SEVERITY_STYLES: Record<SEOSeverity, { bg: string; text: string; label: string }> = {
  critical: { bg: "bg-red-500/10 border-red-500/30", text: "text-red-400", label: "Critical" },
  high: { bg: "bg-amber-500/10 border-amber-500/30", text: "text-amber-400", label: "High" },
  medium: {
    bg: "bg-yellow-500/10 border-yellow-500/30",
    text: "text-yellow-400",
    label: "Medium",
  },
};

const ALL_CATEGORIES = Object.keys(SEO_CATEGORIES) as SEOCategory[];

export default function SEOIndex() {
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<SEOCategory | "all">("all");

  useEffect(() => {
    document.title = "Solutions — How to Fix Infrastructure Issues | ShieldOps";
    const meta = document.querySelector('meta[name="description"]');
    const content =
      "Browse 50+ guides on fixing Kubernetes, AWS, security, performance, and networking issues. Learn how ShieldOps AI agents automate incident resolution.";
    if (meta) {
      meta.setAttribute("content", content);
    } else {
      const newMeta = document.createElement("meta");
      newMeta.name = "description";
      newMeta.content = content;
      document.head.appendChild(newMeta);
    }
    return () => {
      document.title = "ShieldOps";
    };
  }, []);

  const filtered = useMemo(() => {
    let pages = SEO_PAGES;
    if (activeCategory !== "all") {
      pages = pages.filter((p) => p.category === activeCategory);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      pages = pages.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          p.metaDescription.toLowerCase().includes(q) ||
          p.symptoms.some((s) => s.toLowerCase().includes(q)),
      );
    }
    return pages;
  }, [search, activeCategory]);

  const grouped = useMemo(() => {
    const map = new Map<SEOCategory, typeof filtered>();
    for (const page of filtered) {
      const list = map.get(page.category) || [];
      list.push(page);
      map.set(page.category, list);
    }
    return map;
  }, [filtered]);

  return (
    <div className="pt-24">
      {/* Hero */}
      <section className="px-6 pb-8 pt-12">
        <div className="mx-auto max-w-4xl text-center">
          <AnimatedSection>
            <h1 className="text-4xl font-bold tracking-tight text-gray-50 sm:text-5xl">
              How to Fix Infrastructure Issues
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-400">
              Step-by-step troubleshooting guides for Kubernetes, AWS, security, performance, and
              networking issues — plus how ShieldOps AI agents resolve them in seconds.
            </p>
          </AnimatedSection>
        </div>
      </section>

      {/* Search + Filter */}
      <section className="border-y border-gray-800 bg-gray-900/50 px-6 py-6">
        <div className="mx-auto max-w-4xl">
          <AnimatedSection>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search issues (e.g. CrashLoopBackOff, OOM, 502...)"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 py-2.5 pl-10 pr-4 text-sm text-gray-200 placeholder-gray-500 outline-none transition-colors focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <FilterButton
                  active={activeCategory === "all"}
                  onClick={() => setActiveCategory("all")}
                >
                  All ({SEO_PAGES.length})
                </FilterButton>
                {ALL_CATEGORIES.map((cat) => {
                  const Icon = CATEGORY_ICONS[cat];
                  const count = SEO_PAGES.filter((p) => p.category === cat).length;
                  return (
                    <FilterButton
                      key={cat}
                      active={activeCategory === cat}
                      onClick={() => setActiveCategory(cat)}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {SEO_CATEGORIES[cat].label} ({count})
                    </FilterButton>
                  );
                })}
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* Results */}
      <section className="px-6 py-12">
        <div className="mx-auto max-w-4xl">
          {filtered.length === 0 ? (
            <div className="py-20 text-center">
              <p className="text-gray-500">No matching issues found. Try a different search term.</p>
            </div>
          ) : (
            <div className="space-y-12">
              {ALL_CATEGORIES.filter((cat) => grouped.has(cat)).map((cat) => {
                const pages = grouped.get(cat)!;
                const Icon = CATEGORY_ICONS[cat];
                return (
                  <AnimatedSection key={cat}>
                    <div className="mb-4 flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-800">
                        <Icon className="h-4 w-4 text-gray-400" />
                      </div>
                      <h2 className="text-lg font-semibold text-gray-200">
                        {SEO_CATEGORIES[cat].label}
                      </h2>
                      <span className="text-sm text-gray-600">{pages.length} issues</span>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {pages.map((page) => {
                        const sev = SEVERITY_STYLES[page.severity];
                        return (
                          <Link
                            key={page.slug}
                            to={`/solutions/${page.slug}`}
                            className="group flex flex-col rounded-xl border border-gray-800 bg-gray-900/50 p-4 transition-colors hover:border-gray-700 hover:bg-gray-900"
                          >
                            <div className="mb-3 flex items-center gap-2">
                              <span
                                className={clsx(
                                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
                                  sev.bg,
                                  sev.text,
                                )}
                              >
                                <AlertTriangle className="h-3 w-3" />
                                {sev.label}
                              </span>
                            </div>
                            <h3 className="mb-2 text-sm font-medium text-gray-200 group-hover:text-white">
                              {page.title}
                            </h3>
                            <p className="mb-3 line-clamp-2 text-xs text-gray-500">
                              {page.metaDescription}
                            </p>
                            <div className="mt-auto flex items-center justify-between">
                              <span className="text-xs text-brand-400">
                                Auto-fix in {page.agentTime}
                              </span>
                              <ArrowRight className="h-3.5 w-3.5 text-gray-600 transition-colors group-hover:text-brand-400" />
                            </div>
                          </Link>
                        );
                      })}
                    </div>
                  </AnimatedSection>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="border-t border-gray-800 bg-gradient-to-b from-gray-900/50 to-gray-950 px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <AnimatedSection>
            <h2 className="text-2xl font-bold text-gray-50 sm:text-3xl">
              Tired of manual troubleshooting?
            </h2>
            <p className="mt-4 text-gray-400">
              ShieldOps AI agents handle investigation, diagnosis, and remediation automatically.
              Deploy autonomous SRE in minutes.
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
                to="/pricing"
                className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
              >
                View Pricing
              </Link>
            </div>
          </AnimatedSection>
        </div>
      </section>
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "bg-brand-500/20 text-brand-300 border border-brand-500/30"
          : "border border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-300",
      )}
    >
      {children}
    </button>
  );
}
