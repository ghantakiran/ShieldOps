import { useParams, Navigate, Link } from "react-router-dom";
import { ArrowRight, CheckCircle } from "lucide-react";
import clsx from "clsx";
import { PRODUCTS, type ProductId } from "../config/products";
import { PRODUCT_CONTENT } from "../config/productContent";

const VALID_IDS = new Set<string>(Object.keys(PRODUCTS));

type MarketableProductId = Exclude<ProductId, "platform">;

export default function ProductLanding() {
  const { productId } = useParams<{ productId: string }>();

  if (!productId || !VALID_IDS.has(productId)) {
    return <Navigate to="/" replace />;
  }

  const id = productId as MarketableProductId;
  const product = PRODUCTS[id];
  const content = PRODUCT_CONTENT[id];
  const Icon = product.icon;

  return (
    <div className="pt-24">
      {/* Hero */}
      <section className="px-6 pb-16 pt-12">
        <div className="mx-auto max-w-4xl text-center">
          <div
            className={clsx(
              "mb-6 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm",
              id === "sre" && "border-brand-500/30 bg-brand-500/10 text-brand-400",
              id === "soc" && "border-red-500/30 bg-red-500/10 text-red-400",
              id === "finops" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
              id === "compliance" && "border-amber-500/30 bg-amber-500/10 text-amber-400",
              id === "api" && "border-sky-500/30 bg-sky-500/10 text-sky-400",
              id === "marketplace" && "border-orange-500/30 bg-orange-500/10 text-orange-400",
            )}
          >
            <Icon className="h-4 w-4" />
            {product.name}
          </div>

          <h1 className="text-4xl font-bold leading-tight tracking-tight text-gray-50 sm:text-5xl">
            {product.tagline}
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-gray-400">
            {content.hero}
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              to={product.demoPath}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-900/30 transition-colors hover:bg-brand-500"
            >
              Try {product.name} Demo
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/pricing"
              className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
            >
              View Pricing
            </Link>
          </div>
        </div>
      </section>

      {/* Metrics */}
      {content.metrics.length > 0 && (
        <section className="border-y border-gray-800 bg-gray-900/50 px-6 py-12">
          <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 md:grid-cols-4">
            {content.metrics.map((metric) => (
              <div key={metric.label} className="text-center">
                <p className={clsx("text-3xl font-bold", product.color)}>
                  {metric.value}
                </p>
                <p className="mt-1 text-sm text-gray-500">{metric.label}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Features grid */}
      {content.features.length > 0 && (
        <section className="px-6 py-16">
          <div className="mx-auto max-w-5xl">
            <h2 className="mb-12 text-center text-3xl font-bold text-gray-50">
              Everything you need
            </h2>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {content.features.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-xl border border-gray-800 bg-gray-900 p-6 transition-all hover:border-gray-600 hover:shadow-lg hover:shadow-gray-900/50"
                >
                  <h3 className="mb-2 text-lg font-semibold text-gray-100">
                    {feature.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-gray-400">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Integrations */}
      {content.integrations.length > 0 && (
        <section className="px-6 py-16">
          <div className="mx-auto max-w-4xl text-center">
            <h2 className="mb-8 text-2xl font-bold text-gray-50">
              Integrations
            </h2>
            <div className="flex flex-wrap justify-center gap-3">
              {content.integrations.map((name) => (
                <span
                  key={name}
                  className="flex items-center gap-2 rounded-full border border-gray-800 bg-gray-900 px-4 py-2 text-sm text-gray-300"
                >
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                  {name}
                </span>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* CTA */}
      <section className="px-6 py-16">
        <div className="mx-auto max-w-2xl rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center sm:p-12">
          <h2 className="text-2xl font-bold text-gray-50">
            Ready to get started?
          </h2>
          <p className="mt-3 text-gray-400">
            See {product.name} in action with our interactive demo.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              to={product.demoPath}
              className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-900/30 transition-colors hover:bg-brand-500"
            >
              Try {product.name} Demo
            </Link>
            <a
              href="mailto:founders@shieldops.io"
              className="rounded-lg border border-gray-700 px-6 py-3 text-sm font-medium text-gray-300 transition-all hover:border-gray-500 hover:bg-gray-900 hover:text-white"
            >
              Contact Sales
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
