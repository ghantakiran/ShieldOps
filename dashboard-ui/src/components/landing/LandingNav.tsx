import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Menu, X } from "lucide-react";
import clsx from "clsx";
import { PRODUCTS } from "../../config/products";
import Logo from "../Logo";

const productEntries = Object.values(PRODUCTS);

export default function LandingNav() {
  const [productsOpen, setProductsOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setProductsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <nav className="fixed top-0 z-50 w-full border-b border-gray-800/50 bg-gray-950/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center gap-2">
          <Logo />
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-8 md:flex">
          {/* Products dropdown */}
          <div ref={dropdownRef} className="relative">
            <button
              onClick={() => setProductsOpen(!productsOpen)}
              className="flex items-center gap-1 text-sm text-gray-400 transition-colors hover:text-white"
              aria-expanded={productsOpen}
              aria-haspopup="true"
            >
              Products
              <ChevronDown
                className={clsx(
                  "h-3.5 w-3.5 transition-transform",
                  productsOpen && "rotate-180",
                )}
              />
            </button>

            {productsOpen && (
              <div className="absolute left-1/2 top-full mt-3 w-72 -translate-x-1/2 rounded-xl border border-gray-800 bg-gray-900 p-2 shadow-xl">
                {productEntries.map((product) => {
                  const Icon = product.icon;
                  return (
                    <Link
                      key={product.id}
                      to={`/products/${product.id}`}
                      onClick={() => setProductsOpen(false)}
                      className="flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-gray-800"
                    >
                      <Icon className={clsx("mt-0.5 h-5 w-5 shrink-0", product.color)} />
                      <div>
                        <p className="text-sm font-medium text-gray-200">{product.name}</p>
                        <p className="text-xs text-gray-500">{product.tagline}</p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          <Link
            to="/pricing"
            className="text-sm text-gray-400 transition-colors hover:text-white"
          >
            Pricing
          </Link>

          <Link
            to="/app?demo=true"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
          >
            Try Live Demo
          </Link>
          <a
            href="mailto:founders@shieldops.io"
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
          >
            Contact Sales
          </a>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="rounded-lg p-1.5 text-gray-400 hover:text-white md:hidden focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-gray-800 bg-gray-950 px-6 py-4 md:hidden">
          <div className="flex flex-col gap-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Products
            </p>
            {productEntries.map((product) => {
              const Icon = product.icon;
              return (
                <Link
                  key={product.id}
                  to={`/products/${product.id}`}
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-3 text-sm text-gray-300 hover:text-white"
                >
                  <Icon className={clsx("h-4 w-4", product.color)} />
                  {product.name}
                </Link>
              );
            })}
            <hr className="border-gray-800" />
            <Link
              to="/pricing"
              onClick={() => setMobileOpen(false)}
              className="text-sm text-gray-300 hover:text-white"
            >
              Pricing
            </Link>
            <Link
              to="/app?demo=true"
              onClick={() => setMobileOpen(false)}
              className="rounded-lg bg-brand-600 px-4 py-2 text-center text-sm font-medium text-white"
            >
              Try Live Demo
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
