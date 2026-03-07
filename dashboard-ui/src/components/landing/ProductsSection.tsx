import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import clsx from "clsx";
import { PRODUCTS } from "../../config/products";
import AnimatedSection from "./AnimatedSection";

const products = Object.values(PRODUCTS);

export default function ProductsSection() {
  return (
    <section className="px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <AnimatedSection>
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight text-gray-50 sm:text-4xl">
              One platform, four products
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-400">
              Choose the modules that fit your needs — or deploy the full platform for unified operations.
            </p>
          </div>
        </AnimatedSection>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {products.map((product, i) => {
            const Icon = product.icon;
            return (
              <AnimatedSection key={product.id} delay={i * 0.1}>
                <Link
                  to={`/products/${product.id}`}
                  className={clsx(
                    "group flex flex-col rounded-xl border border-gray-800 bg-gray-900 p-6 transition-all hover:border-gray-700 hover:bg-gray-900/80",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={clsx(
                        "rounded-lg bg-gradient-to-br p-2.5",
                        product.bgGradient,
                      )}
                    >
                      <Icon className={clsx("h-5 w-5", product.color)} />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-100">{product.name}</h3>
                      <p className="text-sm text-gray-500">{product.tagline}</p>
                    </div>
                  </div>
                  <p className="mt-4 flex-1 text-sm leading-relaxed text-gray-400">
                    {product.description}
                  </p>
                  <div className="mt-4 flex items-center gap-1 text-sm font-medium text-brand-400 transition-colors group-hover:text-brand-300">
                    Learn more
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                  </div>
                </Link>
              </AnimatedSection>
            );
          })}
        </div>
      </div>
    </section>
  );
}
