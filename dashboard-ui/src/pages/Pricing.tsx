import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle, ChevronDown } from "lucide-react";
import clsx from "clsx";
import { PRICING, FAQ } from "../config/pricing";
import AnimatedSection from "../components/landing/AnimatedSection";

export default function Pricing() {
  const [annual, setAnnual] = useState(true);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="pt-24">
      {/* Header */}
      <section className="px-6 pb-8 pt-12 text-center">
        <AnimatedSection>
          <h1 className="text-4xl font-bold tracking-tight text-gray-50 sm:text-5xl">
            Simple, transparent pricing
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-400">
            Choose the products and tiers that match your needs. Start free, scale as you grow.
          </p>

          {/* Toggle */}
          <div className="mt-8 flex items-center justify-center gap-3">
            <span
              className={clsx(
                "text-sm font-medium",
                !annual ? "text-white" : "text-gray-500",
              )}
            >
              Monthly
            </span>
            <button
              onClick={() => setAnnual(!annual)}
              className={clsx(
                "relative h-6 w-11 rounded-full transition-colors",
                annual ? "bg-brand-500" : "bg-gray-700",
              )}
              role="switch"
              aria-checked={annual}
            >
              <div
                className={clsx(
                  "absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                  annual ? "translate-x-[22px]" : "translate-x-0.5",
                )}
              />
            </button>
            <span
              className={clsx(
                "text-sm font-medium",
                annual ? "text-white" : "text-gray-500",
              )}
            >
              Annual
              <span className="ml-1 text-xs text-emerald-400">Save 20%</span>
            </span>
          </div>
        </AnimatedSection>
      </section>

      {/* Product pricing sections */}
      {PRICING.map((product, pi) => (
        <section key={product.productName} className="px-6 py-12">
          <div className="mx-auto max-w-6xl">
            <AnimatedSection delay={pi * 0.1}>
              <h2 className="mb-8 text-center text-2xl font-bold text-gray-100">
                {product.productName}
              </h2>
            </AnimatedSection>

            <div className="grid gap-6 md:grid-cols-3">
              {product.tiers.map((tier, ti) => (
                <AnimatedSection key={tier.name} delay={pi * 0.1 + ti * 0.08}>
                  <div
                    className={clsx(
                      "flex h-full flex-col rounded-xl border p-6",
                      tier.highlighted
                        ? "border-brand-500/50 bg-brand-500/5"
                        : "border-gray-800 bg-gray-900",
                    )}
                  >
                    {tier.highlighted && (
                      <div className="mb-4 text-xs font-semibold uppercase tracking-wider text-brand-400">
                        Most Popular
                      </div>
                    )}
                    <h3 className="text-lg font-semibold text-gray-100">{tier.name}</h3>
                    <p className="mt-1 text-sm text-gray-500">{tier.description}</p>

                    <div className="mt-4">
                      {tier.monthlyPrice !== null ? (
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-bold text-gray-50">
                            ${annual ? tier.annualPrice : tier.monthlyPrice}
                          </span>
                          <span className="text-sm text-gray-500">/mo</span>
                        </div>
                      ) : (
                        <div className="text-2xl font-bold text-gray-50">Custom</div>
                      )}
                    </div>

                    <ul className="mt-6 flex-1 space-y-3">
                      {tier.features.map((feature) => (
                        <li key={feature} className="flex items-start gap-2 text-sm text-gray-300">
                          <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                          {feature}
                        </li>
                      ))}
                    </ul>

                    <div className="mt-6">
                      {tier.monthlyPrice !== null ? (
                        <Link
                          to="/app?demo=true"
                          className={clsx(
                            "block rounded-lg px-4 py-2.5 text-center text-sm font-medium transition-colors",
                            tier.highlighted
                              ? "bg-brand-500 text-white hover:bg-brand-600"
                              : "border border-gray-700 text-gray-300 hover:border-gray-500 hover:text-white",
                          )}
                        >
                          {tier.cta}
                        </Link>
                      ) : (
                        <a
                          href="mailto:founders@shieldops.io"
                          className="block rounded-lg border border-gray-700 px-4 py-2.5 text-center text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
                        >
                          {tier.cta}
                        </a>
                      )}
                    </div>
                  </div>
                </AnimatedSection>
              ))}
            </div>
          </div>
        </section>
      ))}

      {/* FAQ */}
      <section className="px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <AnimatedSection>
            <h2 className="mb-8 text-center text-2xl font-bold text-gray-100">
              Frequently asked questions
            </h2>
          </AnimatedSection>

          <div className="space-y-3">
            {FAQ.map((item, i) => (
              <AnimatedSection key={i} delay={i * 0.05}>
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full rounded-xl border border-gray-800 bg-gray-900 px-6 py-4 text-left transition-colors hover:border-gray-700"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-200">
                      {item.question}
                    </span>
                    <ChevronDown
                      className={clsx(
                        "h-4 w-4 shrink-0 text-gray-500 transition-transform",
                        openFaq === i && "rotate-180",
                      )}
                    />
                  </div>
                  {openFaq === i && (
                    <p className="mt-3 text-sm leading-relaxed text-gray-400">
                      {item.answer}
                    </p>
                  )}
                </button>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-16">
        <AnimatedSection>
          <div className="mx-auto max-w-2xl rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center sm:p-12">
            <h2 className="text-2xl font-bold text-gray-50">
              Not sure which plan is right?
            </h2>
            <p className="mt-3 text-gray-400">
              Try the live demo or talk to our team for a personalized recommendation.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                to="/app?demo=true"
                className="rounded-lg bg-brand-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
              >
                Try Live Demo
              </Link>
              <a
                href="mailto:founders@shieldops.io"
                className="rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
              >
                Talk to Sales
              </a>
            </div>
          </div>
        </AnimatedSection>
      </section>
    </div>
  );
}
